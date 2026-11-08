"""Schema-aware assessment responses for offline application tests."""

from __future__ import annotations

import json
from typing import Any

from probeloop.ai.ports import ChatRequest


def scripted_assessment(request: ChatRequest) -> str:
    content = json.loads(request.messages[0].content)
    if isinstance(content, list):
        return json.dumps(
            {
                "units": [
                    {"unit_id": unit["unit_id"], "kind": "hr", "past_example": True}
                    for unit in content
                ]
            }
        )
    if "unit" in content:
        return json.dumps(_judgement(request, content))
    if "statement" in content:
        return json.dumps({"analysis": "Synthetic check.", "verdict": "incorrect"})
    if "observations" in content:
        ids = [o["id"] for o in content["observations"]]
        return json.dumps(
            {
                "priorities": ids[:1],
                "strengths": [],
                "summary": "Synthetic evidence-based practice summary.",
            }
        )
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


def _judgement(request: ChatRequest, content: dict[str, Any]) -> dict[str, Any]:
    candidates = [
        t for t in content["unit"]["turns"] if t["speaker"] == "candidate" and len(t["text"]) >= 8
    ]
    evidence = (
        [{"source_id": candidates[0]["source_id"], "quote": candidates[0]["text"][:180]}]
        if candidates
        else []
    )
    result: dict[str, Any] = {
        "scores": {
            c["id"]: {
                "evidence": evidence,
                "reason": "Synthetic assessment.",
                "score": 3 if evidence else None,
            }
            for c in content["rubric"]["criteria"]
        }
    }
    schema = request.response_schema or {}
    if "observations" in schema.get("properties", {}):
        result["observations"] = (
            [
                {
                    "kind": "strength",
                    "evidence": evidence,
                    "text": "Synthetic evidence-based observation.",
                }
            ]
            if evidence
            else []
        )
        result["coverage"] = []
    return result
