"""Interview session aggregate, its value objects and its state machine."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from enum import StrEnum

MAX_CUSTOM_INSTRUCTIONS = 1000
MIN_DURATION_S = 5 * 60
MAX_DURATION_S = 90 * 60


class InvalidTransitionError(Exception):
    """Raised when an operation is not allowed in the session's current state."""


class InvalidConfigError(ValueError):
    """Raised when an interview configuration or context violates a domain rule."""


class InterviewType(StrEnum):
    HR = "hr"
    BEHAVIORAL = "behavioral"
    TECHNICAL = "technical"
    MIXED = "mixed"


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Language(StrEnum):
    ITALIAN = "it"
    ENGLISH = "en"


class Modality(StrEnum):
    TEXT = "text"  # typed answers, no audio (the development CLI)
    VOICE = "voice"  # spoken questions and answers


@dataclass(frozen=True, slots=True)
class InterviewConfig:
    interview_type: InterviewType
    difficulty: Difficulty
    language: Language
    target_duration_s: int
    custom_instructions: str = ""
    modality: Modality = Modality.TEXT

    def __post_init__(self) -> None:
        if not MIN_DURATION_S <= self.target_duration_s <= MAX_DURATION_S:
            raise InvalidConfigError(
                f"target duration must be between {MIN_DURATION_S} and {MAX_DURATION_S} seconds"
            )
        if len(self.custom_instructions) > MAX_CUSTOM_INSTRUCTIONS:
            raise InvalidConfigError(
                f"custom instructions exceed {MAX_CUSTOM_INSTRUCTIONS} characters"
            )


@dataclass(frozen=True, slots=True)
class Topic:
    id: str
    title: str


@dataclass(frozen=True, slots=True)
class InterviewContext:
    """What the interviewer knows before the interview starts."""

    candidate_brief: str
    job_brief: str
    topics: tuple[Topic, ...]

    def __post_init__(self) -> None:
        if not self.topics:
            raise InvalidConfigError("an interview needs at least one topic")
        ids = [t.id for t in self.topics]
        if len(set(ids)) != len(ids):
            raise InvalidConfigError("topic ids must be unique")

    def has_topic(self, topic_id: str) -> bool:
        return any(t.id == topic_id for t in self.topics)


class MoveAction(StrEnum):
    FOLLOW_UP = "follow_up"
    CLARIFY = "clarify"
    NEW_TOPIC = "new_topic"
    PRESENT_EXERCISE = "present_exercise"
    WRAP_UP = "wrap_up"
    END = "end"


class MoveStatus(StrEnum):
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True, slots=True)
class InterviewerMove:
    action: MoveAction
    topic_id: str
    utterance: str
    covered_topic_ids: tuple[str, ...] = ()
    status: MoveStatus = MoveStatus.COMPLETED
    fallback: bool = False
    model_ref: str | None = None
    prompt_ref: str | None = None


class Speaker(StrEnum):
    INTERVIEWER = "interviewer"
    CANDIDATE = "candidate"


@dataclass(frozen=True, slots=True)
class InterviewerTurn:
    seq: int
    at: float
    elapsed_s: float
    move: InterviewerMove
    speaker: Speaker = Speaker.INTERVIEWER


class RevisionSource(StrEnum):
    STT = "stt"  # the live transcript, or the typed answer of a text interview
    RETRANSCRIPTION = "retranscription"  # a later pass over the stored audio
    USER_EDIT = "user_edit"


@dataclass(frozen=True, slots=True)
class TranscriptWord:
    text: str
    start_s: float
    end_s: float
    probability: float | None = None


@dataclass(frozen=True, slots=True)
class TranscriptRevision:
    number: int
    text: str
    source: RevisionSource
    created_at: float
    engine_ref: str | None = None
    words: tuple[TranscriptWord, ...] = ()


@dataclass(frozen=True, slots=True)
class CandidateTurn:
    """An answer. Its text is the latest revision; earlier ones are kept for provenance."""

    seq: int
    at: float
    elapsed_s: float
    revisions: tuple[TranscriptRevision, ...]
    speaker: Speaker = Speaker.CANDIDATE

    def __post_init__(self) -> None:
        if not self.revisions:
            raise InvalidConfigError("an answer needs at least one transcript revision")
        if [r.number for r in self.revisions] != list(range(1, len(self.revisions) + 1)):
            raise InvalidConfigError("transcript revisions must be numbered from 1")

    @property
    def text(self) -> str:
        return self.revisions[-1].text

    @property
    def current(self) -> TranscriptRevision:
        return self.revisions[-1]

    def revised(
        self,
        text: str,
        source: RevisionSource,
        now: float,
        *,
        engine_ref: str | None = None,
        words: tuple[TranscriptWord, ...] = (),
    ) -> CandidateTurn:
        revision = TranscriptRevision(
            number=len(self.revisions) + 1,
            text=" ".join(text.split()),
            source=source,
            created_at=now,
            engine_ref=engine_ref,
            words=words,
        )
        return replace(self, revisions=(*self.revisions, revision))


