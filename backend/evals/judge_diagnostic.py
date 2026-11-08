"""Inspect one judging pass on synthetic answer data; never use personal inputs.

Sends the current ascending-pass request for the first unit and records the raw response,
including any reasoning text, to show where the output budget goes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import ollama
from tests.assessment.support import synthetic_session

from probeloop.ai.fake import FakeChatModel
from probeloop.assessment.application.interview_review import (
    InterviewReviewer,
    evaluation_context,
    turn_data,
)
from probeloop.settings import Settings


async def run(output: Path, context: int, think: bool) -> None:
    settings = Settings()
    reviewer = InterviewReviewer(
        FakeChatModel(["{}"]), judge_reasoning="default" if think else "off"
    )
    session = synthetic_session()
    rubric = reviewer.rubrics["behavioral"]
    unit = {
        "unit_id": "u0",
        "kind": "behavioral",
        "topic": None,
        "difficulty": session.config.difficulty.value,
        "turns": [turn_data(t) for t in session.turns[:4]],
    }
    request = reviewer._judge_request(
        evaluation_context(session, None), rubric, unit, descending=False, language="en"
    )
    schema = reviewer._outputs[("behavioral", True)].model_json_schema()
    response = await ollama.AsyncClient(host=settings.ollama_base_url, timeout=600).chat(
        model=settings.evaluation_model,
        messages=[
            {"role": "system", "content": request.instructions},
            {"role": "user", "content": request.messages[0].content},
        ],
        think=think,
        format=schema,
        stream=False,
        options={
            "num_ctx": context,
            "num_predict": request.max_output_tokens,
            "temperature": request.temperature,
            "presence_penalty": request.presence_penalty,
        },
    )
    await asyncio.to_thread(output.write_text, response.model_dump_json(indent=2))
    print(
        json.dumps(
            {
                "prompt_tokens": response.prompt_eval_count,
                "output_tokens": response.eval_count,
                "reason": response.done_reason,
                "seconds": round((response.total_duration or 0) / 1e9, 2),
                "thinking_chars": len(response.message.thinking or ""),
                "content_chars": len(response.message.content or ""),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--context", type=int, default=16384)
    parser.add_argument("--think", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.output, args.context, args.think))
