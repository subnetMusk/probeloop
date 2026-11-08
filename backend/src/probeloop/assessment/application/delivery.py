"""Descriptive audio/timing measures. No model, personality inference or quality score."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass

from probeloop.assessment.domain.model import DeliveryMetric
from probeloop.interview.application.ports import SessionStore
from probeloop.interview.domain.model import InterviewSession, Speaker
from probeloop.speech.audio import PcmAudio
from probeloop.speech.ports import VAD_WINDOW_SAMPLES, VoiceActivityDetector


@dataclass(frozen=True)
class Activity:
    speech_s: float
    first_s: float | None
    long_pauses: int
    pause_s: float


def activity(audio: PcmAudio, detector: VoiceActivityDetector) -> Activity:
    if audio.sample_rate != 16000:
        raise ValueError("VAD metrics require 16 kHz capture")
    window = VAD_WINDOW_SAMPLES * 2
    flags = [
        detector.speech_probability(audio.data[i : i + window]) >= 0.5
        for i in range(0, len(audio.data) - window + 1, window)
    ]
    voiced = [i for i, flag in enumerate(flags) if flag]
    step = VAD_WINDOW_SAMPLES / audio.sample_rate
    if not voiced:
        return Activity(0, None, 0, 0)
    pauses = []
    run = 0
    for flag in flags[voiced[0] : voiced[-1] + 1]:
        if not flag:
            run += 1
        elif run:
            if run * step >= 1:
                pauses.append(run * step)
            run = 0
    return Activity(len(voiced) * step, voiced[0] * step, len(pauses), sum(pauses))


class DeliveryAnalyser:
    def __init__(
        self, store: SessionStore, vad: Callable[[], VoiceActivityDetector] | None
    ) -> None:
        self.store = store
        self.vad = vad

    async def measure(self, session: InterviewSession, language: str) -> tuple[DeliveryMetric, ...]:
        it = language == "it"
        metrics: list[DeliveryMetric] = []
        times = {
            m.get("answer_turn_seq"): m.get("answer_latency_s")
            for m in await self.store.metrics(session.id)
            if m.get("kind") == "turn"
        }
        candidate_s = interviewer_s = 0.0
        for question in session.interviewer_turns():
            audio = await self.store.load_turn_audio(session.id, question.seq, Speaker.INTERVIEWER)
            if audio:
                interviewer_s += audio.duration_s
        for turn in session.candidate_turns():
            audio = await self.store.load_turn_audio(session.id, turn.seq, Speaker.CANDIDATE)
            duration = audio.duration_s if audio else None
            words = len(re.findall(r"\b[\w'-]+\b", turn.text))
            fillers = (
                r"\b(ehm|uhm|cioè|diciamo|praticamente)\b"
                if session.config.language.value == "it"
                else r"\b(um|uh|you know|like)\b"
            )
            filler_count = len(re.findall(fillers, turn.text, re.IGNORECASE))
            metrics.extend(
                (
                    DeliveryMetric(
                        "answer_duration",
                        round(duration, 2) if duration is not None else None,
                        "s",
                        "Durata dell'audio registrato." if it else "Recorded answer duration.",
                        turn.seq,
                    ),
                    DeliveryMetric(
                        "speaking_rate",
                        round(words * 60 / duration, 1) if duration else None,
                        "words/min",
                        "Parole per minuto, pause incluse."
                        if it
                        else "Words per recorded minute, including pauses.",
                        turn.seq,
                    ),
                    DeliveryMetric(
                        "fillers",
                        filler_count,
                        "count",
                        "Occorrenze lessicali, anche legittime; dipendono dal trascritto."
                        if it
                        else "Lexical matches may be meaningful words and depend on transcription.",
                        turn.seq,
                    ),
                )
            )
            if audio:
                candidate_s += audio.duration_s
            detected = (
                await asyncio.to_thread(activity, audio, self.vad()) if audio and self.vad else None
            )
            delay = times.get(turn.seq)
            latency = (
                float(delay) + detected.first_s
                if isinstance(delay, (float, int)) and detected and detected.first_s is not None
                else None
            )
            metrics.extend(
                (
                    DeliveryMetric(
                        "long_pauses",
                        detected.long_pauses if detected else None,
                        "count",
                        "Pause interne di almeno 1 s, VAD >=0.5 su finestre di 32 ms."
                        if it
                        else "Internal pauses >=1 s, VAD >=0.5 in 32 ms windows.",
                        turn.seq,
                    ),
                    DeliveryMetric(
                        "pause_duration",
                        round(detected.pause_s, 2) if detected else None,
                        "s",
                        "Somma delle pause interne lunghe; silenzio iniziale/finale escluso."
                        if it
                        else "Total long internal pauses; leading/trailing silence excluded.",
                        turn.seq,
                    ),
                    DeliveryMetric(
                        "answer_latency",
                        round(latency, 2) if latency is not None else None,
                        "s",
                        "Fine riproduzione dichiarata dal client fino al primo parlato. "
                        "NA senza tempi o parlato."
                        if it
                        else "Playback end to first speech; NA without timings or speech.",
                        turn.seq,
                    ),
                )
            )
        total = candidate_s + interviewer_s
        metrics.extend(
            (
                DeliveryMetric(
                    "candidate_talk_share",
                    round(candidate_s / total * 100, 1) if total else None,
                    "%",
                    "Quota dell'audio registrato, pause incluse."
                    if it
                    else "Share of recorded audio, including pauses.",
                ),
                DeliveryMetric(
                    "answer_budget_share",
                    round(candidate_s / session.config.target_duration_s * 100, 1)
                    if candidate_s
                    else None,
                    "%",
                    "Audio delle risposte rispetto alla durata obiettivo del colloquio."
                    if it
                    else "Recorded answers relative to the interview time budget.",
                ),
            )
        )
        return tuple(metrics)
