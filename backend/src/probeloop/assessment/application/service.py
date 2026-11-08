"""Submit assessment jobs and retain immutable reports with source and rubric fingerprints."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, replace
from typing import Any

from probeloop.ai.ports import ContextOverflowError
from probeloop.assessment.application.cv_review import CvReviewer
from probeloop.assessment.application.delivery import DeliveryAnalyser
from probeloop.assessment.application.interview_review import InterviewReviewer
from probeloop.assessment.application.ports import ReportStore
from probeloop.assessment.domain.model import (
    Check,
    Report,
    ReportKind,
    TranscriptVersion,
    overall_score,
)
from probeloop.assessment.domain.progress import ProgressGroup, latest_reports, progress_groups
from probeloop.context.domain.model import ContextSnapshot, DocumentKind
from probeloop.interview.application.ports import SessionStore
from probeloop.interview.domain.model import CandidateTurn
from probeloop.platform.jobs import Job, JobError, Progress

logger = logging.getLogger(__name__)
CV_REVIEW_JOB = "review_cv"
INTERVIEW_REVIEW_JOB = "review_interview"
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
        sessions: SessionStore,
        interviewer: InterviewReviewer,
        delivery: DeliveryAnalyser,
    ) -> None:
        self.store = store
        self.reviewer = reviewer
        self._snapshot = snapshot
        self._submit = submit
        self._now = now
        self._new_id = new_id
        self.sessions = sessions
        self.interviewer = interviewer
        self.delivery = delivery

    async def submit_interview(self, session_id: str, language: str) -> Job:
        session = await self.sessions.load(session_id)
        if session is None:
            raise ReportNotFoundError(session_id)
        if not session.is_terminal:
            raise ValueError("end the interview before generating a report")
        if not session.candidate_turns():
            raise ValueError("the interview has no answers to assess")
        revisions = {str(t.seq): t.current.number for t in session.candidate_turns()}
        return await self._submit(
            INTERVIEW_REVIEW_JOB, session_id, {"language": language, "revisions": revisions}
        )

    async def submit_cv(self, snapshot_id: str, language: str) -> Job:
        snapshot = await self._snapshot(snapshot_id)
        if not any(d.kind is DocumentKind.CV for d in snapshot.documents):
            raise ValueError("the approved context has no CV")
        return await self._submit(CV_REVIEW_JOB, snapshot_id, {"language": language})

    async def reports(self, kind: ReportKind, subject_id: str) -> list[Report]:
        return await self.store.reports(kind, subject_id)

    async def history(self) -> list[Report]:
        return latest_reports(await self.store.all())

    async def progress(self) -> tuple[ProgressGroup, ...]:
        return progress_groups(await self.store.all())

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

    async def review_interview(self, job: Job, progress: Progress) -> Mapping[str, Any]:
        started = self._now()
        session = await self.sessions.load(job.subject_id)
        if session is None:
            raise JobError("interview not found")
        requested = job.payload.get("revisions", {})
        session.turns = [
            replace(t, revisions=t.revisions[: int(requested[str(t.seq)])])
            if isinstance(t, CandidateTurn)
            else t
            for t in session.turns
        ]
        language = str(job.payload.get("language", session.config.language.value))
        snapshot = await self._snapshot(session.snapshot_id) if session.snapshot_id else None
        try:
            result = await self.interviewer.review(session, snapshot, language, progress)
            delivery = await self.delivery.measure(session, language)
        except ContextOverflowError:
            raise JobError(
                "documents or answers exceed the evaluator context; "
                "prepare shorter resources or answers"
            ) from None
        except Exception as exc:
            logger.error("interview review failed", extra={"error_type": type(exc).__name__})
            raise JobError("interview review could not be completed; try again") from None
        previous = await self.store.reports(ReportKind.INTERVIEW, session.id)
        rubric_hash = hashlib.sha256(
            "".join(r.digest for _, r in sorted(self.interviewer.rubrics.items())).encode()
        ).hexdigest()
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "turns": [asdict(t) for t in session.turns],
                    "snapshot": snapshot.content_hash if snapshot else None,
                    "rubric": rubric_hash,
                    "language": language,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        checks = [
            Check(
                f"topic:{topic.id}",
                session.coverage[topic.id].value,
                topic.title,
            )
            for topic in session.context.topics
        ]
        checks.extend(result.coverage)
        if snapshot:
            checks.extend(
                Check(
                    f"document_requirement:{m.requirement_id}",
                    m.status.value,
                    next(f.text for f in snapshot.job_facts if f.id == m.requirement_id),
                )
                for m in snapshot.matches
            )
        report = Report(
            id=self._new_id(),
            kind=ReportKind.INTERVIEW,
            subject_id=session.id,
            version=len(previous) + 1,
            created_at=self._now(),
            language=language,
            rubric_id="interview.v1",
            rubric_hash=rubric_hash,
            model_ref=self.interviewer.model.model_ref,
            prompt_ref="classify_units@v1:off+judge_unit@v2:asc,desc:think+synthesise@v2:off",
            input_fingerprint=fingerprint,
            snapshot_id=session.snapshot_id,
            session_id=session.id,
            scores=result.scores,
            observations=result.observations,
            checks=tuple(checks),
            overall=overall_score(result.scores),
            assessed=sum(s.value is not None for s in result.scores),
            criteria=len(result.scores),
            dropped=result.dropped,
            duration_s=round(self._now() - started, 2),
            disclaimer=(
                "Valutazione formativa delle risposte, non una previsione di assunzione. "
                "Le citazioni sono verificate nel trascritto; giudizi e correzioni tecniche "
                "sono generati dal modello e possono essere errati."
                if language == "it"
                else "A formative assessment of answers, not a hiring prediction. "
                "Quotes are checked against the transcript; judgements and technical corrections "
                "are model-generated and may be wrong."
            ),
            units=result.units,
            unit_scores=result.unit_scores,
            delivery=delivery,
            revisions=tuple(
                TranscriptVersion(t.seq, t.current.number) for t in session.candidate_turns()
            ),
        )
        await self.store.save(report)
        return {"report_id": report.id, "version": report.version, "dropped": report.dropped}
