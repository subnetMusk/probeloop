"""SQL report repository: append versions and preserve the complete validated content."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from probeloop.assessment.application.schemas import ReportData
from probeloop.assessment.domain.model import Report, ReportKind
from probeloop.storage.database import ReportRow


class SqlReportStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def all(self) -> list[Report]:
        async with self._sessions() as db:
            rows = (await db.scalars(select(ReportRow).order_by(ReportRow.created_at))).all()
            return [_report(row.data) for row in rows]

    async def reports(self, kind: ReportKind, subject_id: str) -> list[Report]:
        async with self._sessions() as db:
            rows = (
                await db.scalars(
                    select(ReportRow)
                    .where(
                        ReportRow.kind == kind.value,
                        ReportRow.subject_id == subject_id,
                    )
                    .order_by(ReportRow.version)
                )
            ).all()
            return [_report(row.data) for row in rows]

    async def get(self, report_id: str) -> Report | None:
        async with self._sessions() as db:
            row = await db.get(ReportRow, report_id)
            return None if row is None else _report(row.data)

    async def save(self, report: Report) -> None:
        async with self._sessions.begin() as db:
            db.add(
                ReportRow(
                    id=report.id,
                    kind=report.kind.value,
                    subject_id=report.subject_id,
                    version=report.version,
                    created_at=report.created_at,
                    session_id=report.session_id,
                    snapshot_id=report.snapshot_id,
                    data=ReportData.of(report).model_dump(mode="json"),
                )
            )


def _report(data: dict[str, Any]) -> Report:
    # CV reports written before answer-unit reporting retain their original content.
    upgraded = {"units": [], "unit_scores": [], "delivery": [], "revisions": [], **data}
    return ReportData.model_validate(upgraded).domain()
