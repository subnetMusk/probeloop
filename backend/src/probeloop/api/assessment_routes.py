"""CV review jobs and versioned report reads."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ConfigDict

from probeloop.api.schemas import JobView
from probeloop.assessment.application.schemas import ReportData
from probeloop.assessment.application.service import AssessmentService, ReportNotFoundError
from probeloop.assessment.domain.model import Report, ReportKind
from probeloop.context.application.service import ContextNotFoundError
from probeloop.platform.jobs import JobRunner


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: Literal["it", "en"] = "it"
    # CV checks only: interview reports always use the interview's profile (ADR 0015).
    execution_profile: Literal["local", "cloud"] | None = None


class ProgressPointView(BaseModel):
    report_id: str
    subject_id: str
    session_id: str | None
    created_at: float
    version: int
    overall: float | None
    values: dict[str, float | None]
    evidence_counts: dict[str, int]


class ProgressGroupView(BaseModel):
    id: str
    kind: str
    rubric_id: str
    rubric_hash: str
    model_ref: str
    language: str
    criteria: dict[str, str]
    points: list[ProgressPointView]


def assessment_router(
    assessment: AssessmentService,
    jobs: JobRunner,
    export: Callable[[Report, str], bytes],
    execution: Callable[[str | None], str] = lambda requested: requested or "local",
) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/reports")
    async def history() -> list[ReportData]:
        return [ReportData.of(r) for r in await assessment.history()]

    @router.get("/progress")
    async def progress() -> list[ProgressGroupView]:
        return [
            ProgressGroupView.model_validate(asdict(group)) for group in await assessment.progress()
        ]

    @router.post("/snapshots/{snapshot_id}/cv-reviews", status_code=202)
    async def review_cv(snapshot_id: str, body: ReviewRequest) -> JobView:
        try:
            profile = execution(body.execution_profile)
            return JobView.of(await assessment.submit_cv(snapshot_id, body.language, profile))
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

    @router.post("/sessions/{session_id}/reports", status_code=202)
    async def review_interview(session_id: str, body: ReviewRequest) -> JobView:
        try:
            return JobView.of(await assessment.submit_interview(session_id, body.language))
        except ReportNotFoundError as exc:
            raise HTTPException(404, "interview not found") from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.get("/sessions/{session_id}/reports")
    async def interview_reports(session_id: str) -> list[ReportData]:
        return [
            ReportData.of(r) for r in await assessment.reports(ReportKind.INTERVIEW, session_id)
        ]

    @router.get("/reports/{report_id}/export/{format}")
    async def export_report(report_id: str, format: Literal["md", "json", "pdf"]) -> Response:
        try:
            report = await assessment.report(report_id)
        except ReportNotFoundError as exc:
            raise HTTPException(404, "report not found") from exc
        content = await asyncio.to_thread(export, report, format)
        media_type = {"md": "text/markdown", "json": "application/json", "pdf": "application/pdf"}[
            format
        ]
        return Response(
            content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="report-v{report.version}.{format}"',
            },
        )

    return router
