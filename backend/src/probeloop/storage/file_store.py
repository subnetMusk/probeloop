"""File-based session store: one directory per session.

Each directory holds `session.json`, the audio of spoken answers (`audio/answer-NNNN.wav`, 16 kHz
mono) and `metrics.jsonl` (one `TurnMetrics` record per spoken answer). Used until database
persistence (milestone M4). Deleting a session removes its directory, and with it all of its files.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

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
    SessionStatus,
    Topic,
    TopicCoverage,
    Turn,
)
from probeloop.speech.audio import PcmAudio, to_wav

SCHEMA_VERSION = 1
_ID = re.compile(r"^[0-9a-f]{32}$")


class FileSessionStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        root.mkdir(parents=True, exist_ok=True)

    async def save(self, session: InterviewSession) -> None:
        await asyncio.to_thread(self._write, session)

    async def load(self, session_id: str) -> InterviewSession | None:
        return await asyncio.to_thread(self._read, session_id)

    async def summaries(self) -> list[SessionSummary]:
        return await asyncio.to_thread(self._list)

    async def delete(self, session_id: str) -> bool:
        return await asyncio.to_thread(self._delete, session_id)

    async def save_answer_audio(self, session_id: str, turn_seq: int, audio: PcmAudio) -> None:
        await asyncio.to_thread(self._write_audio, session_id, turn_seq, audio)

    async def append_metrics(self, session_id: str, record: Mapping[str, object]) -> None:
        await asyncio.to_thread(self._append_metrics, session_id, dict(record))

    def session_dir(self, session_id: str) -> Path:
        if not _ID.match(session_id):
            raise ValueError("invalid session id")
        return self._root / session_id

    # ------------------------------------------------------------------ sync helpers

    def _write(self, session: InterviewSession) -> None:
        directory = self.session_dir(session.id)
        directory.mkdir(parents=True, exist_ok=True)
        data = json.dumps(to_dict(session), ensure_ascii=False, indent=2)
        _atomic_write(directory / "session.json", data.encode("utf-8"))

    def _write_audio(self, session_id: str, turn_seq: int, audio: PcmAudio) -> None:
        directory = self.session_dir(session_id) / "audio"
        directory.mkdir(parents=True, exist_ok=True)
        _atomic_write(directory / f"answer-{turn_seq:04d}.wav", to_wav(audio))

    def _append_metrics(self, session_id: str, record: dict[str, object]) -> None:
        directory = self.session_dir(session_id)
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "metrics.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _read(self, session_id: str) -> InterviewSession | None:
        try:
            path = self.session_dir(session_id) / "session.json"
        except ValueError:
            return None
        if not path.exists():
            return None
        return from_dict(json.loads(path.read_text(encoding="utf-8")))

    def _list(self) -> list[SessionSummary]:
        out = []
        for path in self._root.glob("*/session.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            out.append(
                SessionSummary(
                    id=data["id"],
                    created_at=data["created_at"],
                    status=SessionStatus(data["status"]),
                    interview_type=data["config"]["interview_type"],
                    language=data["config"]["language"],
                )
            )
        return sorted(out, key=lambda s: s.created_at, reverse=True)

    def _delete(self, session_id: str) -> bool:
        try:
            directory = self.session_dir(session_id)
        except ValueError:
            return False
        if not directory.exists():
            return False
        shutil.rmtree(directory)
        return True


def _atomic_write(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.stem}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------- mapping


def to_dict(s: InterviewSession) -> dict[str, Any]:
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
        return CandidateTurn(seq=d["seq"], at=d["at"], elapsed_s=d["elapsed_s"], text=d["text"])
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
