"""Composition root: the only place that chooses concrete adapters."""

from __future__ import annotations

import functools
import time
from dataclasses import dataclass

from probeloop.ai.debuglog import DebugLogChatModel
from probeloop.ai.ollama import OllamaChatModel
from probeloop.ai.ports import ChatModel
from probeloop.interview.application.llm_interviewer import LlmInterviewer
from probeloop.interview.application.service import SessionService
from probeloop.interview.application.voice import HealthCheck, VoiceServices
from probeloop.interview.domain.model import Language
from probeloop.settings import Settings
from probeloop.speech.fake import FakeSpeechToText, FakeTextToSpeech
from probeloop.speech.http_stt import HttpSpeechToText
from probeloop.speech.piper import PiperTextToSpeech
from probeloop.speech.ports import SpeechToText, TextToSpeech
from probeloop.speech.silero import SileroVad
from probeloop.storage.file_store import FileSessionStore


class SystemClock:
    def now(self) -> float:
        return time.time()


@dataclass(frozen=True, slots=True)
class Container:
    settings: Settings
    model: ChatModel
    sessions: SessionService


def build_voice(settings: Settings) -> VoiceServices | None:
    """The speech services for voice interviews, or None when they are not configured."""
    voices = {
        language: voice
        for language, voice in (
            (Language.ITALIAN, settings.tts_voice_it),
            (Language.ENGLISH, settings.tts_voice_en),
        )
        if voice
    }
    stt: SpeechToText
    tts: TextToSpeech
    checks: list[HealthCheck] = []
    if settings.speech_fake:
        stt, tts = FakeSpeechToText(), FakeTextToSpeech()
    elif settings.stt_url and settings.tts_url:
        http_stt = HttpSpeechToText(settings.stt_url, timeout_s=15.0)
        piper = PiperTextToSpeech(settings.tts_url, timeout_s=15.0)
        checks.append(http_stt.check)
        for voice in voices.values():
            checks.append(functools.partial(piper.check, voice))
        stt, tts = http_stt, piper
    else:
        return None
    return VoiceServices(
        stt=stt,
        tts=tts,
        vad=SileroVad,
        voices=voices,
        checks=checks,
        answer_warning_s=settings.answer_warning_s,
        answer_limit_s=settings.answer_limit_s,
    )


def build(
    settings: Settings,
    *,
    model: ChatModel | None = None,
    voice: VoiceServices | None = None,
) -> Container:
    if model is None:
        model = OllamaChatModel(
            base_url=settings.ollama_base_url,
            model=settings.interviewer_model,
            context_window=settings.context_window,
            keep_alive=settings.keep_alive,
        )
    if settings.llm_debug_log:
        model = DebugLogChatModel(model, settings.data_dir / "logs" / "llm.jsonl")
    if voice is None:
        voice = build_voice(settings)
    sessions = SessionService(
        store=FileSessionStore(settings.data_dir / "sessions"),
        interviewer=LlmInterviewer(model),
        clock=SystemClock(),
        voice=voice,
    )
    return Container(settings=settings, model=model, sessions=sessions)
