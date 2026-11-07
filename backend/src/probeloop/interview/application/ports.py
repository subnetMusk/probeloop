"""Ports used by the interview use cases."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from typing import Protocol

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

    async def append_metrics(self, session_id: str, record: Mapping[str, object]) -> None: ...

    async def export(self, session: InterviewSession) -> None:
        """Write what a finished interview leaves: the full transcript and the whole audio."""
        ...
