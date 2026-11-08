"""Submit assessment jobs and retain immutable reports with source and rubric fingerprints."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from probeloop.assessment.application.cv_review import CvReviewer
from probeloop.assessment.application.ports import ReportStore
from probeloop.assessment.domain.model import Report, ReportKind, overall_score
from probeloop.context.domain.model import ContextSnapshot, DocumentKind
from probeloop.platform.jobs import Job, JobError, Progress

logger = logging.getLogger(__name__)
CV_REVIEW_JOB = "review_cv"
DISCLAIMER = {
    "it": (
        "Valutazione formativa del documento e delle evidenze disponibili; non è una previsione "
        "di assunzione né una certificazione delle competenze o della compatibilità "
        "con tutti gli ATS."
    ),
    "en": (
        "A formative review of the document and available evidence; not a hiring prediction "
        "or a certification of ability or compatibility with every ATS."
    ),
}


class ReportNotFoundError(LookupError):
    pass


class AssessmentService:
    def __init__(
        self,
        *,
        store: ReportStore,
        reviewer: CvReviewer,
        snapshot: Callable[[str], Awaitable[ContextSnapshot]],
        submit: Callable[[str, str, Mapping[str, Any] | None], Awaitable[Job]],
        now: Callable[[], float],
        new_id: Callable[[], str],
    ) -> None:
        self.store = store
        self.reviewer = reviewer
        self._snapshot = snapshot
        self._submit = submit
        self._now = now
        self._new_id = new_id

    async def submit_cv(self, snapshot_id: str, language: str) -> Job:
        snapshot = await self._snapshot(snapshot_id)
        if not any(d.kind is DocumentKind.CV for d in snapshot.documents):
            raise ValueError("the approved context has no CV")
        return await self._submit(CV_REVIEW_JOB, snapshot_id, {"language": language})

    async def reports(self, kind: ReportKind, subject_id: str) -> list[Report]:
        return await self.store.reports(kind, subject_id)

    async def report(self, report_id: str) -> Report:
        report = await self.store.get(report_id)
        if report is None:
            raise ReportNotFoundError(report_id)
        return report

    async def practice_questions(self, snapshot_id: str) -> tuple[str, ...]:
        reports = await self.store.reports(ReportKind.CV, snapshot_id)
        if not reports:
            return ()
        return tuple(n.text for n in reports[-1].observations if n.kind == "question")[:5]

    async def review_cv(self, job: Job, progress: Progress) -> Mapping[str, Any]:
        started = self._now()
        snapshot = await self._snapshot(job.subject_id)
        language = str(job.payload.get("language", snapshot.language))
        try:
            scores, observations, checks, dropped = await self.reviewer.review(
                snapshot, language, progress
            )
        except Exception as exc:
            # Provider/schema exceptions may carry excerpts: never log their contents or causes.
            logger.error("CV review failed", extra={"error_type": type(exc).__name__})
            raise JobError("CV review could not be completed; try again") from None
        rubric = self.reviewer.rubric
        previous = await self.store.reports(ReportKind.CV, snapshot.id)
        report = Report(
            id=self._new_id(),
            kind=ReportKind.CV,
            subject_id=snapshot.id,
            version=len(previous) + 1,
            created_at=self._now(),
            language=language,
            rubric_id=rubric.ref,
            rubric_hash=rubric.digest,
            model_ref=self.reviewer.model.model_ref,
            prompt_ref="review_cv@v1",
            input_fingerprint=hashlib.sha256(
                f"{snapshot.content_hash}:{language}:{rubric.digest}".encode()
            ).hexdigest(),
            snapshot_id=snapshot.id,
            session_id=None,
            scores=scores,
            observations=observations,
            checks=checks,
            overall=overall_score(scores, minimum_share=rubric.minimum_assessed_share),
            assessed=sum(s.value is not None for s in scores),
            criteria=len(scores),
            dropped=dropped,
            duration_s=round(self._now() - started, 2),
            disclaimer=DISCLAIMER[language],
        )
        await self.store.save(report)
        return {"report_id": report.id, "version": report.version, "dropped": dropped}
