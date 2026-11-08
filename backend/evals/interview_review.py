"""Measure evidence-grounded interview review on a synthetic, labelled transcript."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict
from pathlib import Path

from tests.assessment.support import synthetic_session

from probeloop.ai.ollama import OllamaChatModel
from probeloop.assessment.application.interview_review import InterviewReviewer
from probeloop.assessment.domain.model import overall_score
from probeloop.settings import Settings


async def run(output: Path, repetitions: int) -> None:
    settings = Settings()
    model = OllamaChatModel(
        base_url=settings.ollama_base_url,
        model=settings.evaluation_model,
        context_window=settings.evaluation_context_window,
        timeout_s=600,
    )
    results = []
    for index in range(repetitions):

        async def progress(value: float, message: str | None, run_number: int = index + 1) -> None:
            print(f"Run {run_number}: {value:.0%} {message}", flush=True)

        started = time.monotonic()
        result = await InterviewReviewer(model).review(synthetic_session(), None, "en", progress)
        record = {
            "model": model.model_ref,
            "duration_s": round(time.monotonic() - started, 2),
            "overall": overall_score(result.scores),
            **asdict(result),
        }
        results.append(record)
        output.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(
            output.write_text, json.dumps(results, ensure_ascii=False, indent=2)
        )
        print(
            json.dumps(
                {
                    "run": index + 1,
                    "duration_s": record["duration_s"],
                    "overall": record["overall"],
                    "dropped": result.dropped,
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=1)
    args = parser.parse_args()
    asyncio.run(run(args.output, args.repetitions))
