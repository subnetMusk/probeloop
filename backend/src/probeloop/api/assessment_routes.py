"""CV review jobs and versioned report reads."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from probeloop.api.schemas import JobView
from probeloop.assessment.application.schemas import ReportData
from probeloop.assessment.application.service import AssessmentService, ReportNotFoundError
from probeloop.assessment.domain.model import ReportKind
from probeloop.context.application.service import ContextNotFoundError
from probeloop.platform.jobs import JobRunner


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: Literal["it", "en"] = "it"


def assessment_router(assessment: AssessmentService, jobs: JobRunner) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.post("/snapshots/{snapshot_id}/cv-reviews", status_code=202)
    async def review_cv(snapshot_id: str, body: ReviewRequest) -> JobView:
        try:
            return JobView.of(await assessment.submit_cv(snapshot_id, body.language))
        except ContextNotFoundError as exc:
            raise HTTPException(404, "approved context not found") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.get("/snapshots/{snapshot_id}/cv-reviews")
    async def cv_reviews(snapshot_id: str) -> list[ReportData]:
        return [ReportData.of(r) for r in await assessment.reports(ReportKind.CV, snapshot_id)]

    @router.get("/snapshots/{snapshot_id}/jobs")
    async def snapshot_jobs(snapshot_id: str) -> list[JobView]:
        return [JobView.of(j) for j in await jobs.for_subject(snapshot_id)]

    @router.get("/reports/{report_id}")
    async def report(report_id: str) -> ReportData:
        try:
            return ReportData.of(await assessment.report(report_id))
        except ReportNotFoundError as exc:
            raise HTTPException(404, "report not found") from exc

    return router
