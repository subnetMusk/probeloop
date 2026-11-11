"""Pydantic schemas of the REST API and of the WebSocket protocol."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from probeloop.context.domain.model import RoleProfile
from probeloop.interview.application.events import (
    AnswerRecorded,
    AnswerTimeWarning,
    ErrorRaised,
    MoveCompleted,
    Preparing,
    SentenceAudio,
    SessionEnded,
    SessionEvent,
    SpeechFinished,
    StateChanged,
    TranscriptPartial,
    UtteranceDelta,
)
from probeloop.interview.application.ports import SessionSummary
from probeloop.interview.domain.model import (
    MAX_CUSTOM_INSTRUCTIONS,
    CandidateTurn,
    Difficulty,
    EndReason,
    InterviewSession,
    InterviewType,
    Language,
    Modality,
    MoveAction,
    Phase,
    SessionStatus,
    TurnIntent,
)
from probeloop.platform.jobs import Job

MAX_BRIEF = 4000
MAX_ANSWER = 8000
MAX_AUDIO_FRAME_BYTES = 64 * 1024  # two seconds of 16 kHz PCM16; the browser sends about 0.1 s


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RoleProfileData(Strict):
    profession: str = Field(max_length=160)
    target_role: str = Field(max_length=160)
    seniority: str = Field(max_length=160)
    responsibilities: list[str] = Field(max_length=12)
    competencies: list[str] = Field(max_length=12)
    basis_fact_ids: list[str] = Field(max_length=24)
    rationale: str = Field(max_length=800)
    confirmed: bool

    @classmethod
    def of(cls, profile: RoleProfile) -> RoleProfileData:
        return cls.model_validate(asdict(profile))

    def domain(self) -> RoleProfile:
        return RoleProfile(
            profession=self.profession.strip(),
            target_role=self.target_role.strip(),
            seniority=self.seniority.strip(),
            responsibilities=tuple(self.responsibilities),
            competencies=tuple(self.competencies),
            basis_fact_ids=tuple(self.basis_fact_ids),
            rationale=self.rationale,
            confirmed=self.confirmed,
        )


# ---------------------------------------------------------------------- REST


class CreateSession(Strict):
    interview_type: InterviewType
    difficulty: Difficulty = Difficulty.MEDIUM
    language: Language = Language.ITALIAN
    modality: Modality = Modality.TEXT
    duration_minutes: int = Field(default=15, ge=5, le=90)
    custom_instructions: str = Field(default="", max_length=MAX_CUSTOM_INSTRUCTIONS)
    candidate_brief: str | None = Field(default=None, max_length=MAX_BRIEF)
    job_brief: str | None = Field(default=None, max_length=MAX_BRIEF)
    # An approved context (from /api/preparations/{id}/approve): the briefs, the topic plan and
    # the vocabulary come from it instead of the sample brief.
    snapshot_id: str | None = Field(default=None, max_length=32)
    # Where the interviewer and the reports run (ADR 0015); None uses the default.
    execution_profile: str | None = Field(default=None, max_length=1024)
    profile_id: str | None = Field(default=None, max_length=32)


class WordView(BaseModel):
    text: str
    start_s: float
    end_s: float
    probability: float | None


class RevisionView(BaseModel):
    number: int
    text: str
    source: str
    created_at: float
    engine_ref: str | None


class TurnView(BaseModel):
    seq: int
    speaker: Literal["interviewer", "candidate"]
    elapsed_s: float
    text: str
    action: str | None = None
    topic_id: str | None = None
    status: str | None = None
    intent: TurnIntent | None = None
    # Answers only: every transcript revision, and the words of the current one when the
    # recogniser reported them (with their probability, to highlight doubtful words).
    revisions: list[RevisionView]
    words: list[WordView]
    audio: str | None  # URL of the turn's audio, when it was kept


class EditAnswer(Strict):
    text: str = Field(max_length=MAX_ANSWER)


class JobView(BaseModel):
    id: str
    kind: str
    subject_id: str
    status: str
    progress: float
    message: str | None
    error: str | None
    result: dict[str, Any] | None
    created_at: float
    started_at: float | None
    finished_at: float | None

    @classmethod
    def of(cls, job: Job) -> JobView:
        return cls(
            id=job.id,
            kind=job.kind,
            subject_id=job.subject_id,
            status=job.status.value,
            progress=round(job.progress, 3),
            message=job.message,
            error=job.error,
            result=dict(job.result) if job.result is not None else None,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )


class TopicView(BaseModel):
    id: str
    title: str
    objective: str = ""
    rubric_kind: str | None = None
    priority: int = 1
    fact_ids: list[str] = []
    criteria: list[str] = []
    past_example: bool = False
    solvable: bool = False


class SessionView(BaseModel):
    id: str
    status: str
    phase: str | None
    interview_type: str
    difficulty: str
    language: str
    modality: str
    target_duration_s: int
    created_at: float
    end_reason: str | None
    failure: str | None
    topics: list[TopicView]
    coverage: dict[str, str]
    turns: list[TurnView]
    snapshot_id: str | None
    execution_profile: str | None
    profile_id: str | None
    role_profile: RoleProfileData | None = None
    policy_version: str | None = None

    @classmethod
    def of(
        cls, s: InterviewSession, audio: Callable[[int, str], str | None] = lambda _s, _p: None
    ) -> SessionView:
        """`audio(seq, speaker)` gives the URL of a turn's audio, if it was kept."""
        turns = []
        for t in s.turns:
            if isinstance(t, CandidateTurn):
                turns.append(
                    TurnView(
                        seq=t.seq,
                        speaker="candidate",
                        elapsed_s=t.elapsed_s,
                        text=t.text,
                        revisions=[
                            RevisionView(
                                number=r.number,
                                text=r.text,
                                source=r.source.value,
                                created_at=r.created_at,
                                engine_ref=r.engine_ref,
                            )
                            for r in t.revisions
                        ],
                        words=[
                            WordView(
                                text=w.text,
                                start_s=w.start_s,
                                end_s=w.end_s,
                                probability=w.probability,
                            )
                            for w in t.current.words
                        ],
                        audio=audio(t.seq, "candidate"),
                    )
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
                        intent=t.move.intent,
                        revisions=[],
                        words=[],
                        audio=audio(t.seq, "interviewer"),
                    )
                )
        return cls(
            id=s.id,
            role_profile=RoleProfileData.of(s.context.role_profile)
            if s.context.role_profile
            else None,
            status=s.status.value,
            phase=s.phase.value if s.phase else None,
            interview_type=s.config.interview_type.value,
            difficulty=s.config.difficulty.value,
            language=s.config.language.value,
            modality=s.config.modality.value,
            target_duration_s=s.config.target_duration_s,
            created_at=s.created_at,
            end_reason=s.end_reason.value if s.end_reason else None,
            failure=s.failure,
            topics=[TopicView.model_validate(asdict(t)) for t in s.context.topics],
            policy_version=s.context.policy_version,
            coverage={k: v.value for k, v in s.coverage.items()},
            turns=turns,
            snapshot_id=s.snapshot_id,
            execution_profile=s.execution_profile,
            profile_id=s.profile_id,
        )


