"""Persona calibration metrics, computed on constructed evaluator results."""

from __future__ import annotations

from dataclasses import replace

from evals.persona_calibration import (
    Answer,
    Assessment,
    assessment_of,
    contains,
    session_for,
    summary,
)

from probeloop.assessment.application.interview_review import InterviewJudgement
from probeloop.assessment.application.segmentation import answer_units
from probeloop.assessment.domain.model import Evidence, Observation, Score

CLAIM = "An index always makes inserts faster because it removes the need to update the table."


def test_a_persona_answer_becomes_one_scored_unit_and_an_unscored_closing() -> None:
    units = answer_units(session_for("How do indexes affect writes?", "Some answer text."))
    assert [len(u.answer_seqs) for u in units] == [1, 1]
    assert units[-1].kind == "logistics"


def test_the_planted_claim_must_be_present_verbatim() -> None:
    assert contains(
        "Well,  an INDEX always makes inserts faster because it removes the need "
        "to update the table, as we saw.",
        CLAIM,
    )
    assert not contains("Indexes make inserts faster.", CLAIM)


def _assessment(persona: str, regeneration: int, mean: float, **fields: object) -> Assessment:
    base = Assessment(
        card="indexes",
        persona=persona,
        regeneration=regeneration,
        mean=mean,
        accuracy=None,
        experience=None,
        corrections=(),
        unverified=0,
        assessed=4,
        criteria=6,
        dropped=0,
        duration_s=30.0,
    )
    return replace(base, **fields)


def test_summary_counts_detection_ranking_spread_and_false_corrections() -> None:
    answers = [
        Answer("indexes", "weak", "q", CLAIM, True),
        Answer("indexes", "strong", "q", "A correct answer.", None),
    ]
    assessments = [
        _assessment("weak", 0, 1.5, corrections=("removes the need to update the table",)),
        _assessment("weak", 1, 1.8, accuracy=2.0, experience=1.0),
        _assessment("strong", 0, 4.2),
        _assessment("strong", 1, 1.6, corrections=("leave an invalid index",)),
    ]
    result = summary(answers, assessments, {"indexes": CLAIM})
    # Wrong claim found twice, vague ownership once: 3 of 4 planted problems.
    assert result["detection"] == 0.75
    assert result["ranking"] == 0.5
    assert result["spreads"] == {"indexes/weak": 0.3, "indexes/strong": 2.6}
    assert result["false_corrections"] == 1
    assert result["passed"] is False


def test_answers_without_the_planted_claim_are_excluded_and_reported() -> None:
    answers = [
        Answer("indexes", "weak", "q", "The persona ignored the trait.", False),
        Answer("indexes", "strong", "q", "A correct answer.", None),
    ]
    assessments = [_assessment("weak", 0, 1.0), _assessment("strong", 0, 4.0)]
    result = summary(answers, assessments, {"indexes": CLAIM})
    assert result["detection"] is None
    assert result["ranking"] is None
    assert result["missing_planted_claims"] == ["indexes"]
    assert result["passed"] is False


def test_assessment_reads_scores_corrections_and_unverified_quotes() -> None:
    answer = Answer("indexes", "weak", "q", f"We did it together. {CLAIM}", True)
    quote = Evidence("turn-1", "removes the need to update the table", 1)
    result = InterviewJudgement(
        units=(),
        unit_scores=(
            Score("technical.accuracy", "Accuracy", 1, "Wrong.", (quote,), unit_id="u0"),
            Score("technical.experience", "Experience", None, "Not shown.", unit_id="u0"),
        ),
        scores=(),
        observations=(
            Observation("technical_error", "Correction.", (quote,), unit_id="u0"),
            Observation("improvement", "Invented.", (Evidence("turn-1", "I led ten people"),)),
        ),
        dropped=2,
        coverage=(),
    )
    item = assessment_of(answer, 0, result, 12.346)
    assert item.mean == 1
    assert item.accuracy == 1
    assert item.experience is None
    assert item.corrections == ("removes the need to update the table",)
    assert item.unverified == 1
    assert (item.assessed, item.criteria, item.duration_s) == (1, 2, 12.35)
