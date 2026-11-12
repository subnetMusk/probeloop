"""Read models for the history: each interview and each CV check with its latest report."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from probeloop.assessment.domain.model import Report, ReportKind
from probeloop.assessment.domain.progress import latest_reports, scorer_key
from probeloop.context.domain.model import ContextSnapshot
from probeloop.interview.application.ports import SessionSummary


@dataclass(frozen=True, slots=True)
class LatestReport:
    """The latest version of the reports on one subject, and how many versions exist."""

    id: str
    subject_id: str
    version: int
    versions: int
    created_at: float
    overall: float | None
    assessed: int
    criteria: int
    language: str
    model_ref: str
    scorer_key: str = ""
    profile_id: str | None = None


@dataclass(frozen=True, slots=True)
class InterviewEntry:
    session: SessionSummary
    report: LatestReport | None


@dataclass(frozen=True, slots=True)
class CvCheckEntry:
    snapshot: ContextSnapshot
    report: LatestReport


def latest_by_subject(reports: Iterable[Report], kind: ReportKind) -> dict[str, LatestReport]:
    of_kind = [r for r in reports if r.kind is kind]
    versions = Counter(r.subject_id for r in of_kind)
    return {
        r.subject_id: LatestReport(
            id=r.id,
            subject_id=r.subject_id,
            version=r.version,
            versions=versions[r.subject_id],
            created_at=r.created_at,
            overall=r.overall,
            assessed=r.assessed,
            criteria=r.criteria,
            language=r.language,
            model_ref=r.model_ref,
            scorer_key=scorer_key(r),
            profile_id=r.profile_id,
        )
        for r in latest_reports(of_kind)
    }


def interview_history(
    sessions: Iterable[SessionSummary], reports: Iterable[Report]
) -> list[InterviewEntry]:
    """Every interview, newest first, with its latest report when there is one."""
    latest = latest_by_subject(reports, ReportKind.INTERVIEW)
    ordered = sorted(sessions, key=lambda s: s.created_at, reverse=True)
    return [InterviewEntry(session, latest.get(session.id)) for session in ordered]
