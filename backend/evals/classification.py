"""Measure question classification on labelled synthetic Italian and English units."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from tests.conftest import make_session

from probeloop.ai.debuglog import DebugLogChatModel
from probeloop.ai.ollama import OllamaChatModel
from probeloop.ai.ports import ChatModel
from probeloop.assessment.application.interview_review import CallTrace, InterviewReviewer
from probeloop.interview.domain.model import (
    EndReason,
    InterviewerMove,
    InterviewSession,
    MoveAction,
)
from probeloop.settings import Settings

FIXTURE = Path(__file__).parent / "fixtures/synthetic/assessment/classification.json"


def session_for(
    cases: list[dict[str, Any]],
) -> tuple[InterviewSession, dict[str, dict[str, Any]]]:
    session = make_session()
    session.start(0)
    expected = {}
    for index, case in enumerate(cases):
        now = index * 60.0
        unit_id = f"u{len(session.turns)}"
        expected[unit_id] = case
        for followup, question in enumerate(case["questions"]):
            action = MoveAction.FOLLOW_UP if followup else MoveAction.NEW_TOPIC
            session.record_move(InterviewerMove(action, "t1", question), now)
            session.finish_speaking(now + 1)
            session.start_answer(now + 2)
            session.finish_answer(now + 3)
            session.record_answer(
                "Synthetic answer, deliberately irrelevant to classification.", now + 4
            )
            now += 5
    session.end(EndReason.USER_ENDED, len(cases) * 60)
    return session, expected


async def run(args: argparse.Namespace) -> int:
    settings = Settings()
    model: ChatModel = OllamaChatModel(
        base_url=settings.ollama_base_url,
        model=settings.evaluation_model,
        context_window=settings.evaluation_context_window,
        timeout_s=600,
    )
    if args.debug_log:
        model = DebugLogChatModel(model, args.debug_log)
    reviewer = InterviewReviewer(model)
    cases = json.loads(FIXTURE.read_text())
    groups = [[case] for case in cases] if args.isolated else [cases]
    rows = []
    traces: list[dict[str, Any]] = []
    for repetition in range(args.repetitions):
        for group in groups:
            session, expected = session_for(group)
            calls: list[CallTrace] = []
            units, past = await reviewer._classify(session, calls)
            for unit in units:
                case = expected[unit.id]
                row = {
                    "run": repetition + 1,
                    "case": case["id"],
                    "expected_kind": case["kind"],
                    "kind": unit.kind,
                    "expected_past_example": case["past_example"],
                    "past_example": past[unit.id],
                }
                rows.append(row)
                print(json.dumps(row), flush=True)
            traces.extend(asdict(call) for call in calls)
        result = {
            "prompt_ref": reviewer.prompt_ref,
            "model": model.model_ref,
            "fixture_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            "isolated": args.isolated,
            "kind_correct": sum(r["kind"] == r["expected_kind"] for r in rows),
            "past_example_correct": sum(
                r["past_example"] == r["expected_past_example"] for r in rows
            ),
            "total": len(rows),
            "rows": rows,
            "calls": traces,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k not in ("rows", "calls")}), flush=True)
    return 0 if result["kind_correct"] == result["past_example_correct"] == result["total"] else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--debug-log", type=Path)
    parser.add_argument("--isolated", action="store_true", help="classify each unit on its own")
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be positive")
    sys_exit = asyncio.run(run(args))
    raise SystemExit(sys_exit)


if __name__ == "__main__":
    main()
