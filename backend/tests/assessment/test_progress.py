from __future__ import annotations

from dataclasses import replace

from probeloop.assessment.domain.model import Evidence, ReportKind, Score
from probeloop.assessment.domain.progress import (
    comparison_key,
    latest_reports,
    progress_groups,
    scorer_key,
)
from tests.assessment.test_exports import sample_report


def test_regeneration_does_not_create_an_extra_practice_point() -> None:
    evidence = (Evidence("turn-1", "A synthetic answer.", 1),)
    score = Score("technical.accuracy", "Accuracy", 3, "1/1", evidence)
    first = replace(
        sample_report(),
        id="a",
        subject_id="one",
        created_at=1,
        scores=(score,),
        unit_scores=(replace(score, unit_id="u0"),),
        overall=3,
    )
    regenerated = replace(first, id="b", version=2, created_at=3)
    second = replace(
        first,
        id="c",
        subject_id="two",
        created_at=2,
        overall=None,
        scores=(replace(score, value=None),),
    )
    groups = progress_groups([first, regenerated, second])
    assert len(groups) == 1
    assert len(groups[0].points) == 2
    assert [p.report_id for p in groups[0].points] == ["c", "b"]
    assert groups[0].points[0].values["technical.accuracy"] is None
    assert groups[0].points[1].evidence_counts["technical.accuracy"] == 1
    assert len(latest_reports([first, regenerated, second])) == 2


def test_rubric_content_model_prompt_language_and_criteria_must_match() -> None:
    report = sample_report()
    variants = [
        replace(report, rubric_hash="changed"),
        replace(report, rubric_id="interview.v2"),
        replace(report, model_ref="another"),
        replace(report, prompt_ref="judge@v2"),
        replace(report, language="it"),
        replace(report, scores=(Score("another", "Another", None, "Not elicited"),)),
    ]
    assert all(comparison_key(report) != comparison_key(item) for item in variants)
    cv = replace(report, kind=ReportKind.CV, subject_id="snapshot", session_id=None)
    assert {g.kind for g in progress_groups([report, cv])} == {"interview", "cv"}


def test_the_scorer_key_ignores_the_criteria_only() -> None:
    evidence = (Evidence("turn-1", "A synthetic answer.", 1),)
    accuracy = Score("technical.accuracy", "Accuracy", 3, "1/1", evidence)
    clarity = Score("communication.clarity", "Clarity", 4, "1/1", evidence)
    first = replace(sample_report(), id="a", subject_id="one", scores=(accuracy,))
    other = replace(first, id="b", subject_id="two", created_at=1, scores=(clarity,))
    assert comparison_key(first) != comparison_key(other)
    assert scorer_key(first) == scorer_key(other)
    assert scorer_key(first) != scorer_key(replace(first, model_ref="another"))
    assert scorer_key(first) != scorer_key(replace(first, kind=ReportKind.CV))

    groups = progress_groups([first, other], {"synthetic": "technical"})
    assert len(groups) == 2
    assert len({g.scorer_key for g in groups}) == 1
    assert [p.interview_type for g in groups for p in g.points] == ["technical", "technical"]
    assert progress_groups([first])[0].points[0].interview_type is None  # type unknown
