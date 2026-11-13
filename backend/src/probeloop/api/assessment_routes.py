"""CV review jobs and versioned report reads."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from probeloop.api.context_routes import ProfileView
from probeloop.api.downloads import file_headers, subject_filename
from probeloop.api.schemas import JobView
from probeloop.assessment.application.outline import ExportSources
from probeloop.assessment.application.schemas import ReportData
from probeloop.assessment.application.score_scale import score_100
from probeloop.assessment.application.service import (
    AssessmentBusyError,
    AssessmentService,
    ReportNotFoundError,
)
from probeloop.assessment.domain.model import Report, ReportKind
from probeloop.context.application.service import ContextNotFoundError, ContextService
from probeloop.context.domain.model import MAX_TITLE, ContextError
from probeloop.platform.jobs import JobRunner


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: Literal["it", "en"] = "it"
    # CV checks only: interview reports always use the interview's profile (ADR 0015).
    execution_profile: str | None = Field(default=None, max_length=1024)
    # CV checks only: the saved profile the report belongs to.
    profile_id: str | None = Field(default=None, max_length=32)


class ProfileFromCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=MAX_TITLE)


class TargetRoleView(BaseModel):
    profession: str
    target_role: str
    seniority: str


class ProgressPointView(BaseModel):
    scale: Literal["0_100"] = "0_100"
    report_id: str
    subject_id: str
    session_id: str | None
    created_at: float
    version: int
    overall: float | None
    values: dict[str, float | None]
    evidence_counts: dict[str, int]
    interview_type: str | None  # interview reports only
    profile_id: str | None  # the owning saved profile, possibly deleted since
    role: TargetRoleView | None
    rubric_id: str
    rubric_hash: str
    model_ref: str
    prompt_ref: str
    language: str


class ProgressGroupView(BaseModel):
    id: str  # reports in one group compare criterion by criterion
    scorer_key: str  # same rubric, model, prompt and language, whatever the criteria
    kind: str
    rubric_id: str
    rubric_hash: str
    model_ref: str
    language: str
    criteria: dict[str, str]
    points: list[ProgressPointView]


def assessment_router(
    assessment: AssessmentService,
    context: ContextService,
    jobs: JobRunner,
    export: Callable[[Report, str, ExportSources], bytes],
    execution: Callable[[str | None], str] = lambda requested: requested or "local",
) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/reports")
    async def history() -> list[ReportData]:
        return [ReportData.of(r) for r in await assessment.history()]

    @router.get("/progress")
    async def progress() -> list[ProgressGroupView]:
        result = []
        for group in await assessment.progress():
            data = asdict(group)
            for point in data["points"]:
                point["overall"] = score_100(point["overall"])
                point["values"] = {k: score_100(v) for k, v in point["values"].items()}
            result.append(ProgressGroupView.model_validate(data))
        return result

    @router.post("/snapshots/{snapshot_id}/cv-reviews", status_code=202)
    async def review_cv(snapshot_id: str, body: ReviewRequest) -> JobView:
        if body.profile_id is not None:
            try:
                await context.profile(body.profile_id)
            except ContextNotFoundError as exc:
                raise HTTPException(404, "profile not found") from exc
        try:
            plan = execution(body.execution_profile)
            return JobView.of(
                await assessment.submit_cv(snapshot_id, body.language, plan, body.profile_id)
            )
        except ContextNotFoundError as exc:
            raise HTTPException(404, "approved context not found") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.delete("/snapshots/{snapshot_id}/cv-reviews", status_code=204)
    async def delete_cv_check(snapshot_id: str) -> None:
        """Delete every version of a CV check. The approved context and its documents go too,
        unless a saved profile, an interview or another report still uses them."""
        try:
            await assessment.delete_cv_check(snapshot_id)
        except ReportNotFoundError as exc:
            raise HTTPException(404, "CV check not found") from exc
        except AssessmentBusyError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.post("/snapshots/{snapshot_id}/profile", status_code=201)
    async def profile_from_check(snapshot_id: str, body: ProfileFromCheck) -> ProfileView:
        """Save the documents of a CV check as a new profile, which then owns the check."""
        try:
            profile = await context.profile_from_snapshot(snapshot_id, body.name)
        except ContextNotFoundError as exc:
            raise HTTPException(404, "approved context not found") from exc
        except ContextError as exc:
            raise HTTPException(422, str(exc)) from exc
        await assessment.adopt_cv_check(snapshot_id, profile.id)
        return ProfileView.of(profile)

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
        sources = await assessment.export_sources(report) if format != "json" else ExportSources({})
        content = await asyncio.to_thread(export, report, format, sources)
        media_type = {"md": "text/markdown", "json": "application/json", "pdf": "application/pdf"}[
            format
        ]
        filename = await report_filename(report, f"report-v{report.version}.{format}")
        return Response(
            content, media_type=media_type, headers=file_headers(filename, inline=False)
        )

    async def report_filename(report: Report, artefact: str) -> str:
        """Named after the report's subject: the interview session or the CV check's snapshot.
        A subject deleted since falls back to the report's own date."""
        created_at = report.created_at
        if report.kind is ReportKind.INTERVIEW:
            session = await assessment.sessions.load(report.subject_id)
            if session is not None:
                created_at = session.created_at
            return subject_filename("interview", report.subject_id, created_at, artefact)
        with contextlib.suppress(ContextNotFoundError):
            created_at = (await context.snapshot(report.subject_id)).created_at
        return subject_filename("cv-check", report.subject_id, created_at, artefact)

    return router
