"""Schema-aware assessment responses for offline application tests."""

from __future__ import annotations

import json

from probeloop.ai.ports import ChatRequest
from probeloop.assessment.application.rubrics import load_rubric


def scripted_assessment(request: ChatRequest) -> str:
    content = json.loads(request.messages[0].content)
    if isinstance(content, list):
        return json.dumps(
            {"units": [{"unit_id": unit["unit_id"], "kind": "hr"} for unit in content]}
        )
    if "turns" in content:
        candidates = [
            t for t in content["turns"] if t["speaker"] == "candidate" and len(t["text"]) >= 8
        ]
        evidence = (
            [
                {
                    "source_id": candidates[0]["source_id"],
                    "turn_seq": candidates[0]["seq"],
                    "quote": candidates[0]["text"][:180],
                }
            ]
            if candidates
            else []
        )
        kind = content.get("kind")
        return json.dumps(
            {
                "scores": [
                    {
                        "criterion_id": c.id,
                        "score": 3 if evidence else None,
                        "reason": "Synthetic assessment.",
                        "evidence": evidence,
                    }
                    for c in load_rubric(kind).criteria
                ]
                if kind
                else [],
                "observations": [
                    {
                        "kind": "strength" if kind else "summary",
                        "text": "Synthetic evidence-based practice summary.",
                        "evidence": evidence,
                    }
                ]
                if evidence
                else [],
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
