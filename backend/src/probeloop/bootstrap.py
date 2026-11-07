"""Composition root: the only place that chooses concrete adapters."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine

from probeloop.ai.debuglog import DebugLogChatModel
from probeloop.ai.fake import FakeChatModel
from probeloop.ai.ollama import OllamaChatModel
from probeloop.ai.ports import ChatModel, ChatRequest
from probeloop.ids import new_id
from probeloop.interview.application.llm_interviewer import LlmInterviewer
from probeloop.interview.application.service import SessionService
from probeloop.interview.application.transcripts import REFINE_JOB, TranscriptService
from probeloop.interview.application.voice import VoiceServices
from probeloop.interview.domain.model import InterviewSession, Language, Modality
from probeloop.platform.jobs import JobRunner
from probeloop.settings import Settings
from probeloop.speech.fake import FakeSpeechToText, FakeTextToSpeech
from probeloop.speech.http_stt import HttpSpeechToText
from probeloop.speech.piper import PiperTextToSpeech
from probeloop.speech.ports import SpeechToText
from probeloop.speech.silero import SileroVad
from probeloop.storage.database import create_engine, migrate, sessionmaker
from probeloop.storage.session_files import SessionFiles
from probeloop.storage.sql_jobs import SqlJobRepository
from probeloop.storage.sql_sessions import SqlSessionStore


class SystemClock:
    def now(self) -> float:
        return time.time()


@dataclass(frozen=True, slots=True)
class Container:
    settings: Settings
    model: ChatModel
    sessions: SessionService
    transcripts: TranscriptService
    jobs: JobRunner
    store: SqlSessionStore
    engine: AsyncEngine

    async def startup(self) -> None:
        """Bring the schema up to date, then resume the background jobs."""
        await migrate(self.engine)
        await self.jobs.start()

    async def shutdown(self) -> None:
        await self.sessions.shutdown()
        await self.jobs.stop()
        await self.engine.dispose()


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
    clock = SystemClock()
    engine = create_engine(settings.effective_database_url)
    db = sessionmaker(engine)
    store = SqlSessionStore(db, SessionFiles(settings.data_dir / "sessions"))
    transcripts = TranscriptService(store=store, clock=clock, refiner=build_refiner(settings))
    holder: dict[str, SessionService] = {}

    async def gate() -> None:
        await holder["sessions"].wait_until_idle()

    jobs = JobRunner(SqlJobRepository(db), now=clock.now, new_id=new_id, gate=gate)
    jobs.register(REFINE_JOB, transcripts.refine)

    async def on_finished(session: InterviewSession) -> None:
        if session.config.modality is Modality.VOICE and transcripts.can_refine:
            await jobs.submit(REFINE_JOB, session.id)

    sessions = SessionService(
        store=store,
        interviewer=LlmInterviewer(model),
        clock=clock,
        voice=voice,
        on_finished=on_finished,
    )
    holder["sessions"] = sessions
    return Container(
        settings=settings,
        model=model,
        sessions=sessions,
        transcripts=transcripts,
        jobs=jobs,
        store=store,
        engine=engine,
    )


def build_refiner(settings: Settings) -> SpeechToText | None:
    """The accurate recogniser of the refinement pass after the call."""
    if settings.speech_fake:
        return FakeSpeechToText()
    if settings.stt_url:
        # The first call loads Whisper in the worker, which takes minutes on a cold start.
        return HttpSpeechToText(settings.stt_url, engine="refine", timeout_s=900.0)
    return None
