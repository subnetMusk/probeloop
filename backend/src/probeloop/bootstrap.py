"""Composition root: the only place that chooses concrete adapters."""

from __future__ import annotations

import time
from dataclasses import dataclass

from probeloop.ai.debuglog import DebugLogChatModel
from probeloop.ai.ollama import OllamaChatModel
from probeloop.ai.ports import ChatModel
from probeloop.interview.application.llm_interviewer import LlmInterviewer
from probeloop.interview.application.service import SessionService
from probeloop.settings import Settings
from probeloop.storage.file_store import FileSessionStore


class SystemClock:
    def now(self) -> float:
        return time.time()


@dataclass(frozen=True, slots=True)
class Container:
    settings: Settings
    model: ChatModel
    sessions: SessionService


def build(settings: Settings, *, model: ChatModel | None = None) -> Container:
    if model is None:
        model = OllamaChatModel(
            base_url=settings.ollama_base_url,
            model=settings.interviewer_model,
            context_window=settings.context_window,
            keep_alive=settings.keep_alive,
        )
    if settings.llm_debug_log:
        model = DebugLogChatModel(model, settings.data_dir / "logs" / "llm.jsonl")
    sessions = SessionService(
        store=FileSessionStore(settings.data_dir / "sessions"),
        interviewer=LlmInterviewer(model),
        clock=SystemClock(),
    )
    return Container(settings=settings, model=model, sessions=sessions)
