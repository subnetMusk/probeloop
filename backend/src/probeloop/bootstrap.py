"""Composition root: the only place that chooses concrete adapters."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass

from probeloop.ai.debuglog import DebugLogChatModel
from probeloop.ai.fake import FakeChatModel
from probeloop.ai.ollama import OllamaChatModel
from probeloop.ai.ports import ChatModel, ChatRequest
from probeloop.interview.application.llm_interviewer import LlmInterviewer
from probeloop.interview.application.service import SessionService
from probeloop.interview.application.voice import VoiceServices
from probeloop.interview.domain.model import Language
from probeloop.settings import Settings
from probeloop.speech.fake import FakeSpeechToText, FakeTextToSpeech
from probeloop.speech.http_stt import HttpSpeechToText
from probeloop.speech.piper import PiperTextToSpeech
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
    if settings.speech_fake:
        return VoiceServices(
            stt=FakeSpeechToText(),
            tts=FakeTextToSpeech(),
            vad=SileroVad,
            voices=voices,
            answer_warning_s=settings.answer_warning_s,
            answer_limit_s=settings.answer_limit_s,
        )
    if not (settings.stt_url and settings.tts_url):
        return None
    stt = HttpSpeechToText(settings.stt_url, timeout_s=15.0)
    tts = PiperTextToSpeech(settings.tts_url, timeout_s=15.0)
    return VoiceServices(
        stt=stt,
        tts=tts,
        vad=SileroVad,
        voices=voices,
        stt_status=stt.status,
        tts_status=tts.status,
        answer_warning_s=settings.answer_warning_s,
        answer_limit_s=settings.answer_limit_s,
    )


def scripted_moves(questions: int = 3) -> Callable[[ChatRequest], str]:
    """Interviewer moves for end-to-end tests: numbered questions, then a farewell.

    The number comes from the request itself (each earlier move is an assistant message), so
    every session gets the same script.
    """

    def move(request: ChatRequest) -> str:
        asked = sum(1 for message in request.messages if message.role == "assistant")
        if asked >= questions:
            action, utterance = "end", "Grazie, il colloquio di prova è terminato."
        else:
            action, utterance = "follow_up", f"Questa è la domanda di prova numero {asked + 1}?"
        return json.dumps(
            {"action": action, "topic_id": "t1", "utterance": utterance, "covered_topic_ids": []}
        )

    return move


def build(
    settings: Settings,
    *,
    model: ChatModel | None = None,
    voice: VoiceServices | None = None,
) -> Container:
    if model is None and settings.llm_fake:
        model = FakeChatModel([scripted_moves()], chunk_delay_s=0.01)
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
