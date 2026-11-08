from __future__ import annotations

from dataclasses import replace

import pytest

from probeloop.context.application.snapshots import (
    candidate_brief,
    job_brief,
    snapshot_of,
    vocabulary_prompt,
)
from probeloop.context.domain.model import (
    ContextError,
    Document,
    DocumentKind,
    DocumentOrigin,
    Fact,
    FactKind,
    FactOrigin,
    JobMode,
    MatchStatus,
    Preparation,
    PreparationStatus,
    Profile,
    RequirementMatch,
    Review,
    Subject,
    TargetArea,
)
from tests.context.conftest import cv, offer

ROLE = Fact(
    "f1", Subject.CANDIDATE, FactKind.ROLE, "Backend a Logistica Veloce.", FactOrigin.DECLARED
)
GUESS = Fact("f2", Subject.CANDIDATE, FactKind.SKILL, "Kafka.", FactOrigin.INFERRED)
PYTHON = Fact("r1", Subject.JOB, FactKind.REQUIREMENT, "5 anni di Python.", FactOrigin.DECLARED)
KAFKA = Fact("r2", Subject.JOB, FactKind.REQUIREMENT, "Kafka.", FactOrigin.DECLARED)


def in_review(job_mode: JobMode = JobMode.OFFER) -> Preparation:
    documents = [cv(), offer()] if job_mode is not JobMode.NONE else [cv()]
    p = Preparation(id="p1", created_at=0, language="it", job_mode=job_mode, documents=documents)
    matches = [
        RequirementMatch("r1", MatchStatus.PARTIAL, ("f1",), "Python ma meno anni."),
        RequirementMatch("r2", MatchStatus.NOT_SHOWN),
    ]
    area = TargetArea("backend", "mid") if job_mode is JobMode.NONE else None
    p.analysed([ROLE, GUESS, PYTHON, KAFKA], matches, area, ("Python", "FastAPI"))
    return p


def test_documents_need_a_title_and_text() -> None:
    with pytest.raises(ContextError, match="title"):
        replace(cv(), title=" ")
    with pytest.raises(ContextError, match="no text"):
        replace(cv(), text="  \n")


def test_the_job_offer_goes_with_the_job_mode() -> None:
    with pytest.raises(ContextError, match="job offer"):
        Preparation("p", 0, "it", JobMode.NONE, [cv(), offer()])
    with pytest.raises(ContextError, match="job offer"):
        Preparation("p", 0, "it", JobMode.OFFER, [cv()])
    with pytest.raises(ContextError, match="one CV"):
        Preparation("p", 0, "it", JobMode.NONE, [cv(), cv()])


def test_profiles_hold_resources_only() -> None:
    resource = Document("d", DocumentKind.RESOURCE, "Note", DocumentOrigin.TYPED, "testo", 0)
    Profile("p", "Il mio profilo", (resource,), 0, 0)
    with pytest.raises(ContextError, match="resource documents"):
        Profile("p", "Il mio profilo", (cv(),), 0, 0)


def test_the_review_confirms_corrects_excludes_and_adds() -> None:
    p = in_review()
    p.review_fact("f1", Review.CORRECTED, "Backend senior a Logistica Veloce.")
    p.review_fact("f2", Review.EXCLUDED)
    with pytest.raises(ContextError, match="corrected statement"):
        p.review_fact("f1", Review.CORRECTED, " ")
    with pytest.raises(ContextError, match="unknown fact"):
        p.review_fact("zz", Review.CONFIRMED)
    p.add_fact(Fact("u1", Subject.CANDIDATE, FactKind.SKILL, "Go.", FactOrigin.USER))
    with pytest.raises(ContextError, match="only the user"):
        p.add_fact(GUESS)

    assert [f.text for f in p.included_facts(Subject.CANDIDATE)] == [
        "Backend senior a Logistica Veloce.",
        "Go.",
    ]
    p.approve("s1")
    assert p.status is PreparationStatus.APPROVED
    with pytest.raises(ContextError, match="not in review"):
        p.review_fact("f1", Review.CONFIRMED)


