"""Ports used by the interview use cases."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from probeloop.interview.domain.model import (
    InterviewConfig,
    InterviewContext,
    InterviewerMove,
    InterviewSession,
    MoveAction,
    SessionStatus,
    Speaker,
    TopicCoverage,
    Turn,
)
from probeloop.interview.domain.time_policy import TimeDirective
from probeloop.speech.audio import PcmAudio


@dataclass(frozen=True, slots=True)
class MoveRequest:
    config: InterviewConfig
    context: InterviewContext
    turns: tuple[Turn, ...]
    coverage: Mapping[str, TopicCoverage]
    directive: TimeDirective
    remaining_s: float


@dataclass(frozen=True, slots=True)
class MoveDelta:
    """More of the utterance, plus the action and topic once they are known."""

    text: str
    action: MoveAction | None = None
    topic_id: str | None = None


@dataclass(frozen=True, slots=True)
class MoveDone:
    move: InterviewerMove


class Interviewer(Protocol):
    async def prepare(self, request: MoveRequest) -> None:
        """Load the model and warm its prompt cache before the interview starts."""
        ...

    async def check(self) -> None:
        """Raise when the model cannot be used now, for example after a sign-out."""
        ...

    def next_move(self, request: MoveRequest) -> AsyncIterator[MoveDelta | MoveDone]: ...


class Clock(Protocol):
    def now(self) -> float: ...


@dataclass(frozen=True, slots=True)
class SessionSummary:
    id: str
    created_at: float
    status: SessionStatus
    interview_type: str
    language: str
    ended_at: float | None = None
    execution_profile: str | None = None
    profile_id: str | None = None


class SessionStore(Protocol):
    async def save(self, session: InterviewSession) -> None: ...

    async def load(self, session_id: str) -> InterviewSession | None: ...

    async def summaries(self) -> list[SessionSummary]: ...

    async def delete(self, session_id: str) -> bool: ...

    async def save_turn_audio(
        self, session_id: str, turn_seq: int, speaker: Speaker, audio: PcmAudio
    ) -> None:
        """Keep the audio of one turn: answers can be transcribed again later."""
        ...

    async def load_turn_audio(
        self, session_id: str, turn_seq: int, speaker: Speaker
    ) -> PcmAudio | None: ...

    async def append_metrics(self, session_id: str, record: Mapping[str, object]) -> None: ...

    async def metrics(self, session_id: str) -> list[dict[str, Any]]: ...

    async def export(self, session: InterviewSession, *, audio: bool = True) -> None:
        """Write what a finished interview leaves: the full transcript and, with `audio`, the
        whole conversation in one audio file. Written again when an answer is revised."""
        ...

    def artifact(self, session_id: str, name: str) -> Path | None:
        """A downloadable file of the session (an export or a turn's audio), if it exists."""
        ...