class SpeechStatusView(BaseModel):
    ready: bool  # voice interviews can start now
    problems: list[str]  # why not, for the user
    voices: dict[str, str | None]  # language -> configured voice


class SessionSummaryView(BaseModel):
    id: str
    created_at: float
    status: str
    interview_type: str
    difficulty: str
    language: str
    target_duration_s: int
    effective_s: float | None  # interview time without pauses, once it stopped
    answers: int
    ended_at: float | None
    execution_profile: str | None
    profile_id: str | None
    snapshot_id: str | None

    @classmethod
    def of(cls, s: SessionSummary) -> SessionSummaryView:
        return cls(
            id=s.id,
            created_at=s.created_at,
            status=s.status.value,
            interview_type=s.interview_type,
            difficulty=s.difficulty,
            language=s.language,
            target_duration_s=s.target_duration_s,
            effective_s=round(s.effective_s, 1) if s.effective_s is not None else None,
            answers=s.answers,
            ended_at=s.ended_at,
            execution_profile=s.execution_profile,
            profile_id=s.profile_id,
            snapshot_id=s.snapshot_id,
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
    """End of answer. Text sessions send the typed answer; voice sessions send no text."""

    type: Literal["turn.end"]
    text: str | None = Field(default=None, max_length=MAX_ANSWER)


IncomingMessage = Annotated[JoinMessage | SimpleCommand | TurnEnd, Field(discriminator="type")]
incoming_adapter: TypeAdapter[JoinMessage | SimpleCommand | TurnEnd] = TypeAdapter(IncomingMessage)


# ---------------------------------------------------------------------- WebSocket: server -> client
#
# Binary frames from the client are 16 kHz mono PCM16 answer audio. The only binary frames the
# server sends follow a `tts.chunk` message: they carry that sentence's PCM16 audio at the
# `sample_rate` the message states.


class ServerMessage(BaseModel):
    # Fields with defaults are always present in the output, so the generated types make them
    # required.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    seq: int | None  # None: delivered live only, never replayed after a reconnection


class StateChangedMessage(ServerMessage):
    type: Literal["state.changed"] = "state.changed"
    status: SessionStatus
    phase: Phase | None
    elapsed_s: float
    remaining_s: float


class PreparationStepView(BaseModel):
    name: Literal["language_model", "speech_recognition", "speech_synthesis"]
    state: Literal["loading", "ready", "failed"]
    detail: str | None


class PreparingMessage(ServerMessage):
    type: Literal["session.preparing"] = "session.preparing"
    progress: float  # share of the steps that are ready, from 0 to 1
    steps: list[PreparationStepView]


class TextDeltaMessage(ServerMessage):
    type: Literal["interviewer.text.delta"] = "interviewer.text.delta"
    turn_seq: int
    text: str


class MoveCompletedMessage(ServerMessage):
    type: Literal["interviewer.move.completed"] = "interviewer.move.completed"
    turn_seq: int
    action: MoveAction
    topic_id: str
    utterance: str
    fallback: bool


class TtsChunkMessage(ServerMessage):
    """Followed by one binary frame: `samples` PCM16 samples at `sample_rate`."""

    type: Literal["tts.chunk"] = "tts.chunk"
    turn_seq: int
    index: int
    text: str
    sample_rate: int
    samples: int
    duration_s: float


class TtsDoneMessage(ServerMessage):
    type: Literal["tts.done"] = "tts.done"
    turn_seq: int
    sentences: int
    failed: int


class TranscriptPartialMessage(ServerMessage):
    type: Literal["transcript.partial"] = "transcript.partial"
    turn_seq: int
    text: str


class AnswerTimeWarningMessage(ServerMessage):
    type: Literal["answer.time_warning"] = "answer.time_warning"
    turn_seq: int
    remaining_s: float


class AnswerRecordedMessage(ServerMessage):
    type: Literal["candidate.answer.recorded"] = "candidate.answer.recorded"
    turn_seq: int
    text: str
    complete: bool


class SessionEndedMessage(ServerMessage):
    type: Literal["session.ended"] = "session.ended"
    reason: EndReason | None
    failure: str | None


class ErrorMessage(ServerMessage):
    type: Literal["error"] = "error"
    code: str
    message: str
    recoverable: bool


class PongMessage(ServerMessage):
    type: Literal["pong"] = "pong"


OutgoingMessage = Annotated[
    StateChangedMessage
    | PreparingMessage
    | TextDeltaMessage
    | MoveCompletedMessage
    | TtsChunkMessage
    | TtsDoneMessage
    | TranscriptPartialMessage
    | AnswerTimeWarningMessage
    | AnswerRecordedMessage
    | SessionEndedMessage
    | ErrorMessage
    | PongMessage,
    Field(discriminator="type"),
]


def event_frames(seq: int | None, event: SessionEvent) -> list[dict[str, Any] | bytes]:
    """The WebSocket frames of one event: a JSON message, plus the audio of a `tts.chunk`."""
    message = event_message(seq, event)
    if isinstance(event, SentenceAudio):
        return [message, event.audio.data]
    return [message]


def event_message(seq: int | None, event: SessionEvent) -> dict[str, Any]:
    return _message(seq, event).model_dump(mode="json")


def _message(seq: int | None, event: SessionEvent) -> ServerMessage:
    match event:
        case StateChanged():
            return StateChangedMessage(
                seq=seq,
                status=event.status,
                phase=event.phase,
                elapsed_s=event.elapsed_s,
                remaining_s=event.remaining_s,
            )
        case Preparing():
            return PreparingMessage(
                seq=seq,
                progress=round(event.progress, 3),
                steps=[
                    PreparationStepView(name=s.name, state=s.state, detail=s.detail)
                    for s in event.steps
                ],
            )
        case UtteranceDelta():
            return TextDeltaMessage(seq=seq, turn_seq=event.turn_seq, text=event.text)
        case MoveCompleted():
            return MoveCompletedMessage(
                seq=seq,
                turn_seq=event.turn_seq,
                action=event.action,
                topic_id=event.topic_id,
                utterance=event.utterance,
                fallback=event.fallback,
            )
        case SentenceAudio():
            return TtsChunkMessage(
                seq=seq,
                turn_seq=event.turn_seq,
                index=event.index,
                text=event.text,
                sample_rate=event.audio.sample_rate,
                samples=event.audio.samples,
                duration_s=round(event.audio.duration_s, 3),
            )
        case SpeechFinished():
            return TtsDoneMessage(
                seq=seq, turn_seq=event.turn_seq, sentences=event.sentences, failed=event.failed
            )
        case TranscriptPartial():
            return TranscriptPartialMessage(seq=seq, turn_seq=event.turn_seq, text=event.text)
        case AnswerTimeWarning():
            return AnswerTimeWarningMessage(
                seq=seq, turn_seq=event.turn_seq, remaining_s=event.remaining_s
            )
        case AnswerRecorded():
            return AnswerRecordedMessage(
                seq=seq, turn_seq=event.turn_seq, text=event.text, complete=event.complete
            )
        case SessionEnded():
            return SessionEndedMessage(seq=seq, reason=event.reason, failure=event.failure)
        case ErrorRaised():
            return ErrorMessage(
                seq=seq, code=event.code, message=event.message, recoverable=event.recoverable
            )


def error_message(code: str, message: str, *, recoverable: bool = True) -> dict[str, Any]:
    """An error tied to one client message; not part of the replayable event stream."""
    return ErrorMessage(seq=None, code=code, message=message, recoverable=recoverable).model_dump(
        mode="json"
    )


def pong_message() -> dict[str, Any]:
    return PongMessage(seq=None).model_dump(mode="json")
