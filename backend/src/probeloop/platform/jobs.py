"""Background jobs: persisted, run one at a time, polled by the client.

Jobs do the slow work outside the interview: re-transcribing answers, analysing documents,
generating reports. They run one at a time because they share one GPU and the CPUs, and they wait
while an interview is in progress (the `gate`), so they never slow down a live conversation or
evict the interviewer's prompt cache.

A job interrupted by a restart is queued again at the next start.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Job:
    id: str
    kind: str
    subject_id: str
    status: JobStatus
    created_at: float
    progress: float = 0.0
    message: str | None = None
    error: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    result: Mapping[str, Any] | None = None
    started_at: float | None = None
    finished_at: float | None = None

    @property
    def finished(self) -> bool:
        return self.status in (JobStatus.SUCCEEDED, JobStatus.FAILED)


class JobError(Exception):
    """A job failed for a reason the user can read. Other exceptions are reported generically."""


class JobRepository(Protocol):
    async def add(self, job: Job) -> None: ...

    async def update(self, job: Job) -> None: ...

    async def get(self, job_id: str) -> Job | None: ...

    async def for_subject(self, subject_id: str) -> list[Job]: ...

    async def unfinished(self) -> list[Job]: ...


type Progress = Callable[[float, str | None], Awaitable[None]]
type Handler = Callable[[Job, Progress], Awaitable[Mapping[str, Any] | None]]


class JobRunner:
    def __init__(
        self,
        repository: JobRepository,
        *,
        now: Callable[[], float],
        new_id: Callable[[], str],
        gate: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._repository = repository
        self._now = now
        self._new_id = new_id
        self._gate = gate
        self._handlers: dict[str, Handler] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None
        self._idle = asyncio.Event()
        self._idle.set()

    def register(self, kind: str, handler: Handler) -> None:
        self._handlers[kind] = handler

    async def start(self) -> None:
        """Queue the jobs left unfinished by the previous run, then start working."""
        for job in sorted(await self._repository.unfinished(), key=lambda j: j.created_at):
            if job.status is JobStatus.RUNNING:
                job = replace(job, status=JobStatus.QUEUED, message="restarted")
                await self._repository.update(job)
            self._enqueue(job.id)
        self._worker = asyncio.create_task(self._work(), name="job-runner")

    async def stop(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker
            self._worker = None

    async def submit(
        self, kind: str, subject_id: str, payload: Mapping[str, Any] | None = None
    ) -> Job:
        """Queue a job. An unfinished job of the same kind for the same subject is reused."""
        if kind not in self._handlers:
            raise ValueError(f"unknown job kind {kind!r}")
        for existing in await self._repository.for_subject(subject_id):
            if existing.kind == kind and not existing.finished:
                return existing
        job = Job(
            id=self._new_id(),
            kind=kind,
            subject_id=subject_id,
            status=JobStatus.QUEUED,
            created_at=self._now(),
            payload=dict(payload or {}),
        )
        await self._repository.add(job)
        self._enqueue(job.id)
        return job

    async def get(self, job_id: str) -> Job | None:
        return await self._repository.get(job_id)

    async def for_subject(self, subject_id: str) -> list[Job]:
        return await self._repository.for_subject(subject_id)

    async def wait_idle(self) -> None:
        """Wait until the queue is empty and no job runs (for tests and tools)."""
        await self._idle.wait()

    def _enqueue(self, job_id: str) -> None:
        self._idle.clear()
        self._queue.put_nowait(job_id)

    async def _work(self) -> None:
        while True:
            job_id = await self._queue.get()
            try:
                if self._gate is not None:
                    await self._gate()
                await self._run(job_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("job runner error", extra={"job_id": job_id})
            finally:
                if self._queue.empty():
                    self._idle.set()

    async def _run(self, job_id: str) -> None:
        job = await self._repository.get(job_id)
        if job is None or job.finished:
            return
        handler = self._handlers.get(job.kind)
        if handler is None:
            await self._repository.update(
                replace(
                    job, status=JobStatus.FAILED, error="unknown job kind", finished_at=self._now()
                )
            )
            return
        job = replace(job, status=JobStatus.RUNNING, started_at=self._now(), progress=0.0)
        await self._repository.update(job)
        current = job

        async def progress(fraction: float, message: str | None) -> None:
            nonlocal current
            current = replace(current, progress=max(0.0, min(1.0, fraction)), message=message)
            await self._repository.update(current)

        logger.info("job started", extra={"job_id": job.id, "kind": job.kind})
        try:
            result = await handler(job, progress)
        except asyncio.CancelledError:
            raise  # stopped by shutdown: queued again at the next start
        except JobError as exc:
            current = replace(
                current, status=JobStatus.FAILED, error=str(exc), finished_at=self._now()
            )
        except Exception as exc:
            logger.exception("job failed", extra={"job_id": job.id, "kind": job.kind})
            current = replace(
                current,
                status=JobStatus.FAILED,
                error=f"internal error ({type(exc).__name__})",
                finished_at=self._now(),
            )
        else:
            current = replace(
                current,
                status=JobStatus.SUCCEEDED,
                progress=1.0,
                result=dict(result or {}),
                finished_at=self._now(),
            )
        await self._repository.update(current)
        logger.info(
            "job finished",
            extra={"job_id": job.id, "kind": job.kind, "status": current.status.value},
        )