type Turn = InterviewerTurn | CandidateTurn


class SessionStatus(StrEnum):
    READY = "ready"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    ENDED = "ended"
    FAILED = "failed"


class Phase(StrEnum):
    INTERVIEWER_THINKING = "interviewer_thinking"
    INTERVIEWER_SPEAKING = "interviewer_speaking"
    AWAITING_CANDIDATE = "awaiting_candidate"
    CANDIDATE_SPEAKING = "candidate_speaking"
    FINALIZING_TRANSCRIPT = "finalizing_transcript"


class EndReason(StrEnum):
    COMPLETED = "completed"
    TIME_LIMIT = "time_limit"
    USER_ENDED = "user_ended"


class TopicCoverage(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COVERED = "covered"


# Phase a paused session returns to. THINKING is resolved at resume time (see `resume`).
_RESUME_PHASE = {
    Phase.INTERVIEWER_SPEAKING: Phase.AWAITING_CANDIDATE,
    Phase.AWAITING_CANDIDATE: Phase.AWAITING_CANDIDATE,
    Phase.CANDIDATE_SPEAKING: Phase.AWAITING_CANDIDATE,
    Phase.FINALIZING_TRANSCRIPT: Phase.FINALIZING_TRANSCRIPT,
}


@dataclass
class InterviewSession:
    """Aggregate root. All state changes go through the methods below."""

    id: str
    config: InterviewConfig
    context: InterviewContext
    created_at: float
    status: SessionStatus = SessionStatus.READY
    phase: Phase | None = None
    turns: list[Turn] = field(default_factory=list)
    coverage: dict[str, TopicCoverage] = field(default_factory=dict)
    started_at: float | None = None
    ended_at: float | None = None
    end_reason: EndReason | None = None
    failure: str | None = None
    paused_at: float | None = None
    paused_total_s: float = 0.0
    paused_phase: Phase | None = None
    final_question_asked: bool = False

    def __post_init__(self) -> None:
        for topic in self.context.topics:
            self.coverage.setdefault(topic.id, TopicCoverage.NOT_STARTED)

    # ------------------------------------------------------------------ queries

    def elapsed_s(self, now: float) -> float:
        """Effective interview time, excluding pauses."""
        if self.started_at is None:
            return 0.0
        end = self.ended_at or self.paused_at or now
        return max(0.0, end - self.started_at - self.paused_total_s)

    @property
    def is_terminal(self) -> bool:
        return self.status in (SessionStatus.ENDED, SessionStatus.FAILED)

    def interviewer_turns(self) -> list[InterviewerTurn]:
        return [t for t in self.turns if isinstance(t, InterviewerTurn)]

    def questions_asked(self) -> list[str]:
        return [t.move.utterance for t in self.interviewer_turns() if t.move.utterance]

    def current_topic_id(self) -> str:
        moves = self.interviewer_turns()
        return moves[-1].move.topic_id if moves else self.context.topics[0].id

    def last_move(self) -> InterviewerMove | None:
        moves = self.interviewer_turns()
        return moves[-1].move if moves else None

    # ------------------------------------------------------------------ transitions

    def start(self, now: float) -> None:
        self._require_status(SessionStatus.READY)
        self.status = SessionStatus.IN_PROGRESS
        self.phase = Phase.INTERVIEWER_THINKING
        self.started_at = now

    def record_move(
        self, move: InterviewerMove, now: float, *, final_question: bool = False
    ) -> None:
        self._require_phase(Phase.INTERVIEWER_THINKING)
        self._append_move(move, now)
        if final_question:
            self.final_question_asked = True
        self.phase = Phase.INTERVIEWER_SPEAKING

    def finish_speaking(self, now: float) -> None:
        self._require_phase(Phase.INTERVIEWER_SPEAKING)
        last = self.last_move()
        if last is not None and last.action is MoveAction.END:
            self._close(EndReason.COMPLETED, now)
        else:
            self.phase = Phase.AWAITING_CANDIDATE

    def start_answer(self, now: float) -> None:
        self._require_phase(Phase.AWAITING_CANDIDATE)
        self.phase = Phase.CANDIDATE_SPEAKING

    def finish_answer(self, now: float) -> None:
        self._require_phase(Phase.CANDIDATE_SPEAKING)
        self.phase = Phase.FINALIZING_TRANSCRIPT

    def record_answer(
        self,
        text: str,
        now: float,
        *,
        engine_ref: str | None = None,
        words: tuple[TranscriptWord, ...] = (),
    ) -> None:
        self._require_phase(Phase.FINALIZING_TRANSCRIPT)
        revision = TranscriptRevision(
            number=1,
            text=text.strip(),
            source=RevisionSource.STT,
            created_at=now,
            engine_ref=engine_ref,
            words=words,
        )
        self.turns.append(
            CandidateTurn(
                seq=len(self.turns), at=now, elapsed_s=self.elapsed_s(now), revisions=(revision,)
            )
        )
        self.phase = Phase.INTERVIEWER_THINKING

    def revise_answer(
        self,
        seq: int,
        text: str,
        source: RevisionSource,
        now: float,
        *,
        engine_ref: str | None = None,
        words: tuple[TranscriptWord, ...] = (),
    ) -> CandidateTurn:
        """Add a transcript revision to an answer of a finished interview."""
        if not self.is_terminal:
            raise InvalidTransitionError("answers can be revised only after the interview")
        if source is RevisionSource.STT:
            raise InvalidConfigError("the live transcript is always the first revision")
        if not 0 <= seq < len(self.turns) or not isinstance(self.turns[seq], CandidateTurn):
            raise InvalidConfigError(f"turn {seq} is not an answer")
        turn = self.turns[seq]
        assert isinstance(turn, CandidateTurn)
        revised = turn.revised(text, source, now, engine_ref=engine_ref, words=words)
        self.turns[seq] = revised
        return revised

    def candidate_turns(self) -> list[CandidateTurn]:
        return [t for t in self.turns if isinstance(t, CandidateTurn)]

    def pause(self, now: float, *, partial_move: InterviewerMove | None = None) -> None:
        """Pause the interview. A move cut short while it was being generated may be kept."""
        self._require_status(SessionStatus.IN_PROGRESS)
        assert self.phase is not None
        paused_phase = self.phase
        if self.phase is Phase.INTERVIEWER_THINKING and _has_utterance(partial_move):
            assert partial_move is not None
            self._append_move(partial_move, now)
            paused_phase = Phase.INTERVIEWER_SPEAKING
        self.status = SessionStatus.PAUSED
        self.paused_at = now
        self.paused_phase = paused_phase

    def resume(self, now: float) -> None:
        self._require_status(SessionStatus.PAUSED)
        assert self.paused_at is not None
        assert self.paused_phase is not None
        self.paused_total_s += now - self.paused_at
        self.paused_at = None
        self.status = SessionStatus.IN_PROGRESS
        if self.paused_phase is Phase.INTERVIEWER_THINKING:
            self.phase = Phase.INTERVIEWER_THINKING  # the interrupted move is generated again
        else:
            self.phase = _RESUME_PHASE[self.paused_phase]
        self.paused_phase = None

    def end(
        self, reason: EndReason, now: float, *, partial_move: InterviewerMove | None = None
    ) -> None:
        if self.status not in (SessionStatus.IN_PROGRESS, SessionStatus.PAUSED):
            raise InvalidTransitionError(f"cannot end a session in status {self.status}")
        if self.phase is Phase.INTERVIEWER_THINKING and _has_utterance(partial_move):
            assert partial_move is not None
            self._append_move(partial_move, now)
        self._close(reason, now)

    def fail(self, message: str, now: float) -> None:
        if self.is_terminal:
            raise InvalidTransitionError(f"cannot fail a session in status {self.status}")
        if self.status is SessionStatus.PAUSED and self.paused_at is not None:
            self.paused_total_s += now - self.paused_at
            self.paused_at = None
        self.status = SessionStatus.FAILED
        self.failure = message
        self.phase = None
        self.ended_at = now

    # ------------------------------------------------------------------ internals

    def _append_move(self, move: InterviewerMove, now: float) -> None:
        if not self.context.has_topic(move.topic_id):
            raise InvalidConfigError(f"unknown topic {move.topic_id!r}")
        self.turns.append(
            InterviewerTurn(seq=len(self.turns), at=now, elapsed_s=self.elapsed_s(now), move=move)
        )
        if self.coverage[move.topic_id] is TopicCoverage.NOT_STARTED:
            self.coverage[move.topic_id] = TopicCoverage.IN_PROGRESS
        for topic_id in _known(move.covered_topic_ids, self.coverage):
            self.coverage[topic_id] = TopicCoverage.COVERED

    def _close(self, reason: EndReason, now: float) -> None:
        if self.status is SessionStatus.PAUSED and self.paused_at is not None:
            self.paused_total_s += now - self.paused_at
            self.paused_at = None
        self.status = SessionStatus.ENDED
        self.phase = None
        self.paused_phase = None
        self.end_reason = reason
        self.ended_at = now

    def _require_status(self, expected: SessionStatus) -> None:
        if self.status is not expected:
            raise InvalidTransitionError(f"expected status {expected}, got {self.status}")

    def _require_phase(self, expected: Phase) -> None:
        self._require_status(SessionStatus.IN_PROGRESS)
        if self.phase is not expected:
            raise InvalidTransitionError(f"expected phase {expected}, got {self.phase}")


def _has_utterance(move: InterviewerMove | None) -> bool:
    return move is not None and bool(move.utterance.strip())


def _known(topic_ids: Iterable[str], coverage: dict[str, TopicCoverage]) -> list[str]:
    return [t for t in topic_ids if t in coverage]
