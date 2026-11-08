"""Schema-aware assessment responses for offline application tests."""

from __future__ import annotations

import json

from probeloop.ai.ports import ChatRequest


def scripted_assessment(request: ChatRequest) -> str:
    content = json.loads(request.messages[0].content)
    source_id = content["source_id"]
    text = content["text"]
    quote = next(line for line in text.splitlines() if len(line) >= 8)[:180]
    evidence = [{"source_id": source_id, "quote": quote, "turn_seq": None}]
    return json.dumps(
        {
            "scores": [
                {
                    "criterion_id": name,
                    "score": 3,
                    "reason": "Synthetic assessment.",
                    "evidence": evidence,
                }
                for name in (
                    "relevance",
                    "impact",
                    "ownership",
                    "clarity",
                    "consistency",
                    "depth",
                    "readability",
                )
            ],
            "observations": [
                {
                    "kind": "question",
                    "text": "Which personal contribution mattered most?",
                    "evidence": evidence,
                    "replacement": None,
                }
            ],
        }
    )
