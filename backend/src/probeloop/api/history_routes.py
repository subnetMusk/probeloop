"""The history of interviews and CV checks, for the dashboard and its lists."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from probeloop.api.context_routes import DocumentView
from probeloop.assessment.application.history import CvCheckEntry, InterviewEntry, LatestReport
from probeloop.assessment.application.score_scale import score_100
from probeloop.assessment.application.service import AssessmentService
from probeloop.context.application.service import ContextService
from probeloop.context.domain.model import DocumentKind


class LatestReportView(BaseModel):
    scale: Literal["0_100"] = "0_100"
    id: str
    version: int
    versions: int  # how many versions exist
    created_at: float
    overall: float | None
    assessed: int
    criteria: int
    language: str
    model_ref: str
    scorer_key: str = ""

    @classmethod
    def of(cls, r: LatestReport) -> LatestReportView:
        return cls(
            id=r.id,
            version=r.version,
            versions=r.versions,
            created_at=r.created_at,
            overall=score_100(r.overall),
            assessed=r.assessed,
            criteria=r.criteria,
            language=r.language,
            model_ref=r.model_ref,
            scorer_key=r.scorer_key,
        )


class ProfileRefView(BaseModel):
    id: str
    name: str | None  # None when the profile was deleted after the interview


class InterviewHistoryView(BaseModel):
    id: str
    created_at: float
    status: str
    interview_type: str
    difficulty: str
    language: str
    target_duration_s: int
    effective_s: float | None  # interview time without pauses, once it stopped
    answers: int
    execution_profile: str | None
    profile: ProfileRefView | None
    snapshot_id: str | None
    latest_report: LatestReportView | None

    @classmethod
    def of(cls, entry: InterviewEntry, profile_names: dict[str, str]) -> InterviewHistoryView:
        s = entry.session
        return cls(
            id=s.id,
            created_at=s.created_at,
            status=s.status.value,
            interview_type=s.interview_type,
            difficulty=s.difficulty,
            language=s.language,
            target_duration_s=s.target_duration_s,
            effective_s=round(s.effective_s, 1) if s.effective_s is not None else None,
            answers=s.answers,
            execution_profile=s.execution_profile,
            profile=(
                ProfileRefView(id=s.profile_id, name=profile_names.get(s.profile_id))
                if s.profile_id
                else None
            ),
            snapshot_id=s.snapshot_id,
            latest_report=LatestReportView.of(entry.report) if entry.report else None,
        )


class CvCheckHistoryView(BaseModel):
    snapshot_id: str
    created_at: float  # when the context was approved
    language: str
    job_mode: str
    cv: DocumentView | None
    job_offer: DocumentView | None
    latest_report: LatestReportView

    @classmethod
    def of(cls, entry: CvCheckEntry) -> CvCheckHistoryView:
        s = entry.snapshot
        documents = {d.kind: d for d in s.documents}
        cv, offer = documents.get(DocumentKind.CV), documents.get(DocumentKind.JOB_OFFER)
        return cls(
            snapshot_id=s.id,
            created_at=s.created_at,
            language=s.language,
            job_mode=s.job_mode.value,
            cv=DocumentView.of(cv) if cv else None,
            job_offer=DocumentView.of(offer) if offer else None,
            latest_report=LatestReportView.of(entry.report),
        )


def history_router(assessment: AssessmentService, context: ContextService) -> APIRouter:
    router = APIRouter(prefix="/api/history")

    @router.get("/interviews")
    async def interviews() -> list[InterviewHistoryView]:
        """Every interview, newest first, with its latest report."""
        names = {p.id: p.name for p in await context.profiles()}
        return [InterviewHistoryView.of(e, names) for e in await assessment.interview_history()]

    @router.get("/cv-checks")
    async def cv_checks() -> list[CvCheckHistoryView]:
        """Every approved context with a CV review, latest review first."""
        return [CvCheckHistoryView.of(e) for e in await assessment.cv_history()]

    return router
