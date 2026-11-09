from dataclasses import asdict, replace

import pytest

from probeloop.assessment.application.schemas import ReportData
from probeloop.assessment.application.score_scale import anchored_score, score_100
from probeloop.assessment.domain.model import Evidence, Score
from probeloop.assessment.infrastructure.exports import export_report
from tests.assessment.test_exports import sample_report


@pytest.mark.parametrize(
    ("raw", "expected"), [(1, 0), (3, 50), (5, 100), (3.33, 58.25), (None, None)]
)
def test_scale_preserves_anchors_missing_values_and_precision(
    raw: float | None, expected: float | None
) -> None:
    assert score_100(raw) == expected
    assert anchored_score(expected) == raw


def test_legacy_and_new_json_roundtrip_without_changing_assessment_meaning() -> None:
    report = replace(
        sample_report(),
        scores=(Score("a", "Accuracy", 3.33, "Reason", (Evidence("a", "Quote"),)),),
        overall=3.33,
    )
    legacy = ReportData.model_validate(asdict(report))
    public = ReportData.of(report)
    assert legacy.scale == "1_5"
    assert public.scale == "0_100"
    assert public.overall == 58.25
    assert public.scores[0].value == 58.25
    assert legacy.domain() == public.domain() == report
    assert ReportData.model_validate_json(public.model_dump_json()).domain() == report
    assert b'"scale": "0_100"' in export_report(report, "json")


def test_zero_is_an_observed_lowest_anchor_not_a_missing_score() -> None:
    report = replace(
        sample_report(),
        overall=1,
        scores=(Score("a", "Accuracy", 1, "Reason", (Evidence("a", "Quote"),)),),
    )
    assert ReportData.of(report).overall == 0
    assert ReportData.of(report).domain().scores[0].value == 1
