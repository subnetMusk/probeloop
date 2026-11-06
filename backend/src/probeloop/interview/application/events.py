"""Events a live session emits towards its client."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from probeloop.interview.domain.model import EndReason, MoveAction, Phase, SessionStatus


@dataclass(frozen=True, slots=True)
class StateChanged:
    status: SessionStatus
    phase: Phase | None
    elapsed_s: float
    remaining_s: float


@dataclass(frozen=True, slots=True)
class UtteranceDelta:
    turn_seq: int
    text: str


@dataclass(frozen=True, slots=True)
class MoveCompleted:
    turn_seq: int
    action: MoveAction
    topic_id: str
    utterance: str
    fallback: bool


@dataclass(frozen=True, slots=True)
class AnswerRecorded:
    turn_seq: int
    text: str


@dataclass(frozen=True, slots=True)
class SessionEnded:
    reason: EndReason | None
    failure: str | None = None


@dataclass(frozen=True, slots=True)
class ErrorRaised:
    code: str
    message: str
    recoverable: bool


type SessionEvent = (
    StateChanged | UtteranceDelta | MoveCompleted | AnswerRecorded | SessionEnded | ErrorRaised
)
type EventSink = Callable[[SessionEvent], Awaitable[None]]
