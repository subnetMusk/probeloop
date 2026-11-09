"""Session store on the database, with the audio and exports in the session's directory."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from probeloop.interview.application.ports import SessionSummary
from probeloop.interview.domain.model import (
    CandidateTurn,
    Difficulty,
    EndReason,
    InterviewConfig,
    InterviewContext,
    InterviewerMove,
    InterviewerTurn,
    InterviewSession,
    InterviewType,
    Language,
    Modality,
    MoveAction,
    MoveStatus,
    Phase,
    RevisionSource,
    SessionStatus,
    Speaker,
    Topic,
    TopicCoverage,
    TranscriptRevision,
    TranscriptWord,
    Turn,
)
from probeloop.speech.audio import PcmAudio
from probeloop.storage.database import (
    JobRow,
    RevisionRow,
    SessionRow,
    TurnMetricsRow,
    TurnRow,
)
from probeloop.storage.session_files import SessionFiles
from probeloop.storage.sql_context import fact_from_json, fact_to_json, role_from_json


class SqlSessionStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], files: SessionFiles) -> None:
        self._sessions = sessions
        self._files = files
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    @property
    def files(self) -> SessionFiles:
        return self._files

    async def save(self, session: InterviewSession) -> None:
        """Insert or update the session. Turns and revisions are append-only: only the new ones
        are written.

        A save is not interrupted when its caller is cancelled (a move cancelled by a pause):
        it finishes in the background, and saves of the same session run one at a time.
        """
        await asyncio.shield(self._save_in_turn(session))

    async def _save_in_turn(self, session: InterviewSession) -> None:
        async with self._locks[session.id]:
            await self._save(session)

    async def _save(self, session: InterviewSession) -> None:
        async with self._sessions.begin() as db:
            row = await db.get(SessionRow, session.id, options=[_WITH_TURNS])
            if row is None:
                row = SessionRow(id=session.id)
                db.add(row)
            _fill_session(row, session)
            stored = {t.seq: t for t in row.turns}
            for turn in session.turns:
                turn_row = stored.get(turn.seq)
                if turn_row is None:
                    turn_row = _turn_row(session.id, turn)
                    row.turns.append(turn_row)
                if isinstance(turn, CandidateTurn):
                    numbers = {r.number for r in turn_row.revisions}
                    turn_row.revisions.extend(
                        _revision_row(session.id, turn.seq, r)
                        for r in turn.revisions
                        if r.number not in numbers
                    )

    async def load(self, session_id: str) -> InterviewSession | None:
        async with self._sessions() as db:
            row = await db.get(SessionRow, session_id, options=[_WITH_TURNS])
            return None if row is None else _session(row)

    async def summaries(self) -> list[SessionSummary]:
        answers = (
            select(func.count())
            .where(TurnRow.session_id == SessionRow.id, TurnRow.speaker == Speaker.CANDIDATE.value)
            .correlate(SessionRow)
            .scalar_subquery()
        )
        query = select(
            SessionRow.id,
            SessionRow.created_at,
            SessionRow.status,
            SessionRow.interview_type,
            SessionRow.difficulty,
            SessionRow.language,
            SessionRow.target_duration_s,
            SessionRow.started_at,
            SessionRow.ended_at,
            SessionRow.paused_at,
            SessionRow.paused_total_s,
            SessionRow.execution_profile,
            SessionRow.profile_id,
            SessionRow.snapshot_id,
            answers.label("answers"),
        ).order_by(SessionRow.created_at.desc())
        async with self._sessions() as db:
            rows = (await db.execute(query)).all()
        return [
            SessionSummary(
                id=r.id,
                created_at=r.created_at,
                status=SessionStatus(r.status),
                interview_type=r.interview_type,
                language=r.language,
                ended_at=r.ended_at,
                execution_profile=r.execution_profile,
                profile_id=r.profile_id,
                difficulty=r.difficulty,
                target_duration_s=r.target_duration_s,
                effective_s=_effective_s(r.started_at, r.ended_at or r.paused_at, r.paused_total_s),
                answers=r.answers,
                snapshot_id=r.snapshot_id,
            )
            for r in rows
        ]

    async def delete(self, session_id: str) -> bool:
        async with self._sessions.begin() as db:
            row = await db.get(SessionRow, session_id)
            if row is None:
                return False
            await db.delete(row)
            await db.execute(delete(JobRow).where(JobRow.subject_id == session_id))
        await asyncio.to_thread(self._files.remove, session_id)
        return True

    async def save_turn_audio(
        self, session_id: str, turn_seq: int, speaker: Speaker, audio: PcmAudio
    ) -> None:
        await asyncio.to_thread(self._files.write_turn_audio, session_id, turn_seq, speaker, audio)

    async def load_turn_audio(
        self, session_id: str, turn_seq: int, speaker: Speaker
    ) -> PcmAudio | None:
        return await asyncio.to_thread(self._files.read_turn_audio, session_id, turn_seq, speaker)

    async def append_metrics(self, session_id: str, record: Mapping[str, object]) -> None:
        async with self._sessions.begin() as db:
            db.add(TurnMetricsRow(session_id=session_id, record=dict(record)))

    async def metrics(self, session_id: str) -> list[dict[str, Any]]:
        query = (
            select(TurnMetricsRow.record)
            .where(TurnMetricsRow.session_id == session_id)
            .order_by(TurnMetricsRow.id)
        )
        async with self._sessions() as db:
            return [dict(r) for r in (await db.scalars(query)).all()]

    async def export(self, session: InterviewSession, *, audio: bool = True) -> None:
        await asyncio.to_thread(self._files.export, session, audio=audio)

    def artifact(self, session_id: str, name: str) -> Path | None:
        return self._files.artifact(session_id, name)


_WITH_TURNS = selectinload(SessionRow.turns).selectinload(TurnRow.revisions)


# ---------------------------------------------------------------------- mapping


def _fill_session(row: SessionRow, s: InterviewSession) -> None:
    row.created_at = s.created_at
    row.status = s.status.value
    row.phase = s.phase.value if s.phase else None
    row.interview_type = s.config.interview_type.value
    row.difficulty = s.config.difficulty.value
    row.language = s.config.language.value
    row.modality = s.config.modality.value
    row.target_duration_s = s.config.target_duration_s
    row.custom_instructions = s.config.custom_instructions
    row.context = {
        "candidate_brief": s.context.candidate_brief,
        "job_brief": s.context.job_brief,
        "topics": [{"id": t.id, "title": t.title} for t in s.context.topics],
        "vocabulary": list(s.context.vocabulary),
        "role_profile": asdict(s.context.role_profile) if s.context.role_profile else None,
        "facts": [fact_to_json(f) for f in s.context.facts],
    }
    row.coverage = {k: v.value for k, v in s.coverage.items()}
    row.started_at = s.started_at
    row.ended_at = s.ended_at
    row.end_reason = s.end_reason.value if s.end_reason else None
    row.failure = s.failure
    row.paused_at = s.paused_at
    row.paused_total_s = s.paused_total_s
    row.paused_phase = s.paused_phase.value if s.paused_phase else None
    row.final_question_asked = s.final_question_asked
    row.snapshot_id = s.snapshot_id
    row.execution_profile = s.execution_profile
    row.profile_id = s.profile_id


def _turn_row(session_id: str, turn: Turn) -> TurnRow:
    move = None
    if isinstance(turn, InterviewerTurn):
        m = turn.move
        move = {
            "action": m.action.value,
            "topic_id": m.topic_id,
            "utterance": m.utterance,
            "covered_topic_ids": list(m.covered_topic_ids),
            "status": m.status.value,
            "fallback": m.fallback,
            "model_ref": m.model_ref,
            "prompt_ref": m.prompt_ref,
        }
    return TurnRow(
        session_id=session_id,
        seq=turn.seq,
        speaker=turn.speaker.value,
        at=turn.at,
        elapsed_s=turn.elapsed_s,
        move=move,
        revisions=[],
    )


def _revision_row(session_id: str, seq: int, r: TranscriptRevision) -> RevisionRow:
    return RevisionRow(
        session_id=session_id,
        turn_seq=seq,
        number=r.number,
        text=r.text,
        source=r.source.value,
        created_at=r.created_at,
        engine_ref=r.engine_ref,
        words=[[w.text, w.start_s, w.end_s, w.probability] for w in r.words],
    )


def _session(row: SessionRow) -> InterviewSession:
    ctx = row.context
    return InterviewSession(
        id=row.id,
        created_at=row.created_at,
        config=InterviewConfig(
            interview_type=InterviewType(row.interview_type),
            difficulty=Difficulty(row.difficulty),
            language=Language(row.language),
            target_duration_s=row.target_duration_s,
            custom_instructions=row.custom_instructions,
            modality=Modality(row.modality),
        ),
        context=InterviewContext(
            candidate_brief=ctx["candidate_brief"],
            job_brief=ctx["job_brief"],
            topics=tuple(Topic(id=t["id"], title=t["title"]) for t in ctx["topics"]),
            vocabulary=tuple(ctx.get("vocabulary", ())),
            role_profile=role_from_json(ctx.get("role_profile")),
            facts=tuple(fact_from_json(f) for f in ctx.get("facts", ())),
        ),
        status=SessionStatus(row.status),
        phase=Phase(row.phase) if row.phase else None,
        turns=[_turn(t) for t in row.turns],
        coverage={k: TopicCoverage(v) for k, v in row.coverage.items()},
        started_at=row.started_at,
        ended_at=row.ended_at,
        end_reason=EndReason(row.end_reason) if row.end_reason else None,
        failure=row.failure,
        paused_at=row.paused_at,
        paused_total_s=row.paused_total_s,
        paused_phase=Phase(row.paused_phase) if row.paused_phase else None,
        final_question_asked=row.final_question_asked,
        snapshot_id=row.snapshot_id,
        execution_profile=row.execution_profile,
        profile_id=row.profile_id,
    )


def _turn(row: TurnRow) -> Turn:
    if row.speaker == Speaker.CANDIDATE.value:
        return CandidateTurn(
            seq=row.seq,
            at=row.at,
            elapsed_s=row.elapsed_s,
            revisions=tuple(_revision(r) for r in row.revisions),
        )
    m = row.move
    assert m is not None
    return InterviewerTurn(
        seq=row.seq,
        at=row.at,
        elapsed_s=row.elapsed_s,
        move=InterviewerMove(
            action=MoveAction(m["action"]),
            topic_id=m["topic_id"],
            utterance=m["utterance"],
            covered_topic_ids=tuple(m["covered_topic_ids"]),
            status=MoveStatus(m["status"]),
            fallback=m["fallback"],
            model_ref=m["model_ref"],
            prompt_ref=m["prompt_ref"],
        ),
    )


def _revision(row: RevisionRow) -> TranscriptRevision:
    return TranscriptRevision(
        number=row.number,
        text=row.text,
        source=RevisionSource(row.source),
        created_at=row.created_at,
        engine_ref=row.engine_ref,
        words=tuple(
            TranscriptWord(text=w[0], start_s=w[1], end_s=w[2], probability=w[3]) for w in row.words
        ),
    )


def _effective_s(started_at: float | None, end: float | None, paused_s: float) -> float | None:
    """The same measure as `InterviewSession.elapsed_s`, for interviews that are not running."""
    if started_at is None or end is None:
        return None
    return max(0.0, end - started_at - paused_s)
