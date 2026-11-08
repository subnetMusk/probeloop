"""Measure a real-model CV review on labelled synthetic text; keep raw output outside git."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict
from pathlib import Path

from probeloop.ai.ollama import OllamaChatModel
from probeloop.assessment.application.cv_review import CvReviewer
from probeloop.assessment.application.rubrics import load_rubric
from probeloop.context.domain.model import (
    ContextSnapshot,
    Document,
    DocumentKind,
    DocumentOrigin,
    JobMode,
    TargetArea,
)
from probeloop.settings import Settings


async def run(output: Path) -> None:
    settings = Settings()
    model = OllamaChatModel(
        base_url=settings.ollama_base_url,
        model=settings.evaluation_model,
        context_window=settings.evaluation_context_window,
        timeout_s=600,
    )
    text = (Path(__file__).parents[1] / "tests/fixtures/synthetic/cv_review/cv.txt").read_text()
    document = Document("cv", DocumentKind.CV, "Synthetic CV", DocumentOrigin.TYPED, text, 0)
    snapshot = ContextSnapshot(
        "snapshot",
        "preparation",
        0,
        "en",
        JobMode.NONE,
        (),
        (),
        (),
        TargetArea("Backend engineering", "mid", "Synthetic evaluation", confirmed=True),
        (),
        (document,),
        "synthetic",
    )

    async def progress(value: float, message: str | None) -> None:
        print(f"{value:.0%}: {message}", flush=True)

    started = time.monotonic()
    scores, observations, checks, dropped = await CvReviewer(model, load_rubric("cv")).review(
        snapshot,
        "en",
        progress,
    )
    result = {
        "model": model.model_ref,
        "duration_s": round(time.monotonic() - started, 2),
        "scores": [asdict(s) for s in scores],
        "observations": [asdict(n) for n in observations],
        "checks": [asdict(c) for c in checks],
        "dropped": dropped,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(output.write_text, json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({"duration_s": result["duration_s"], "dropped": dropped}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(run(parser.parse_args().output))
