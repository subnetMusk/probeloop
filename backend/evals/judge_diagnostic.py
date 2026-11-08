"""Inspect output-budget failures on synthetic answer data; never use personal inputs."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import ollama
from tests.assessment.support import synthetic_session

from probeloop.ai.fake import FakeChatModel
from probeloop.assessment.application.interview_review import InterviewReviewer, turn_data
from probeloop.assessment.application.schemas import UnitJudgementsOut
from probeloop.settings import Settings


async def run(output: Path, context: int, tokens: int) -> None:
    settings = Settings()
    reviewer = InterviewReviewer(FakeChatModel(["{}"]))
    session = synthetic_session()
    request = reviewer._request(
        "judge_unit",
        {
            "unit_id": "u0",
            "kind": "behavioral",
            "turns": [turn_data(t) for t in session.turns[:4]],
            "approved_snapshot": None,
        },
        tokens=tokens,
        rubric=reviewer.rubrics["behavioral"],
    )
    response = await ollama.AsyncClient(host=settings.ollama_base_url, timeout=600).chat(
        model=settings.evaluation_model,
        messages=[
            {"role": "system", "content": request.instructions},
            {"role": "user", "content": request.messages[0].content},
        ],
        think=True,
        format=UnitJudgementsOut.model_json_schema(),
        stream=False,
        options={"num_ctx": context, "num_predict": tokens, "temperature": 0.1},
    )
    await asyncio.to_thread(output.write_text, response.model_dump_json(indent=2))
    print(
        json.dumps(
            {
                "prompt_tokens": response.prompt_eval_count,
                "output_tokens": response.eval_count,
                "reason": response.done_reason,
                "thinking_chars": len(response.message.thinking or ""),
                "content_chars": len(response.message.content or ""),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--context", type=int, default=8192)
    parser.add_argument("--tokens", type=int, default=5500)
    args = parser.parse_args()
    asyncio.run(run(args.output, args.context, args.tokens))
