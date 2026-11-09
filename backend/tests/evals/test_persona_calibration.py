"""Persona calibration metrics, computed on constructed evaluator results."""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest
from evals.persona_calibration import (
    Answer,
    Assessment,
    answers_digest,
    assessment_of,
    checked_audit,
    contains,
    saved_answers,
    session_for,
    summary,
    traits_present,
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


def test_persona_traits_are_checked_in_code() -> None:
    card = {"wrong_claim": CLAIM}
    assert traits_present(f"The team added one. {CLAIM}", card, "weak")
    assert not traits_present(f"I added one. {CLAIM}", card, "weak")
    assert not traits_present(f"We cut latency by 30%. {CLAIM}", card, "weak")
    assert not traits_present("The team added an index.", card, "weak")
    assert traits_present("I measured both before I added it.", card, "strong")
    assert not traits_present(f"I measured it. {CLAIM}", card, "strong")
    assert not traits_present("We measured it.", card, "strong")


def _assessment(persona: str, regeneration: int, mean: float, **fields: object) -> Assessment:
    base = Assessment(
        card="indexes",
        persona=persona,
        regeneration=regeneration,
        mean=mean,
        accuracy=None,
        experience=None,
        ownership=None,
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
        Answer("indexes", "weak", "q", CLAIM, True, 1),
        Answer("indexes", "strong", "q", "A correct answer.", True, 2),
    ]
    assessments = [
        _assessment("weak", 0, 1.5, corrections=("removes the need to update the table",)),
        _assessment("weak", 1, 1.8, accuracy=2.0, ownership=1.0),
        _assessment("strong", 0, 4.2),
        _assessment("strong", 1, 1.6, corrections=("leave an invalid index",)),
    ]
    result = summary(answers, assessments, {"indexes": CLAIM})
    # Wrong claim found twice, vague ownership once: 3 of 4 planted problems.
    assert result["detection"] == 0.75
    assert result["technical_detection"] == 1
    assert result["ownership_detection"] == 0.5
    assert result["ranking"] == 0.5
    assert result["spreads"] == {"indexes/weak": 0.3, "indexes/strong": 2.6}
    assert result["corrections_on_strong"] == 1
    assert result["persona_attempts"] == 3
    assert result["passed"] is False


def test_answers_without_their_traits_are_excluded_and_reported() -> None:
    answers = [
        Answer("indexes", "weak", "q", "The persona ignored the trait.", False, 3),
        Answer("indexes", "strong", "q", "A correct answer.", True, 1),
    ]
    assessments = [_assessment("weak", 0, 1.0), _assessment("strong", 0, 4.0)]
    result = summary(answers, assessments, {"indexes": CLAIM})
    assert result["detection"] is None
    assert result["ranking"] is None
    assert result["non_compliant"] == ["indexes/weak"]
    assert result["passed"] is False


def test_assessment_reads_scores_corrections_and_unverified_quotes() -> None:
    answer = Answer("indexes", "weak", "q", f"We did it together. {CLAIM}", True, 1)
    quote = Evidence("turn-1", "removes the need to update the table", 1)
    result = InterviewJudgement(
        units=(),
        unit_scores=(
            Score("technical.accuracy", "Accuracy", 1, "Wrong.", (quote,), unit_id="u0"),
            Score("technical.experience", "Experience", None, "Not shown.", unit_id="u0"),
            Score("technical.ownership", "Contribution", 1, "Unclear.", (quote,), unit_id="u0"),
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
    assert item.ownership == 1
    assert item.corrections == ("removes the need to update the table",)
    assert item.unverified == 1
    assert (item.assessed, item.criteria, item.duration_s) == (2, 3, 12.35)


def test_experience_does_not_substitute_for_the_contribution_criterion() -> None:
    answers = [Answer("indexes", "weak", "q", CLAIM, True, 1)]
    item = _assessment("weak", 0, 2.0, accuracy=1, experience=1, ownership=5)
    result = summary(answers, [item], {"indexes": CLAIM})
    assert result["detection"] == 0.5
    assert result["technical_detection"] == 1
    assert result["ownership_detection"] == 0


def test_reused_answers_are_checked_again_and_cannot_hide_missing_pairs(tmp_path: Path) -> None:
    weak = Answer("indexes", "weak", "q", "We added one. " + CLAIM, False, 1)
    strong = Answer("indexes", "strong", "q", "I measured the workload.", False, 1)
    path = tmp_path / "run.json"
    cards = [{"id": "indexes", "question": "q", "wrong_claim": CLAIM}]
    record = {"persona_model": "synthetic-model", "answers": [asdict(weak), asdict(strong)]}
    path.write_text(json.dumps(record))
    answers, model, prompt = saved_answers(path, cards)
    assert all(a.compliant for a in answers)
    assert [a.text for a in answers] == [weak.text, strong.text]
    assert model == "synthetic-model"
    assert prompt == "persona@v1"
    record["answers"] = [asdict(weak), asdict(weak)]
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="exactly once"):
        saved_answers(path, cards)
    record["answers"] = [asdict(weak), asdict(replace(strong, question="Different question"))]
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="different question"):
        saved_answers(path, cards)


def test_answer_audits_cannot_be_reused_for_changed_or_unreviewed_inputs(tmp_path: Path) -> None:
    answer = Answer("indexes", "strong", "q", "I measured the workload.", True, 1)
    path = tmp_path / "audit.json"
    record = {
        "answers_sha256": answers_digest([answer]),
        "checks": [
            {
                "card": "indexes",
                "persona": "strong",
                "label_verified": True,
                "notes": "Synthetic review note.",
                "sources": ["https://www.postgresql.org/docs/current/indexes.html"],
            }
        ],
    }
    path.write_text(json.dumps(record))
    assert checked_audit(path, [answer]) == record
    with pytest.raises(ValueError, match="does not match"):
        checked_audit(path, [replace(answer, text="Different answer")])
    record["checks"][0]["label_verified"] = False  # type: ignore[index]
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="verified traits"):
        checked_audit(path, [answer])
