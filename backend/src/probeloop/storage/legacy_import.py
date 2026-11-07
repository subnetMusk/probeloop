"""Import of the sessions written by the file-based store used before M4.

Each old session directory holds `session.json` and, for voice interviews, the audio of every
turn and `metrics.jsonl`. The directory layout of the audio is the same as today, so only the
structured data moves to the database. An imported `session.json` is renamed to
`session.imported.json`, so a second run skips it.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from probeloop.interview.application.ports import SessionStore
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
    Topic,
    TopicCoverage,
    TranscriptRevision,
    Turn,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ImportResult:
    imported: list[str]
    skipped: list[str]
    failed: list[str]


async def import_file_sessions(root: Path, store: SessionStore) -> ImportResult:
    imported: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []
    paths = await asyncio.to_thread(lambda: sorted(root.glob("*/session.json")))
    for path in paths:
        try:
            text = await asyncio.to_thread(path.read_text, encoding="utf-8")
            session = from_dict(json.loads(text))
        except (ValueError, KeyError, TypeError):
            logger.exception("old session not readable", extra={"path": str(path)})
            failed.append(path.parent.name)
            continue
        if await store.load(session.id) is not None:
            skipped.append(session.id)
            continue
        await store.save(session)
        for record in await asyncio.to_thread(_take_metrics, path.parent / "metrics.jsonl"):
            await store.append_metrics(session.id, record)
        await asyncio.to_thread(path.rename, path.with_name("session.imported.json"))
        imported.append(session.id)
    return ImportResult(imported=imported, skipped=skipped, failed=failed)


def _take_metrics(path: Path) -> list[dict[str, Any]]:
    """The metric records of an old session; the file is removed once they are read."""
    if not path.is_file():
        return []
    records = [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]
    path.unlink()
    return records


# ---------------------------------------------------------------------- mapping


def to_dict(s: InterviewSession) -> dict[str, Any]:
    """The old format; kept to write test fixtures."""
    return {
        "schema_version": SCHEMA_VERSION,
        "id": s.id,
        "created_at": s.created_at,
        "config": {
            "interview_type": s.config.interview_type.value,
            "difficulty": s.config.difficulty.value,
            "language": s.config.language.value,
            "target_duration_s": s.config.target_duration_s,
            "custom_instructions": s.config.custom_instructions,
            "modality": s.config.modality.value,
        },
        "context": {
            "candidate_brief": s.context.candidate_brief,
            "job_brief": s.context.job_brief,
            "topics": [{"id": t.id, "title": t.title} for t in s.context.topics],
        },
        "status": s.status.value,
        "phase": s.phase.value if s.phase else None,
        "turns": [_turn_to_dict(t) for t in s.turns],
        "coverage": {k: v.value for k, v in s.coverage.items()},
        "started_at": s.started_at,
        "ended_at": s.ended_at,
        "end_reason": s.end_reason.value if s.end_reason else None,
        "failure": s.failure,
        "paused_at": s.paused_at,
        "paused_total_s": s.paused_total_s,
        "paused_phase": s.paused_phase.value if s.paused_phase else None,
        "final_question_asked": s.final_question_asked,
    }


def from_dict(d: dict[str, Any]) -> InterviewSession:
    if d.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported session schema version {d.get('schema_version')}")
    c = d["config"]
    ctx = d["context"]
    return InterviewSession(
        id=d["id"],
        created_at=d["created_at"],
        config=InterviewConfig(
            interview_type=InterviewType(c["interview_type"]),
            difficulty=Difficulty(c["difficulty"]),
            language=Language(c["language"]),
            target_duration_s=c["target_duration_s"],
            custom_instructions=c["custom_instructions"],
            # Absent in sessions written before voice support: those were text interviews.
            modality=Modality(c.get("modality", Modality.TEXT.value)),
        ),
        context=InterviewContext(
            candidate_brief=ctx["candidate_brief"],
            job_brief=ctx["job_brief"],
            topics=tuple(Topic(id=t["id"], title=t["title"]) for t in ctx["topics"]),
        ),
        status=SessionStatus(d["status"]),
        phase=Phase(d["phase"]) if d["phase"] else None,
        turns=[_turn_from_dict(t) for t in d["turns"]],
        coverage={k: TopicCoverage(v) for k, v in d["coverage"].items()},
        started_at=d["started_at"],
        ended_at=d["ended_at"],
        end_reason=EndReason(d["end_reason"]) if d["end_reason"] else None,
        failure=d["failure"],
        paused_at=d["paused_at"],
        paused_total_s=d["paused_total_s"],
        paused_phase=Phase(d["paused_phase"]) if d["paused_phase"] else None,
        final_question_asked=d["final_question_asked"],
    )


def _turn_to_dict(t: Turn) -> dict[str, Any]:
    base: dict[str, Any] = {"seq": t.seq, "at": t.at, "elapsed_s": t.elapsed_s}
    if isinstance(t, CandidateTurn):
        return {**base, "speaker": "candidate", "text": t.text}
    m = t.move
    return {
        **base,
        "speaker": "interviewer",
        "move": {
            "action": m.action.value,
            "topic_id": m.topic_id,
            "utterance": m.utterance,
            "covered_topic_ids": list(m.covered_topic_ids),
            "status": m.status.value,
            "fallback": m.fallback,
            "model_ref": m.model_ref,
            "prompt_ref": m.prompt_ref,
        },
    }


def _turn_from_dict(d: dict[str, Any]) -> Turn:
    if d["speaker"] == "candidate":
        revision = TranscriptRevision(
            number=1, text=d["text"], source=RevisionSource.STT, created_at=d["at"]
        )
        return CandidateTurn(
            seq=d["seq"], at=d["at"], elapsed_s=d["elapsed_s"], revisions=(revision,)
        )
    m = d["move"]
    return InterviewerTurn(
        seq=d["seq"],
        at=d["at"],
        elapsed_s=d["elapsed_s"],
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
