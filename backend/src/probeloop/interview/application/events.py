"""Events a live session emits towards its client."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from probeloop.interview.domain.model import EndReason, MoveAction, Phase, SessionStatus
from probeloop.speech.audio import PcmAudio


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
class SentenceAudio:
    """One synthesised sentence of the interviewer's utterance, at the voice's sample rate.

    Audio is delivered live only: it is not kept for replay after a reconnection.
    """

    turn_seq: int
    index: int
    text: str
    audio: PcmAudio


@dataclass(frozen=True, slots=True)
class SpeechFinished:
    """No more audio will follow for this utterance."""

    turn_seq: int
    sentences: int
    failed: int


@dataclass(frozen=True, slots=True)
class TranscriptPartial:
    """The answer recognised so far, while the candidate is still speaking."""

    turn_seq: int
    text: str


@dataclass(frozen=True, slots=True)
class AnswerTimeWarning:
    turn_seq: int
    remaining_s: float


@dataclass(frozen=True, slots=True)
class AnswerRecorded:
    turn_seq: int
    text: str
    complete: bool = True  # False when part of a spoken answer could not be transcribed


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
    StateChanged
    | UtteranceDelta
    | MoveCompleted
    | SentenceAudio
    | SpeechFinished
    | TranscriptPartial
    | AnswerTimeWarning
    | AnswerRecorded
    | SessionEnded
    | ErrorRaised
)
type EventSink = Callable[[SessionEvent], Awaitable[None]]
