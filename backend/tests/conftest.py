"""Shared fakes for tests. All data is synthetic."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from probeloop.ai.ports import LlmError
from probeloop.interview.application.events import SessionEvent
from probeloop.interview.application.ports import (
    MoveDelta,
    MoveDone,
    MoveRequest,
    SessionSummary,
)
from probeloop.interview.domain.model import (
    Difficulty,
    InterviewConfig,
    InterviewContext,
    InterviewerMove,
    InterviewSession,
    InterviewType,
    Language,
    Modality,
    MoveAction,
    Speaker,
    Topic,
)
from probeloop.interview.domain.time_policy import TimeDirective
from probeloop.speech.audio import PcmAudio


@dataclass
class FakeClock:
    t: float = 1_000_000.0

    def now(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


@dataclass
class MemoryStore:
    sessions: dict[str, InterviewSession] = field(default_factory=dict)
    saves: int = 0
    audio: dict[tuple[str, int], PcmAudio] = field(default_factory=dict)
    speakers: dict[tuple[str, int], str] = field(default_factory=dict)
    metrics: list[dict[str, object]] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)

    async def save(self, session: InterviewSession) -> None:
        self.saves += 1
        self.sessions[session.id] = session

    async def load(self, session_id: str) -> InterviewSession | None:
        return self.sessions.get(session_id)

    async def summaries(self) -> list[SessionSummary]:
        return [
            SessionSummary(
                s.id,
                s.created_at,
                s.status,
                s.config.interview_type.value,
                s.config.language.value,
                ended_at=s.ended_at,
                execution_profile=s.execution_profile,
                profile_id=s.profile_id,
                difficulty=s.config.difficulty.value,
                target_duration_s=s.config.target_duration_s,
                effective_s=(
                    s.elapsed_s(0)
                    if s.started_at is not None and (s.ended_at or s.paused_at)
                    else None
                ),
                answers=len(s.candidate_turns()),
                snapshot_id=s.snapshot_id,
            )
            for s in sorted(self.sessions.values(), key=lambda s: s.created_at, reverse=True)
        ]

    async def delete(self, session_id: str) -> bool:
        return self.sessions.pop(session_id, None) is not None

    async def save_turn_audio(
        self, session_id: str, turn_seq: int, speaker: Speaker, audio: PcmAudio
    ) -> None:
        self.audio[(session_id, turn_seq)] = audio
        self.speakers[(session_id, turn_seq)] = speaker.value

    async def load_turn_audio(
        self, session_id: str, turn_seq: int, speaker: Speaker
    ) -> PcmAudio | None:
        if self.speakers.get((session_id, turn_seq)) != speaker.value:
            return None
        return self.audio.get((session_id, turn_seq))

    async def export(self, session: InterviewSession, *, audio: bool = True) -> None:
        self.exports.append(session.id)

    async def append_metrics(self, session_id: str, record: Mapping[str, object]) -> None:
        self.metrics.append(dict(record))

    def artifact(self, session_id: str, name: str) -> Path | None:
        return None


@dataclass
class EventRecorder:
    events: list[SessionEvent] = field(default_factory=list)

    async def __call__(self, event: SessionEvent) -> None:
        self.events.append(event)

    def of(self, kind: type) -> list:  # type: ignore[type-arg]
        return [e for e in self.events if isinstance(e, kind)]


type MoveScript = Callable[[MoveRequest], InterviewerMove | Exception]


def default_script(request: MoveRequest) -> InterviewerMove:
    """Asks a numbered question; closes when the time policy says so."""
    n = sum(1 for t in request.turns if t.speaker == "interviewer")
    if request.directive is TimeDirective.CLOSE:
        return InterviewerMove(MoveAction.END, "t1", "Grazie, il colloquio è terminato.")
    if request.directive is TimeDirective.FINAL_QUESTION:
        return InterviewerMove(MoveAction.WRAP_UP, "t3", "Ha qualche domanda per me?")
    return InterviewerMove(MoveAction.FOLLOW_UP, "t1", f"Domanda numero {n + 1}?")


@dataclass
class ScriptedInterviewer:
    script: MoveScript = default_script
    chunk_size: int = 6
    chunk_delay_s: float = 0.0
    requests: list[MoveRequest] = field(default_factory=list)
    prepared: int = 0
    prepare_errors: list[Exception] = field(default_factory=list)  # raised by the next warm-ups
    check_errors: list[Exception] = field(default_factory=list)  # raised by the next checks
    limit_errors: list[Exception] = field(default_factory=list)  # raised by the next reader loads

    async def check(self) -> None:
        if self.check_errors:
            raise self.check_errors.pop(0)

    async def prepare(self, request: MoveRequest) -> None:
        self.prepared += 1
        if self.prepare_errors:
            raise self.prepare_errors.pop(0)

    async def prepare_limits(self) -> None:
        if self.limit_errors:
            raise self.limit_errors.pop(0)

    async def next_move(self, request: MoveRequest) -> AsyncIterator[MoveDelta | MoveDone]:
        self.requests.append(request)
        result = self.script(request)
        if isinstance(result, Exception):
            raise result
        text = result.utterance
        for i in range(0, len(text), self.chunk_size):
            if self.chunk_delay_s:
                await asyncio.sleep(self.chunk_delay_s)
            yield MoveDelta(text[i : i + self.chunk_size], result.action, result.topic_id)
        yield MoveDone(result)


def failing(times: int, then: MoveScript = default_script) -> MoveScript:
    calls = {"n": 0}

    def script(request: MoveRequest) -> InterviewerMove | Exception:
        calls["n"] += 1
        if calls["n"] <= times:
            return LlmError("model unreachable")
        return then(request)

    return script


def make_config(
    minutes: int = 15,
    language: Language = Language.ITALIAN,
    modality: Modality = Modality.TEXT,
) -> InterviewConfig:
    return InterviewConfig(
        interview_type=InterviewType.TECHNICAL,
        difficulty=Difficulty.MEDIUM,
        language=language,
        target_duration_s=minutes * 60,
        modality=modality,
    )


def make_context() -> InterviewContext:
    return InterviewContext(
        candidate_brief="Synthetic candidate: three years of Python backend work.",
        job_brief="Synthetic job: backend developer, Python and PostgreSQL.",
        topics=(Topic("t1", "Introduction"), Topic("t2", "Main project"), Topic("t3", "Closing")),
    )


def make_session(
    minutes: int = 15, session_id: str = "0" * 32, modality: Modality = Modality.TEXT
) -> InterviewSession:
    return InterviewSession(
        id=session_id,
        config=make_config(minutes, modality=modality),
        context=make_context(),
        created_at=0.0,
    )


def move_json(action: str, topic_id: str, utterance: str, covered: list[str] | None = None) -> str:
    return json.dumps(
        {
            "action": action,
            "topic_id": topic_id,
            "utterance": utterance,
            "covered_topic_ids": covered or [],
        }
    )


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore()


@pytest.fixture
def recorder() -> EventRecorder:
    return EventRecorder()
