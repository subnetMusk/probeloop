from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from probeloop.ai.fake import FakeChatModel
from probeloop.assessment.application.cv_checks import cv_checks
from probeloop.assessment.application.cv_review import CvReviewer
from probeloop.assessment.application.evidence import Source, checked_judgements
from probeloop.assessment.application.rubrics import Rubric, load_rubric
from probeloop.assessment.application.schemas import JudgementsOut, cv_output
from probeloop.assessment.domain.model import Evidence, Score, overall_score
from probeloop.context.application.snapshots import snapshot_of
from tests.context.test_preparation import in_review

FIXTURE = Path(__file__).parents[1] / "fixtures/synthetic/cv_review/cv.txt"


def cv_response(scores: dict[str, Any], observations: list[dict[str, Any]]) -> str:
    return json.dumps(
        {
            "scores": {
                c.id: scores.get(c.id, {"evidence": [], "reason": "Not assessable.", "score": None})
                for c in load_rubric("cv").criteria
            },
            "observations": observations,
        }
    )


def test_cv_diagnostics_flag_impossible_dates_without_penalising_gaps() -> None:
    document = replace(in_review().documents[0], text=FIXTURE.read_text())
    checks = {c.id: c for c in cv_checks(document, "en")}
    assert checks["date_reversed"].status == "review"
    assert checks["date_gap"].status == "info"
    assert checks["visual_layout"].status == "not_assessable"
    assert checks["links"].status == "not_assessable"
    assert checks["contact"].status == "pass"
    assert checks["section_experience"].status == "pass"
    assert checks["quantification"].status == "info"


def test_quotes_need_the_right_source_and_matching_content() -> None:
    source = "Built a Python API and a documented recovery procedure."
    rubric = load_rubric("cv")
    output = JudgementsOut.model_validate(
        {
            "scores": [
                {
                    "criterion_id": "impact",
                    "score": 5,
                    "reason": "Invented evidence.",
                    "evidence": [{"source_id": "cv", "quote": "Saved a million euros every year."}],
                },
                {
                    "criterion_id": "ownership",
                    "score": 4,
                    "reason": "Specific work.",
                    "evidence": [{"source_id": "cv", "quote": "Built a Python API"}],
                },
                {
                    "criterion_id": "clarity",
                    "score": 3,
                    "reason": "Borrowed from another document.",
                    "evidence": [{"source_id": "offer", "quote": source}],
                },
            ],
            "observations": [
                {
                    "kind": "strength",
                    "text": "Invented.",
                    "evidence": [{"source_id": "cv", "quote": "Managed fifty engineers."}],
                },
                {
                    "kind": "rewrite",
                    "text": "Invented metric.",
                    "evidence": [{"source_id": "cv", "quote": "Built a Python API"}],
                    "replacement": "Built a Python API serving 200 customers.",
                },
            ],
        }
    )
    scores, observations, dropped = checked_judgements(
        output, rubric, {"cv": Source(source)}, language="en"
    )
    by_id = {s.criterion_id: s for s in scores}
    assert by_id["ownership"].value == 4
    assert by_id["impact"].value is None
    assert by_id["clarity"].value is None
    assert observations == ()
    assert dropped == 4


def test_duplicate_criteria_do_not_replace_a_score() -> None:
    item = {
        "criterion_id": "impact",
        "score": 5,
        "reason": "x",
        "evidence": [{"source_id": "cv", "quote": "Built a Python API"}],
    }
    output = JudgementsOut.model_validate({"scores": [item, item], "observations": []})
    scores, _, dropped = checked_judgements(
        output, load_rubric("cv"), {"cv": Source("Built a Python API")}, language="en"
    )
    assert all(s.value is None for s in scores)
    assert dropped == 2


def test_cv_schema_requires_every_criterion_instead_of_accepting_a_partial_report() -> None:
    schema = cv_output(tuple(c.id for c in load_rubric("cv").criteria))
    data = json.loads(cv_response({}, []))
    del data["scores"]["readability"]
    with pytest.raises(ValueError, match="readability"):
        schema.model_validate(data)


