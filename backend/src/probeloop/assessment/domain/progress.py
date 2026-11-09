"""Latest-report progress groups with explicit comparability boundaries and no imputation.

A group holds the reports whose scores can be compared criterion by criterion: same kind,
rubric, model, prompt, language and criteria. The scorer key leaves the criteria out, so that
a chart of overall scores may join groups whose scorer is the same while each interview covers
different criteria.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass

from probeloop.assessment.domain.model import Report, ReportKind


@dataclass(frozen=True, slots=True)
class ProgressPoint:
    report_id: str
    subject_id: str
    session_id: str | None
    created_at: float
    version: int
    overall: float | None
    values: dict[str, float | None]
    evidence_counts: dict[str, int]
    interview_type: str | None = None  # interview reports only


@dataclass(frozen=True, slots=True)
class ProgressGroup:
    id: str
    scorer_key: str
    kind: str
    rubric_id: str
    rubric_hash: str
    model_ref: str
    language: str
    criteria: dict[str, str]
    points: tuple[ProgressPoint, ...]


def comparison_key(report: Report) -> str:
    content = [*_scorer(report), sorted(s.criterion_id for s in report.scores)]
    return hashlib.sha256(json.dumps(content).encode()).hexdigest()


def scorer_key(report: Report) -> str:
    """Who scored the report and how, without the criteria it covers."""
    return hashlib.sha256(json.dumps(_scorer(report)).encode()).hexdigest()


def _scorer(report: Report) -> list[str]:
    identity = [
        report.kind.value,
        report.rubric_id,
        report.rubric_hash,
        report.model_ref,
        report.prompt_ref,
        report.language,
    ]
    if report.assessment_profile_id:
        identity.append(report.assessment_profile_id)
    return identity


def latest_reports(reports: list[Report]) -> list[Report]:
    latest: dict[tuple[str, str], Report] = {}
    for report in reports:
        key = report.kind.value, report.subject_id
        if key not in latest or report.version > latest[key].version:
            latest[key] = report
    return sorted(latest.values(), key=lambda r: r.created_at, reverse=True)


def progress_groups(
    reports: list[Report], interview_types: Mapping[str, str] | None = None
) -> tuple[ProgressGroup, ...]:
    """Groups of the latest reports of interviews and CV checks.

    `interview_types` maps session ids to their interview type.
    """
    types = interview_types or {}
    groups: dict[str, list[Report]] = {}
    for report in latest_reports(reports):
        groups.setdefault(comparison_key(report), []).append(report)
    result = []
    for key, items in groups.items():
        sample = items[0]
        points = tuple(
            ProgressPoint(
                report.id,
                report.subject_id,
                report.session_id,
                report.created_at,
                report.version,
                report.overall,
                {s.criterion_id: s.value for s in report.scores},
                {
                    s.criterion_id: sum(
                        u.value is not None and u.criterion_id == s.criterion_id
                        for u in report.unit_scores
                    )
                    for s in report.scores
                },
                types.get(report.session_id)
                if report.kind is ReportKind.INTERVIEW and report.session_id
                else None,
            )
            for report in sorted(items, key=lambda r: r.created_at)
        )
        result.append(
            ProgressGroup(
                key,
                scorer_key(sample),
                sample.kind.value,
                sample.rubric_id,
                sample.rubric_hash,
                sample.model_ref,
                sample.language,
                {s.criterion_id: s.label for s in sample.scores},
                points,
            )
        )
    return tuple(result)
