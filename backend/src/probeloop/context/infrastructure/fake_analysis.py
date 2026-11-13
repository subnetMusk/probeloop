"""Deterministic document analysis for offline browser tests; never used with real engines."""

from __future__ import annotations

import json

from probeloop.ai.ports import ChatRequest


def scripted_analysis(request: ChatRequest) -> str:
    properties = (request.response_schema or {}).get("properties", {})
    content = request.messages[0].content
    if "target_role" in properties:
        return json.dumps(
            {
                "profession": "Software engineering",
                "target_role": "Backend engineer",
                "seniority": "mid",
                "responsibilities": ["Maintain reliable services"],
                "competencies": ["Reasoning about reliability"],
                "basis_fact_ids": [],
                "rationale": "Synthetic proposal; confirm or correct before starting.",
            }
        )
    if "requirements" in properties and "facts" in properties:  # not the offer draft
        text = content.split("<<<\n", 1)[-1].rsplit("\n>>>", 1)[0]
        lines = [line.strip() for line in text.splitlines() if len(line.strip()) >= 8]
        items: list[dict[str, object]] = [
            {
                "statement": line[:400],
                "quote": line[:600],
                "category": "skill",
                "obligation": "must",
                "any_of": [],
                "equivalents": [],
                "threshold": None,
                "refines": None,
                "implicit": False,
            }
            for line in lines[:6]
        ]
        return json.dumps({"requirements": items, "facts": [], "terms": ["Python", "FastAPI"]})
    if "facts" in properties:
        text = content.split("<<<\n", 1)[-1].rsplit("\n>>>", 1)[0]
        job = "Document type: a job offer." in request.instructions
        subject, kind = ("job", "requirement") if job else ("candidate", "role")
        lines = [line.strip() for line in text.splitlines() if len(line.strip()) >= 8]
        facts = [
            {"subject": subject, "kind": kind, "statement": line[:400], "quote": line[:600]}
            for line in lines[:6]
        ]
        if not job:
            facts.append(
                {
                    "subject": "candidate",
                    "kind": "skill",
                    "statement": "Unverified model interpretation.",
                    "quote": "This invented quotation does not occur in the document.",
                }
            )
        return json.dumps({"facts": facts, "terms": ["Python", "FastAPI", "PostgreSQL"]})
    if "matches" in properties:
        requirements, candidate = content.split("\n\nCandidate facts:\n", 1)
        fact_ids = [
            line[2:].split(":", 1)[0] for line in candidate.splitlines() if line.startswith("- ")
        ]
        return json.dumps(
            {
                "matches": [
                    {
                        "requirement_id": line[2:].split(":", 1)[0],
                        "status": "partial" if fact_ids else "not_shown",
                        "fact_ids": fact_ids[:1],
                        "rationale": "Synthetic comparison for browser tests.",
                    }
                    for line in requirements.splitlines()
                    if line.startswith("- ")
                ]
            }
        )
    if "area" in properties:
        return json.dumps(
            {
                "area": "Backend engineering",
                "seniority": "mid",
                "rationale": "Backend roles in the supplied CV.",
            }
        )
    if "responsibilities" in properties:
        return json.dumps(
            {
                "title": "Backend engineer",
                "company": "Synthetic software company",
                "seniority": "mid",
                "summary": "Develop Python services.",
                "responsibilities": ["Build reliable APIs."],
                "requirements": ["Python and PostgreSQL experience."],
                "nice_to_have": [],
            }
        )
    raise AssertionError("unexpected analysis schema")