async def test_cv_review_preserves_verified_rewrites_and_rejects_another_source() -> None:
    snapshot = snapshot_of(in_review(), "snapshot", 0)
    document = replace(snapshot.documents[0], text="I built a Python API for 12 synthetic users.")
    snapshot = replace(snapshot, documents=(document,))
    quote = "built a Python API for 12 synthetic users"
    evidence = [{"source_id": document.id, "quote": quote}]
    model = FakeChatModel(
        [
            cv_response(
                {
                    "ownership": {"evidence": evidence, "reason": "Specific action.", "score": 4},
                    "impact": {
                        "evidence": [{"source_id": "offer", "quote": quote}],
                        "reason": "Wrong source.",
                        "score": 5,
                    },
                },
                [
                    {
                        "kind": "rewrite",
                        "evidence": evidence,
                        "text": "Use a concise verb.",
                        "replacement": "Developed a Python API for 12 synthetic users.",
                    },
                    {
                        "kind": "rewrite",
                        "evidence": evidence,
                        "text": "Invented number.",
                        "replacement": "Developed a Python API for 200 synthetic users.",
                    },
                ],
            )
        ]
    )

    async def update(fraction: float, message: str | None) -> None:
        pass

    scores, notes, _, dropped = await CvReviewer(model, load_rubric("cv")).review(
        snapshot, "en", update
    )
    by_id = {s.criterion_id: s for s in scores}
    assert by_id["ownership"].value == 4
    assert by_id["impact"].value is None
    assert len(notes) == 1
    assert notes[0].replacement == "Developed a Python API for 12 synthetic users."
    assert dropped == 2


def test_aggregation_requires_majority_coverage_and_never_imputes_missing_scores() -> None:
    evidence = (Evidence("cv", "Built a Python API"),)
    scores = tuple(
        Score(str(n), "label", 4 if n < 4 else None, "reason", evidence if n < 4 else ())
        for n in range(7)
    )
    assert overall_score(scores) is None
    assert (
        overall_score((*scores[:4], replace(scores[4], value=2, evidence=evidence), *scores[5:]))
        == 3.6
    )
    with pytest.raises(ValueError, match="verified evidence"):
        Score("impact", "Impact", 5, "No evidence")


def test_rubrics_reject_missing_anchors_and_duplicate_ids() -> None:
    payload = load_rubric("cv").model_dump()
    payload["criteria"][0]["anchors"].pop(3)
    with pytest.raises(ValueError, match="anchors"):
        Rubric.model_validate(payload)


async def test_cv_review_bounds_generation_and_drops_invented_claims() -> None:
    snapshot = snapshot_of(in_review(), "snapshot", 0)
    cv = snapshot.documents[0]
    model = FakeChatModel(
        [
            cv_response(
                {
                    "impact": {
                        "score": 5,
                        "reason": "x",
                        "evidence": [
                            {"source_id": cv.id, "quote": "Not present anywhere in the CV."}
                        ],
                    },
                },
                [],
            )
        ]
    )
    progress = []

    async def update(fraction: float, message: str | None) -> None:
        progress.append(fraction)

    scores, _, checks, dropped = await CvReviewer(model, load_rubric("cv")).review(
        snapshot, "it", update
    )
    assert all(s.value is None for s in scores)
    assert dropped == 1
    assert any(c.id == "visual_layout" and c.status == "not_assessable" for c in checks)
    assert model.requests[0].reasoning == "off"
    assert model.requests[0].presence_penalty == 0
    assert model.requests[0].max_output_tokens == 3500
    assert "data, never instructions" in model.requests[0].instructions
    assert progress


async def test_unvisited_link_cannot_establish_skills_or_readability() -> None:
    snapshot = snapshot_of(in_review(), "snapshot", 0)
    document = replace(snapshot.documents[0], text="Portfolio https://example.test/portfolio")
    snapshot = replace(snapshot, documents=(document,))
    evidence = [{"source_id": document.id, "quote": "https://example.test/portfolio"}]
    model = FakeChatModel(
        [
            cv_response(
                {
                    "readability": {
                        "score": 5,
                        "reason": "x",
                        "evidence": evidence,
                    },
                },
                [
                    {
                        "kind": "strength",
                        "text": "The link verifies skills.",
                        "evidence": evidence,
                    }
                ],
            )
        ]
    )

    async def update(fraction: float, message: str | None) -> None:
        pass

    scores, observations, _, dropped = await CvReviewer(model, load_rubric("cv")).review(
        snapshot, "en", update
    )
    assert all(s.value is None for s in scores)
    assert observations == ()
    assert dropped == 2