def test_an_approved_context_can_be_reopened_and_approved_again() -> None:
    p = in_review()
    p.reopen()  # already in review: nothing changes
    assert p.status is PreparationStatus.REVIEW
    first = snapshot_of(p, "s1", now=1)
    p.approve(first.id)
    p.reopen()
    assert (p.status, p.snapshot_id) == (PreparationStatus.REVIEW, None)
    assert snapshot_of(p, "s2", now=2).content_hash == first.content_hash
    p.review_fact("f2", Review.EXCLUDED)
    assert snapshot_of(p, "s3", now=3).content_hash != first.content_hash
    p.approve("s3")
    assert p.snapshot_id == "s3"

    analysing = Preparation("p", 0, "it", JobMode.OFFER, [cv(), offer()])
    with pytest.raises(ContextError, match="not approved"):
        analysing.reopen()
    analysing.failed("boom")
    with pytest.raises(ContextError, match="not approved"):
        analysing.reopen()


def test_the_area_can_be_set_only_without_a_job_offer() -> None:
    with pytest.raises(ContextError, match="only without a job offer"):
        in_review().set_area("data", "senior")
    p = in_review(JobMode.NONE)
    p.set_area(" data engineering ", "senior")
    assert p.area == TargetArea("data engineering", "senior", "", confirmed=True)
    p.approve("s1")
    with pytest.raises(ContextError, match="confirm the professional area"):
        in_review(JobMode.NONE).approve("s2")


def test_generated_offers_cannot_be_presented_as_real_postings() -> None:
    generated = replace(offer(), origin=DocumentOrigin.GENERATED)
    with pytest.raises(ContextError, match="labelled as generated"):
        Preparation("p", 0, "it", JobMode.OFFER, [cv(), generated])
    with pytest.raises(ContextError, match="labelled as generated"):
        Preparation("p", 0, "it", JobMode.GENERATED, [cv(), offer()])
    Preparation("p", 0, "it", JobMode.GENERATED, [cv(), generated])


def test_snapshots_hash_their_content_only() -> None:
    first = snapshot_of(in_review(), "s1", now=1)
    second = snapshot_of(in_review(), "s2", now=2)
    assert first.content_hash == second.content_hash
    changed = in_review()
    changed.review_fact("f2", Review.EXCLUDED)
    excluded = snapshot_of(changed, "s3", now=3)
    assert excluded.content_hash != first.content_hash
    assert [f.id for f in excluded.candidate_facts] == ["f1"]


def test_briefs_label_inferred_facts_and_list_missing_requirements() -> None:
    snapshot = snapshot_of(in_review(), "s1", now=1)
    brief = candidate_brief(snapshot)
    assert "Role:\n- Backend a Logistica Veloce." in brief
    assert "- Kafka. (inferred, not literally stated)" in brief
    job = job_brief(snapshot)
    assert "Requirements the candidate's documents do not show:\n- Kafka." in job
    assert "Requirements the documents show only in part:\n- 5 anni di Python." in job

    without_offer = snapshot_of(in_review(JobMode.NONE), "s2", now=1)
    assert "There is no job offer" in job_brief(without_offer)
    assert "backend (mid)" in job_brief(without_offer)


def test_review_withdraws_matches_whose_evidence_changed() -> None:
    p = in_review()
    p.review_fact("f1", Review.EXCLUDED)
    assert p.matches[0].status is MatchStatus.NOT_SHOWN
    assert p.matches[0].fact_ids == ()
    p.review_fact("r2", Review.EXCLUDED)
    assert [m.requirement_id for m in p.matches] == ["r1"]

    p = in_review()
    p.review_fact("f1", Review.CORRECTED, "A different role.")
    assert p.matches[0].status is MatchStatus.NOT_SHOWN
    assert "A different role. (corrected by the candidate)" in candidate_brief(
        snapshot_of(p, "s", 0)
    )


def test_snapshot_hash_does_not_depend_on_analysis_ids() -> None:
    p = in_review()
    first = snapshot_of(p, "s1", 1)
    p.id = "another-preparation"
    p.facts = [replace(f, id=f"new-{f.id}") for f in p.facts]
    p.matches = [
        replace(
            m,
            requirement_id=f"new-{m.requirement_id}",
            fact_ids=tuple(f"new-{i}" for i in m.fact_ids),
        )
        for m in p.matches
    ]
    assert snapshot_of(p, "s2", 2).content_hash == first.content_hash


def test_the_vocabulary_prompt_fits_its_budget() -> None:
    assert vocabulary_prompt(()) is None
    assert vocabulary_prompt(("Python", "FastAPI")) == "Python, FastAPI"
    long = tuple(f"Term{n}" for n in range(200))
    assert len(vocabulary_prompt(long, max_chars=100) or "") <= 100
