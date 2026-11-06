"""Pydantic schemas of the REST API and of the WebSocket protocol."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from probeloop.interview.application.events import (
    AnswerRecorded,
    ErrorRaised,
    MoveCompleted,
    SessionEnded,
    SessionEvent,
    StateChanged,
    UtteranceDelta,
)
from probeloop.interview.application.ports import SessionSummary
from probeloop.interview.domain.model import (
    MAX_CUSTOM_INSTRUCTIONS,
    CandidateTurn,
    Difficulty,
    InterviewSession,
    InterviewType,
    Language,
)

MAX_BRIEF = 4000
MAX_ANSWER = 8000


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------- REST


class CreateSession(Strict):
    interview_type: InterviewType
    difficulty: Difficulty = Difficulty.MEDIUM
    language: Language = Language.ITALIAN
    duration_minutes: int = Field(default=15, ge=5, le=90)
    custom_instructions: str = Field(default="", max_length=MAX_CUSTOM_INSTRUCTIONS)
    candidate_brief: str | None = Field(default=None, max_length=MAX_BRIEF)
    job_brief: str | None = Field(default=None, max_length=MAX_BRIEF)


class TurnView(BaseModel):
    seq: int
    speaker: Literal["interviewer", "candidate"]
    elapsed_s: float
    text: str
    action: str | None = None
    topic_id: str | None = None
    status: str | None = None


class SessionView(BaseModel):
    id: str
    status: str
    phase: str | None
    interview_type: str
    difficulty: str
    language: str
    target_duration_s: int
    created_at: float
    end_reason: str | None
    failure: str | None
    topics: list[dict[str, str]]
    coverage: dict[str, str]
    turns: list[TurnView]

    @classmethod
    def of(cls, s: InterviewSession) -> SessionView:
        turns = []
        for t in s.turns:
            if isinstance(t, CandidateTurn):
                turns.append(
                    TurnView(seq=t.seq, speaker="candidate", elapsed_s=t.elapsed_s, text=t.text)
                )
            else:
                turns.append(
                    TurnView(
                        seq=t.seq,
                        speaker="interviewer",
                        elapsed_s=t.elapsed_s,
                        text=t.move.utterance,
                        action=t.move.action.value,
                        topic_id=t.move.topic_id,
                        status=t.move.status.value,
                    )
                )
        return cls(
            id=s.id,
            status=s.status.value,
            phase=s.phase.value if s.phase else None,
            interview_type=s.config.interview_type.value,
            difficulty=s.config.difficulty.value,
            language=s.config.language.value,
            target_duration_s=s.config.target_duration_s,
            created_at=s.created_at,
            end_reason=s.end_reason.value if s.end_reason else None,
            failure=s.failure,
            topics=[{"id": t.id, "title": t.title} for t in s.context.topics],
            coverage={k: v.value for k, v in s.coverage.items()},
            turns=turns,
        )


class SessionSummaryView(BaseModel):
    id: str
    created_at: float
    status: str
    interview_type: str
    language: str

    @classmethod
    def of(cls, s: SessionSummary) -> SessionSummaryView:
        return cls(
            id=s.id,
            created_at=s.created_at,
            status=s.status.value,
            interview_type=s.interview_type,
            language=s.language,
        )


# ---------------------------------------------------------------------- WebSocket: client -> server


class ClientMessage(Strict):
    client_msg_id: str | None = Field(default=None, max_length=64)


class JoinMessage(ClientMessage):
    type: Literal["session.join"]
    last_seq: int = Field(default=0, ge=0)


class SimpleCommand(ClientMessage):
    type: Literal[
        "session.start",
        "session.pause",
        "session.resume",
        "session.end",
        "playback.finished",
        "turn.start",
        "ping",
    ]


class TurnEnd(ClientMessage):
    type: Literal["turn.end"]
    text: str = Field(max_length=MAX_ANSWER)


IncomingMessage = Annotated[JoinMessage | SimpleCommand | TurnEnd, Field(discriminator="type")]
incoming_adapter: TypeAdapter[JoinMessage | SimpleCommand | TurnEnd] = TypeAdapter(IncomingMessage)


# ---------------------------------------------------------------------- WebSocket: server -> client


def event_message(seq: int, event: SessionEvent) -> dict[str, Any]:
    body: dict[str, Any]
    match event:
        case StateChanged():
            body = {
                "type": "state.changed",
                "status": event.status.value,
                "phase": event.phase.value if event.phase else None,
                "elapsed_s": event.elapsed_s,
                "remaining_s": event.remaining_s,
            }
        case UtteranceDelta():
            body = {
                "type": "interviewer.text.delta",
                "turn_seq": event.turn_seq,
                "text": event.text,
            }
        case MoveCompleted():
            body = {
                "type": "interviewer.move.completed",
                "turn_seq": event.turn_seq,
                "action": event.action.value,
                "topic_id": event.topic_id,
                "utterance": event.utterance,
                "fallback": event.fallback,
            }
        case AnswerRecorded():
            body = {
                "type": "candidate.answer.recorded",
                "turn_seq": event.turn_seq,
                "text": event.text,
            }
        case SessionEnded():
            body = {
                "type": "session.ended",
                "reason": event.reason.value if event.reason else None,
                "failure": event.failure,
            }
        case ErrorRaised():
            body = {
                "type": "error",
                "code": event.code,
                "message": event.message,
                "recoverable": event.recoverable,
            }
    return {"seq": seq, **body}


def error_message(code: str, message: str, *, recoverable: bool = True) -> dict[str, Any]:
    """An error tied to one client message; not part of the replayable event stream."""
    return {
        "seq": None,
        "type": "error",
        "code": code,
        "message": message,
        "recoverable": recoverable,
    }
