"""The CV check with a selected line classifier: it reads headings and measured outcomes."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Any

import pytest

from probeloop.ai.fake import FakeChatModel
from probeloop.assessment.application.cv_checks import LineReadings, cv_checks, section_of
from probeloop.assessment.application.cv_review import CvReviewer
from probeloop.assessment.application.rubrics import load_rubric
from probeloop.assessment.application.service import CV_REVIEW_JOB, AssessmentService
from probeloop.context.application.ports import (
    Classified,
    LineReading,
    ObligationReading,
    OfferLine,
    TextClassifierUnavailable,
)
from probeloop.context.application.snapshots import snapshot_of
from probeloop.context.domain.lines import logical_lines
from probeloop.context.domain.model import ContextSnapshot, Document
from probeloop.platform.jobs import Job, JobError, JobStatus
from tests.assessment.test_cv import cv_response
from tests.context.test_preparation import in_review

CV = """Giulia Verdi
giulia.verdi@example.test

E S P E R I E N Z A   P R O F E S S I O N A L E
Responsabile turni, Magazzino Nord, 2019 - 2023
- Coordinato 35 operatori su tre turni.
- Ridotto il tempo di risposta dell'API a 380 ms.

Progetti
- Portale interno per le consegne.

I S T R U Z I O N E :
Diploma di perito informatico, 2014 - 2019

Competenze tecniche.
Python, SQL

Lingue
Inglese B2
"""
LETTER_SPACED = "E S P E R I E N Z A   P R O F E S S I O N A L E"
HEADINGS = frozenset(
    {LETTER_SPACED, "Progetti", "I S T R U Z I O N E :", "Competenze tecniche.", "Lingue"}
)
MEASURED = frozenset(
    {
        "- Coordinato 35 operatori su tre turni.",
        "- Ridotto il tempo di risposta dell'API a 380 ms.",
    }
)
HEADING_REF = "typesafe:jev-test:cv.heading.v2:threshold=0.6"
QUANTIFIED_REF = "typesafe:jev-test:cv.quantified.v2:threshold=0.5"


def classified(lines: Sequence[str], positive: frozenset[str], ref: str) -> Classified[LineReading]:
    return Classified(
        tuple(LineReading(line in positive, 0.9 if line in positive else 0.1) for line in lines),
        ref,
    )


def readings(
    headings: frozenset[str] = HEADINGS, measured: frozenset[str] = MEASURED
) -> LineReadings:
    lines = tuple(logical_lines(CV))
    return LineReadings(
        lines,
        classified(lines, headings, HEADING_REF),
        classified(lines, measured, QUANTIFIED_REF),
    )


def document() -> Document:
    return replace(in_review().documents[0], text=CV)


def test_lines_read_as_headings_name_sections_in_any_spacing_case_or_punctuation() -> None:
    checks = {c.id: c for c in cv_checks(document(), "en", readings())}

    assert checks["section_experience"].status == "pass"
    assert [e.quote for e in checks["section_experience"].evidence] == [LETTER_SPACED]
    assert checks["section_education"].status == "pass"
    assert [e.quote for e in checks["section_education"].evidence] == ["I S T R U Z I O N E :"]
    assert checks["section_skills"].status == "pass"
    assert [e.quote for e in checks["section_skills"].evidence] == ["Competenze tecniche."]


def test_projects_name_the_experience_section() -> None:
    checks = {c.id: c for c in cv_checks(document(), "it", readings(HEADINGS - {LETTER_SPACED}))}

    assert checks["section_experience"].status == "pass"
    assert [e.quote for e in checks["section_experience"].evidence] == ["Progetti"]


@pytest.mark.parametrize(
    ("heading", "section"),
    [
        ("ESPERIENZE DI TIROCINIO", "experience"),
        ("PROGETTI DI SVILUPPO SOFTWARE", "experience"),
        ("Work history", "experience"),
        ("E S P E R I E N Z E", "experience"),
        ("Formazione e certificazioni", "education"),
        ("COMPETENZE TECNICHE", "skills"),
        ("Competenze linguistiche", "skills"),
        ("CERTIFICAZIONI E LINGUE", None),
        ("Hobby", None),
    ],
)
def test_a_heading_names_a_section_by_the_words_it_starts_with(
    heading: str, section: str | None
) -> None:
    assert section_of(heading) == section


def test_the_classifier_decides_whether_a_line_is_a_heading() -> None:
    not_a_heading = readings(HEADINGS - {"Competenze tecniche."})
    checks = {c.id: c for c in cv_checks(document(), "en", not_a_heading)}

    assert checks["section_skills"].status == "review"
    assert checks["section_skills"].evidence == ()


def test_measured_lines_are_counted_whatever_their_unit() -> None:
    checks = {c.id: c for c in cv_checks(document(), "en", readings())}

    quantification = checks["quantification"]
    assert quantification.status == "info"
    assert quantification.detail == "Lines stating a measured outcome or scope: 2"
    assert [e.quote for e in quantification.evidence] == [
        "- Coordinato 35 operatori su tre turni.",
        "- Ridotto il tempo di risposta dell'API a 380 ms.",
    ]


def test_measured_lines_quote_at_most_five() -> None:
    lines = tuple(f"- Gestito {n} ordini al giorno." for n in range(7))
    lines_read = LineReadings(
        lines,
        classified(lines, frozenset(), HEADING_REF),
        classified(lines, frozenset(lines), QUANTIFIED_REF),
    )
    checks = {c.id: c for c in cv_checks(document(), "en", lines_read)}

    assert checks["quantification"].detail.endswith(": 7")
    assert [e.quote for e in checks["quantification"].evidence] == list(lines[:5])


def test_the_line_reader_is_recorded_with_its_wordings_and_thresholds() -> None:
    checks = {c.id: c for c in cv_checks(document(), "it", readings())}

    reader = checks["line_reader"]
    assert reader.status == "info"
    assert reader.detail.endswith(f"Modelli: {HEADING_REF}; {QUANTIFIED_REF}")
    assert reader.evidence == ()


def test_without_readings_exact_patterns_still_decide() -> None:
    checks = {c.id: c for c in cv_checks(document(), "en")}

    assert "line_reader" not in checks
    assert checks["section_experience"].status == "review"
    assert checks["section_education"].status == "review"
    assert checks["section_skills"].status == "review"
    assert checks["quantification"].detail == "Numerical outcome or scope measures detected: 0"


class Lines:
    """Reads the synthetic CV's headings and measured outcomes, and records what it was asked."""

    def __init__(self, error: str | None = None) -> None:
        self.error = error
        self.asked: list[tuple[str, tuple[str, ...]]] = []

    async def obligations(self, lines: Sequence[OfferLine]) -> Classified[ObligationReading]:
        raise AssertionError("not used by the CV check")

    async def headings(self, lines: Sequence[str]) -> Classified[LineReading]:
        self.asked.append(("headings", tuple(lines)))
        if self.error:
            raise TextClassifierUnavailable(self.error)
        return classified(lines, HEADINGS, HEADING_REF)

    async def quantified(self, lines: Sequence[str]) -> Classified[LineReading]:
        self.asked.append(("quantified", tuple(lines)))
        return classified(lines, MEASURED, QUANTIFIED_REF)


