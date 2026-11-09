from __future__ import annotations

from probeloop.ai.fake import FakeChatModel
from probeloop.assessment.application.interview_review import InterviewReviewer
from probeloop.assessment.application.labels import label
from probeloop.assessment.application.rubrics import load_rubric
from tests.assessment.test_interview import AGREE, _review, _script


def test_technical_v2_adds_contribution_without_rewriting_v1_anchors() -> None:
    legacy = load_rubric("technical")
    current = load_rubric("technical", version=2)
    assert current.criteria[:-1] == legacy.criteria
    assert current.criteria[-1].id == "ownership"
    assert current.ref == "technical.v2"
    assert legacy.ref == "technical.v1"
    assert current.digest != legacy.digest
    assert label(current.criteria[-1].label, "it") == "Contributo personale"
    reviewer = InterviewReviewer(FakeChatModel([]))
    assert reviewer.rubrics["technical"] == current
    assert "technical.v2" in reviewer.rubric_ref


async def test_contribution_is_available_only_when_a_past_example_was_requested() -> None:
    result = await _review(FakeChatModel([_script(AGREE, [])]))
    ownership = {
        s.unit_id: s for s in result.unit_scores if s.criterion_id == "technical.ownership"
    }
    assert ownership["u4"].value == 4
    assert ownership["u4"].evidence
    assert ownership["u6"].value is None
    assert ownership["u6"].evidence == ()
    assert ownership["u6"].reason == "No question asked for a past example."
