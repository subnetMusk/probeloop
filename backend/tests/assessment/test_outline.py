from __future__ import annotations

import json
import re
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from probeloop.assessment.application.labels import section_label
from probeloop.assessment.application.outline import report_outline
from probeloop.assessment.application.schemas import ReportData
from probeloop.assessment.domain.model import Check, DeliveryMetric
from probeloop.assessment.infrastructure.exports import markdown, report_html

FIXTURE = Path(__file__).parents[1] / "fixtures/synthetic/assessment/report-outline.json"


def test_cv_requirements_follow_the_page_order_and_delivery_rounds_half_up() -> None:
    cases = json.loads(FIXTURE.read_text())
    cv = ReportData.model_validate(cases["cv"]["report"]).domain()
    outline = report_outline(
        cv,
        {},
        requirements=(
            Check("document_requirement:a", "met", "Shown requirement"),
            Check("document_requirement:b", "not_shown", "Missing requirement"),
            Check("document_requirement:c", "partial", "Partial requirement"),
        ),
    )
    assert [row.id for row in outline.requirements] == ["b", "c", "a"]
    report = replace(
        ReportData.model_validate(cases["interview"]["report"]).domain(),
        delivery=(
            DeliveryMetric("answer_duration", 48, "s", "", 1),
            DeliveryMetric("fillers", 1, "count", "", 1),
        ),
    )
    delivery = report_outline(report, {}).delivery
    assert delivery is not None
    assert delivery.fillers_per_minute == 1.3


@pytest.mark.parametrize("kind", ["interview", "cv"])
def test_outline_matches_the_shared_frontend_contract(kind: str) -> None:
    case = json.loads(FIXTURE.read_text())[kind]
    report = ReportData.model_validate(case["report"]).domain()
    revisions = {r.seq: r.revision for r in report.revisions}
    transcript = {}
    for turn in case.get("session", {}).get("turns", []):
        revision = next(
            (r for r in turn["revisions"] if r["number"] == revisions.get(turn["seq"])), None
        )
        transcript[turn["seq"]] = revision["text"] if revision else turn["text"]
    outline = report_outline(report, transcript)
    actual = asdict(outline)
    actual.pop("title")
    actual.pop("original")
    assert json.loads(json.dumps(actual)) == case["expected"]
    if kind == "interview":
        assert outline.units[0].answers[1].text == "Partizioni per cliente."
        assert outline.delivery is not None
        assert outline.delivery.median_rate == 130
        assert outline.delivery.talk_share == 62.5
        assert outline.improvements[0].replacement
    else:
        assert [check.status for check in outline.checks] == [
            "review",
            "info",
            "pass",
            "not_assessable",
        ]


@pytest.mark.parametrize("kind", ["interview", "cv"])
@pytest.mark.parametrize("language", ["en", "it"])
def test_exports_keep_section_order_and_shorten_technical_hashes(kind: str, language: str) -> None:
    case = json.loads(FIXTURE.read_text())[kind]
    report = replace(ReportData.model_validate(case["report"]).domain(), language=language)
    outline = report_outline(report, {})
    md = markdown(report)
    html = report_html(report)
    assert re.findall(r'<section id="([^"]+)"', html) == list(outline.sections)
    headings = re.findall(r"^## (.+)$", md, re.M)
    assert headings[: len(outline.sections)] == [
        section_label(key, language) for key in outline.sections
    ]
    for full_hash in (report.rubric_hash, report.input_fingerprint):
        assert full_hash not in md
        assert full_hash not in html
        assert md.index(full_hash[:8]) > md.index(section_label("technical", language))
    assert "Judgements differ" not in markdown(report)
    assert "Judgements differ" not in report_html(report)
    if report.scores:
        unstable = replace(report, scores=(replace(report.scores[0], unstable=True),))
        assert ("Judgements differ" if language == "en" else "I giudizi differiscono") in markdown(
            unstable
        )
    for note in report.observations:
        assert html.count(note.text) == 1
