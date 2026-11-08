from __future__ import annotations

from dataclasses import replace

from probeloop.assessment.application.history import interview_history, latest_by_subject
from probeloop.assessment.domain.model import ReportKind
from probeloop.interview.application.ports import SessionSummary
from probeloop.interview.domain.model import SessionStatus
from tests.assessment.test_exports import sample_report


def summary(session_id: str, created_at: float) -> SessionSummary:
    return SessionSummary(session_id, created_at, SessionStatus.ENDED, "technical", "it")


def test_each_subject_shows_its_latest_report_and_how_many_versions_exist() -> None:
    first = replace(sample_report(), id="a", subject_id="one", created_at=1, overall=3)
    second = replace(first, id="b", version=2, created_at=5, overall=4)
    cv = replace(first, id="c", kind=ReportKind.CV, subject_id="snapshot", session_id=None)
    latest = latest_by_subject([second, first, cv], ReportKind.INTERVIEW)
    assert list(latest) == ["one"]
    assert (latest["one"].id, latest["one"].version, latest["one"].versions) == ("b", 2, 2)
    assert latest["one"].overall == 4
    assert latest_by_subject([first, cv], ReportKind.CV)["snapshot"].versions == 1


def test_interviews_are_listed_newest_first_with_or_without_a_report() -> None:
    report = replace(sample_report(), id="r", subject_id="old", session_id="old")
    entries = interview_history([summary("old", 1), summary("new", 2)], [report])
    assert [e.session.id for e in entries] == ["new", "old"]
    assert entries[0].report is None
    assert entries[1].report is not None
    assert entries[1].report.id == "r"
