"""Latest-report progress groups with explicit comparability boundaries and no imputation."""

from __future__ import annotations

import hashlib
import json
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


@dataclass(frozen=True, slots=True)
class ProgressGroup:
    id: str
    kind: str
    rubric_id: str
    rubric_hash: str
    model_ref: str
    language: str
    criteria: dict[str, str]
    points: tuple[ProgressPoint, ...]


def comparison_key(report: Report) -> str:
    content = [
        report.kind.value,
        report.rubric_id,
        report.rubric_hash,
        report.model_ref,
        report.prompt_ref,
        report.language,
        sorted(s.criterion_id for s in report.scores),
    ]
    return hashlib.sha256(json.dumps(content).encode()).hexdigest()


def latest_reports(reports: list[Report]) -> list[Report]:
    latest: dict[tuple[str, str], Report] = {}
    for report in reports:
        key = report.kind.value, report.subject_id
        if key not in latest or report.version > latest[key].version:
            latest[key] = report
    return sorted(latest.values(), key=lambda r: r.created_at, reverse=True)


def progress_groups(reports: list[Report]) -> tuple[ProgressGroup, ...]:
    groups: dict[str, list[Report]] = {}
    for report in latest_reports(reports):
        if report.kind is not ReportKind.INTERVIEW:
            continue
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
            )
            for report in sorted(items, key=lambda r: r.created_at)
        )
        result.append(
            ProgressGroup(
                key,
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
