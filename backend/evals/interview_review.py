"""Measure evidence-grounded interview review on a synthetic, labelled transcript.

Each run records every logical model call (phase, attempts, tokens, stop reasons, duration) and
the labelled checks below, so latency and quality are compared on the same output. The fixture
is `tests/fixtures/synthetic/assessment/interview.json`; its traits define the expectations.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import asdict
from pathlib import Path

from tests.assessment.support import synthetic_session

from probeloop.ai.debuglog import DebugLogChatModel
from probeloop.ai.ollama import OllamaChatModel
from probeloop.ai.ports import ChatModel
from probeloop.assessment.application.interview_review import (
    InterviewJudgement,
    InterviewReviewer,
    Reasoning,
)
from probeloop.assessment.domain.model import overall_score
from probeloop.interview.domain.model import InterviewSession
from probeloop.settings import Settings


def labelled_checks(result: InterviewJudgement, session: InterviewSession) -> dict[str, object]:
    """Expectations from the fixture traits: u0 vague ownership, u4 planted error (turn 5), u6
    a correct answer that mentions a real failure mode (turn 7), u8 closing."""

    def score(unit: str, criterion: str) -> float | None:
        return next(
            (
                s.value
                for s in result.unit_scores
                if s.unit_id == unit and s.criterion_id == criterion
            ),
            None,
        )

    def cites(turn: int) -> bool:
        return any(
            any(e.turn_seq == turn for e in o.evidence)
            for o in result.observations
            if o.kind == "technical_error"
        )

    texts = {t.seq: t.text for t in session.candidate_turns()}
    quotes = [e for s in result.unit_scores for e in s.evidence] + [
        e for o in result.observations for e in o.evidence
    ]
    keys = [(o.unit_id, o.kind, tuple(e.quote for e in o.evidence)) for o in result.observations]
    ownership = score("u0", "behavioral.ownership")
    planted = score("u4", "technical.accuracy")
    strong = score("u6", "technical.accuracy")
    return {
        "vague_ownership_detected": ownership is not None and ownership <= 2,
        "planted_error_reported": cites(5),
        "planted_error_scored_low": planted is not None and planted <= 2,
        "no_false_correction_on_correct_answer": not cites(7),
        "correct_answer_accuracy_at_least_4": strong is not None and strong >= 4,
        # The u6 question asks for a plan, not for a past example.
        "plan_not_scored_as_experience": score("u6", "technical.experience") is None,
        "closing_unscored": not any(s.unit_id == "u8" for s in result.unit_scores),
        "unverified_quotes": sum(
            e.turn_seq is None
            or " ".join(e.quote.split()) not in " ".join(texts[e.turn_seq].split())
            for e in quotes
        ),
        "duplicate_observations": len(keys) - len(set(keys)),
        "unstable_scores": sum(s.unstable for s in result.unit_scores),
    }


async def run(
    output: Path,
    repetitions: int,
    judge_reasoning: Reasoning,
    presence_penalty: float | None,
    debug_log: Path | None,
) -> None:
    settings = Settings()
    model = OllamaChatModel(
        base_url=settings.ollama_base_url,
        model=settings.evaluation_model,
        context_window=settings.evaluation_context_window,
        timeout_s=600,
    )
    # Raw prompts and outputs of synthetic data only, to explain discarded items.
    traced: ChatModel = DebugLogChatModel(model, debug_log) if debug_log else model
    reviewer = InterviewReviewer(
        traced, judge_reasoning=judge_reasoning, presence_penalty=presence_penalty
    )
    results: list[dict[str, object]] = []
    for index in range(repetitions):

        async def progress(value: float, message: str | None, run_number: int = index + 1) -> None:
            print(f"Run {run_number}: {value:.0%} {message or ''}", flush=True)

        session = synthetic_session()
        started = time.monotonic()
        result = await reviewer.review(session, None, "en", progress)
        record = {
            "model": model.model_ref,
            "prompt_ref": reviewer.prompt_ref,
            "presence_penalty": presence_penalty,
            "duration_s": round(time.monotonic() - started, 2),
            "overall": overall_score(result.scores),
            "checks": labelled_checks(result, session),
            **asdict(result),
        }
        results.append(record)
        output.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(
            output.write_text, json.dumps(results, ensure_ascii=False, indent=2)
        )
        for call in result.calls:
            print(
                f"  {call.phase:17} {call.unit_id or '-':4} attempts={call.attempts} "
                f"in={call.prompt_tokens} out={call.output_tokens} {call.duration_s:7.2f}s "
                f"stop={','.join(str(r) for r in call.stop_reasons)}",
                flush=True,
            )
        print(
            json.dumps(
                {
                    "run": index + 1,
                    "duration_s": record["duration_s"],
                    "overall": record["overall"],
                    "dropped": result.dropped,
                    "disputed": result.disputed,
                    "calls": len(result.calls),
                    "output_tokens": sum(c.output_tokens or 0 for c in result.calls),
                    "checks": record["checks"],
                }
            ),
            flush=True,
        )
    overall = [r["overall"] for r in results if isinstance(r["overall"], float | int)]
    if len(overall) > 1:
        print(json.dumps({"overall_spread": round(max(overall) - min(overall), 2)}), flush=True)
    durations = [float(str(r["duration_s"])) for r in results]
    print(json.dumps({"median_duration_s": statistics.median(durations)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--judge-reasoning", choices=["off", "default"], default="off")
    parser.add_argument(
        "--presence-penalty",
        default="0",
        help="a number, or 'model' to keep the model's default",
    )
    parser.add_argument("--debug-log", type=Path, default=None)
    args = parser.parse_args()
    penalty = None if args.presence_penalty == "model" else float(args.presence_penalty)
    asyncio.run(run(args.output, args.repetitions, args.judge_reasoning, penalty, args.debug_log))