def snapshot() -> ContextSnapshot:
    taken = snapshot_of(in_review(), "snapshot", 0)
    return replace(taken, documents=(replace(taken.documents[0], text=CV),))


async def unreported(fraction: float, message: str | None) -> None:
    pass


async def test_the_classifier_is_asked_only_when_it_is_selected() -> None:
    jev = Lines()
    selected = {"classification": "rules"}
    reviewer = CvReviewer(
        FakeChatModel([cv_response({}, []), cv_response({}, [])]),
        load_rubric("cv"),
        classifier=lambda: jev if selected["classification"] == "jev" else None,
    )

    _, _, checks, _ = await reviewer.review(snapshot(), "en", unreported)
    assert jev.asked == []
    assert "line_reader" not in {c.id for c in checks}

    selected["classification"] = "jev"
    _, _, checks, _ = await reviewer.review(snapshot(), "en", unreported)
    lines = tuple(logical_lines(CV))
    assert jev.asked == [("headings", lines), ("quantified", lines)]
    by_id = {c.id: c for c in checks}
    assert by_id["section_experience"].status == "pass"
    assert by_id["quantification"].detail == "Lines stating a measured outcome or scope: 2"
    assert by_id["line_reader"].status == "info"


async def test_an_unavailable_classifier_fails_the_check_with_its_message() -> None:
    message = "Jev is unreachable; check the connection and try again"
    model = FakeChatModel([cv_response({}, [])])
    jev = Lines(error=message)

    async def taken(snapshot_id: str) -> ContextSnapshot:
        return snapshot()

    unused: Any = None
    service = AssessmentService(
        store=unused,
        reviewer=CvReviewer(model, load_rubric("cv"), classifier=lambda: jev),
        snapshot=taken,
        submit=unused,
        now=lambda: 0.0,
        new_id=lambda: "id",
        sessions=unused,
        interviewer=unused,
        delivery=unused,
        jobs=unused,
        discard_snapshot=unused,
    )
    job = Job(
        id="j",
        kind=CV_REVIEW_JOB,
        subject_id="snapshot",
        status=JobStatus.RUNNING,
        created_at=0,
        payload={"language": "en"},
    )

    with pytest.raises(JobError) as raised:
        await service.review_cv(job, unreported)

    # No silent fallback to the exact patterns, and no model call for a check that cannot finish.
    assert str(raised.value) == message
    assert model.requests == []
