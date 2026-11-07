"""Job repository on the database."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from probeloop.platform.jobs import Job, JobStatus
from probeloop.storage.database import JobRow


class SqlJobRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def add(self, job: Job) -> None:
        async with self._sessions.begin() as db:
            row = JobRow(id=job.id)
            _fill(row, job)
            db.add(row)

    async def update(self, job: Job) -> None:
        async with self._sessions.begin() as db:
            row = await db.get(JobRow, job.id)
            if row is None:  # the subject was deleted while the job ran
                return
            _fill(row, job)

    async def get(self, job_id: str) -> Job | None:
        async with self._sessions() as db:
            row = await db.get(JobRow, job_id)
            return None if row is None else _job(row)

    async def for_subject(self, subject_id: str) -> list[Job]:
        query = select(JobRow).where(JobRow.subject_id == subject_id).order_by(JobRow.created_at)
        async with self._sessions() as db:
            return [_job(r) for r in (await db.scalars(query)).all()]

    async def unfinished(self) -> list[Job]:
        query = select(JobRow).where(
            JobRow.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value])
        )
        async with self._sessions() as db:
            return [_job(r) for r in (await db.scalars(query)).all()]


def _fill(row: JobRow, job: Job) -> None:
    row.kind = job.kind
    row.subject_id = job.subject_id
    row.status = job.status.value
    row.progress = job.progress
    row.message = job.message
    row.error = job.error
    row.payload = dict(job.payload)
    row.result = dict(job.result) if job.result is not None else None
    row.created_at = job.created_at
    row.started_at = job.started_at
    row.finished_at = job.finished_at


def _job(row: JobRow) -> Job:
    return Job(
        id=row.id,
        kind=row.kind,
        subject_id=row.subject_id,
        status=JobStatus(row.status),
        created_at=row.created_at,
        progress=row.progress,
        message=row.message,
        error=row.error,
        payload=row.payload,
        result=row.result,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )
