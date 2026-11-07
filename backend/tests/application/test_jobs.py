from __future__ import annotations

import asyncio
import itertools
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

import pytest

from probeloop.platform.jobs import Job, JobError, JobRunner, JobStatus, Progress


class MemoryJobs:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.updates: list[Job] = []

    async def add(self, job: Job) -> None:
        self.jobs[job.id] = job

    async def update(self, job: Job) -> None:
        self.jobs[job.id] = job
        self.updates.append(job)

    async def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    async def for_subject(self, subject_id: str) -> list[Job]:
        return [j for j in self.jobs.values() if j.subject_id == subject_id]

    async def unfinished(self) -> list[Job]:
        return [j for j in self.jobs.values() if not j.finished]


def runner(repo: MemoryJobs, **kwargs: Any) -> JobRunner:
    ids = (f"job{n}" for n in itertools.count())
    clock = itertools.count()
    return JobRunner(repo, now=lambda: float(next(clock)), new_id=lambda: next(ids), **kwargs)


async def test_jobs_run_in_order_and_report_progress() -> None:
    repo = MemoryJobs()
    jobs = runner(repo)
    ran: list[str] = []

    async def handler(job: Job, progress: Progress) -> Mapping[str, Any]:
        ran.append(job.subject_id)
        await progress(0.5, "half")
        return {"subject": job.subject_id}

    jobs.register("work", handler)
    await jobs.start()
    first = await jobs.submit("work", "s1")
    second = await jobs.submit("work", "s2")
    await jobs.wait_idle()
    await jobs.stop()

    assert ran == ["s1", "s2"]
    done = await jobs.get(first.id)
    assert done is not None
    assert (done.status, done.progress, done.result) == (
        JobStatus.SUCCEEDED,
        1.0,
        {"subject": "s1"},
    )
    assert any(u.message == "half" and u.status is JobStatus.RUNNING for u in repo.updates)
    assert (await jobs.get(second.id)).status is JobStatus.SUCCEEDED  # type: ignore[union-attr]


async def test_an_unfinished_job_for_the_same_subject_is_reused() -> None:
    repo = MemoryJobs()
    jobs = runner(repo)
    release = asyncio.Event()

    async def handler(job: Job, progress: Progress) -> None:
        await release.wait()

    jobs.register("work", handler)
    await jobs.start()
    first = await jobs.submit("work", "s1")
    assert (await jobs.submit("work", "s1")).id == first.id
    release.set()
    await jobs.wait_idle()
    third = await jobs.submit("work", "s1")  # the first one is finished: a new job
    assert third.id != first.id
    await jobs.wait_idle()
    await jobs.stop()


async def test_failures_are_recorded_with_a_safe_message() -> None:
    repo = MemoryJobs()
    jobs = runner(repo)

    async def known(job: Job, progress: Progress) -> None:
        raise JobError("the audio was deleted")

    async def unknown(job: Job, progress: Progress) -> None:
        raise RuntimeError("secret detail")

    jobs.register("known", known)
    jobs.register("unknown", unknown)
    await jobs.start()
    a = await jobs.submit("known", "s1")
    b = await jobs.submit("unknown", "s1")
    await jobs.wait_idle()
    await jobs.stop()
    failed_a, failed_b = await jobs.get(a.id), await jobs.get(b.id)
    assert failed_a is not None
    assert failed_b is not None
    assert (failed_a.status, failed_a.error) == (JobStatus.FAILED, "the audio was deleted")
    assert failed_b.status is JobStatus.FAILED
    assert failed_b.error == "internal error (RuntimeError)"


async def test_unknown_kinds_are_refused() -> None:
    jobs = runner(MemoryJobs())
    with pytest.raises(ValueError, match="unknown job kind"):
        await jobs.submit("nope", "s1")


async def test_jobs_interrupted_by_a_restart_run_again() -> None:
    repo = MemoryJobs()
    interrupted = Job(
        id="old", kind="work", subject_id="s1", status=JobStatus.RUNNING, created_at=0.0
    )
    queued = replace(interrupted, id="older", status=JobStatus.QUEUED, created_at=-1.0)
    await repo.add(interrupted)
    await repo.add(queued)
    ran: list[str] = []

    async def handler(job: Job, progress: Progress) -> None:
        ran.append(job.id)

    jobs = runner(repo)
    jobs.register("work", handler)
    await jobs.start()
    await jobs.wait_idle()
    await jobs.stop()
    assert ran == ["older", "old"]
    assert repo.jobs["old"].status is JobStatus.SUCCEEDED


async def test_jobs_wait_for_the_gate() -> None:
    repo = MemoryJobs()
    open_gate = asyncio.Event()

    async def gate() -> None:
        await open_gate.wait()

    jobs = runner(repo, gate=gate)
    ran: list[str] = []

    async def handler(job: Job, progress: Progress) -> None:
        ran.append(job.id)

    jobs.register("work", handler)
    await jobs.start()
    await jobs.submit("work", "s1")
    await asyncio.sleep(0.05)
    assert ran == []  # an interview is in progress
    open_gate.set()
    await jobs.wait_idle()
    await jobs.stop()
    assert ran == ["job0"]
