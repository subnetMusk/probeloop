"""SQL report repository: append versions and preserve the complete validated content."""

from __future__ import annotations

from dataclasses import replace

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from probeloop.assessment.application.schemas import ReportData
from probeloop.assessment.domain.model import Report, ReportKind
from probeloop.storage.database import JobRow, ReportRow


class SqlReportStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def all(self) -> list[Report]:
        async with self._sessions() as db:
            rows = (await db.scalars(select(ReportRow).order_by(ReportRow.created_at))).all()
            return [_report(row) for row in rows]

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
            return [_report(row) for row in rows]

    async def get(self, report_id: str) -> Report | None:
        async with self._sessions() as db:
            row = await db.get(ReportRow, report_id)
            return None if row is None else _report(row)

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
                    profile_id=report.profile_id,
                    # The owner is kept in its column only: it can change, the content cannot.
                    data=ReportData.of(report).model_dump(mode="json", exclude={"profile_id"}),
                )
            )

    async def adopt_cv_reports(self, snapshot_id: str, profile_id: str) -> int:
        async with self._sessions.begin() as db:
            result = await db.execute(
                update(ReportRow)
                .where(
                    ReportRow.kind == ReportKind.CV.value,
                    ReportRow.subject_id == snapshot_id,
                    ReportRow.profile_id.is_(None),
                )
                .values(profile_id=profile_id)
            )
            return _count(result)

    async def delete_cv_check(self, snapshot_id: str) -> bool:
        async with self._sessions.begin() as db:
            result = await db.execute(
                delete(ReportRow).where(
                    ReportRow.kind == ReportKind.CV.value, ReportRow.subject_id == snapshot_id
                )
            )
            # The review jobs of a context are its only jobs; the caller checked none is pending.
            await db.execute(delete(JobRow).where(JobRow.subject_id == snapshot_id))
            return _count(result) > 0


def _count(result: object) -> int:
    return int(getattr(result, "rowcount", 0) or 0)


def _report(row: ReportRow) -> Report:
    # CV reports written before answer-unit reporting retain their original content.
    upgraded = {"units": [], "unit_scores": [], "delivery": [], "revisions": [], **row.data}
    return replace(ReportData.model_validate(upgraded).domain(), profile_id=row.profile_id)
