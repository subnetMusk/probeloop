"""Deleting a CV check with fakes: pending reviews block it, and the context goes after it."""

from __future__ import annotations

from typing import Any

import pytest

from probeloop.assessment.application.service import (
    CV_REVIEW_JOB,
    AssessmentBusyError,
    AssessmentService,
    ReportNotFoundError,
)
from probeloop.platform.jobs import Job, JobStatus


class Reports:
    def __init__(self, existing: bool) -> None:
        self.existing = existing
        self.deleted: list[str] = []

    async def delete_cv_check(self, snapshot_id: str) -> bool:
        self.deleted.append(snapshot_id)
        return self.existing


def service(reports: Reports, jobs: list[Job], discarded: list[str]) -> AssessmentService:
    async def for_subject(subject_id: str) -> list[Job]:
        return [j for j in jobs if j.subject_id == subject_id]

    async def discard(snapshot_id: str) -> bool:
        discarded.append(snapshot_id)
        return True

    unused: Any = None
    return AssessmentService(
        store=reports,  # type: ignore[arg-type]
        reviewer=unused,
        snapshot=unused,
        submit=unused,
        now=lambda: 0.0,
        new_id=lambda: "id",
        sessions=unused,
        interviewer=unused,
        delivery=unused,
        jobs=for_subject,
        discard_snapshot=discard,
    )


def job(status: JobStatus) -> Job:
    return Job(id="j", kind=CV_REVIEW_JOB, subject_id="s1", status=status, created_at=0)


async def test_a_running_review_blocks_the_deletion() -> None:
    reports, discarded = Reports(existing=True), []
    with pytest.raises(AssessmentBusyError):
        await service(reports, [job(JobStatus.RUNNING)], discarded).delete_cv_check("s1")
    assert (reports.deleted, discarded) == ([], [])


async def test_the_context_is_discarded_after_the_reports() -> None:
    reports, discarded = Reports(existing=True), []
    await service(reports, [job(JobStatus.SUCCEEDED)], discarded).delete_cv_check("s1")
    assert (reports.deleted, discarded) == (["s1"], ["s1"])


async def test_an_unknown_check_is_not_found() -> None:
    reports, discarded = Reports(existing=False), []
    with pytest.raises(ReportNotFoundError):
        await service(reports, [], discarded).delete_cv_check("s1")
    assert discarded == []
