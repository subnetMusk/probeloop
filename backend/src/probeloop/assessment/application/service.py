"""Submit assessment jobs and retain immutable reports with source and rubric fingerprints."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, replace
from typing import Any

from probeloop.ai.ports import ContextOverflowError, UserActionRequiredError
from probeloop.assessment.application.cv_review import CvReviewer
from probeloop.assessment.application.delivery import DeliveryAnalyser
from probeloop.assessment.application.history import (
    CvCheckEntry,
    InterviewEntry,
    interview_history,
    latest_by_subject,
)
from probeloop.assessment.application.interview_review import CallTrace, InterviewReviewer
from probeloop.assessment.application.outline import ExportSources
from probeloop.assessment.application.ports import ReportStore
from probeloop.assessment.domain.comparability import assessment_profile_id
from probeloop.assessment.domain.model import (
    Check,
    QuestionTrace,
    ReferenceDocument,
    Report,
    ReportKind,
    TranscriptVersion,
    explored_scores,
    overall_score,
)
from probeloop.assessment.domain.progress import ProgressGroup, latest_reports, progress_groups
from probeloop.context.domain.model import ContextSnapshot, DocumentKind
from probeloop.interview.application.ports import SessionStore
from probeloop.interview.domain.model import CandidateTurn, InterviewerTurn
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
        payload: dict[str, object] = {"language": language, "revisions": revisions}
        if session.execution_profile:
            # The reports of an interview use the interview's profile (ADR 0015).
            payload["execution"] = session.execution_profile
        return await self._submit(INTERVIEW_REVIEW_JOB, session_id, payload)

    async def submit_cv(
        self, snapshot_id: str, language: str, execution_profile: str | None = None
    ) -> Job:
        snapshot = await self._snapshot(snapshot_id)
        if not any(d.kind is DocumentKind.CV for d in snapshot.documents):
            raise ValueError("the approved context has no CV")
        payload: dict[str, object] = {"language": language}
        if execution_profile:
            payload["execution"] = execution_profile
        return await self._submit(CV_REVIEW_JOB, snapshot_id, payload)

    async def reports(self, kind: ReportKind, subject_id: str) -> list[Report]:
        return await self.store.reports(kind, subject_id)

    async def history(self) -> list[Report]:
        return latest_reports(await self.store.all())

    async def progress(self) -> tuple[ProgressGroup, ...]:
        types = {s.id: s.interview_type for s in await self.sessions.summaries()}
        return progress_groups(await self.store.all(), types)

    async def interview_history(self) -> list[InterviewEntry]:
        return interview_history(await self.sessions.summaries(), await self.store.all())

    async def cv_history(self) -> list[CvCheckEntry]:
        """Every approved context with a CV review, latest review first."""
        latest = latest_by_subject(await self.store.all(), ReportKind.CV)
        entries = []
        for report in sorted(latest.values(), key=lambda r: r.created_at, reverse=True):
            try:
                snapshot = await self._snapshot(report.subject_id)
            except LookupError:
                # Snapshots are kept while their reports exist; skip one that is not.
                logger.warning("CV review without its context", extra={"report_id": report.id})
                continue
            entries.append(CvCheckEntry(snapshot, report))
        return entries

    async def report(self, report_id: str) -> Report:
        report = await self.store.get(report_id)
        if report is None:
            raise ReportNotFoundError(report_id)
        return report

    async def export_sources(self, report: Report) -> ExportSources:
        """Read the immutable snapshot and the exact transcript revisions that were assessed."""
        transcript: dict[int, str] = {}
        if report.session_id:
            session = await self.sessions.load(report.session_id)
            revisions = {r.seq: r.revision for r in report.revisions}
            if session:
                for turn in session.turns:
                    if isinstance(turn, InterviewerTurn):
                        transcript[turn.seq] = turn.move.utterance
                    elif turn.seq in revisions:
                        transcript[turn.seq] = next(
                            (r.text for r in turn.revisions if r.number == revisions[turn.seq]), ""
                        )
        if report.kind is not ReportKind.CV or not report.snapshot_id:
            return ExportSources(transcript)
        snapshot = await self._snapshot(report.snapshot_id)
        facts = {fact.id: fact.text for fact in snapshot.job_facts}
        requirements = tuple(
            Check(
                f"document_requirement:{match.requirement_id}",
                match.status.value,
                facts[match.requirement_id],
            )
            for match in snapshot.matches
            if match.requirement_id in facts
        )
        cv = next((d for d in snapshot.documents if d.kind is DocumentKind.CV), None)
        return ExportSources(
            transcript, requirements, (cv.filename or cv.title) if cv and cv.has_original else None
        )

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
        except UserActionRequiredError as exc:
            raise JobError(str(exc)) from None
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
            prompt_ref=self.reviewer.prompt_ref,
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
        except UserActionRequiredError as exc:
            raise JobError(str(exc)) from None
        except ContextOverflowError:
            raise JobError(
                "documents or answers exceed the evaluator context; "
                "prepare shorter resources or answers"
            ) from None
        except Exception as exc:
            logger.error("interview review failed", extra={"error_type": type(exc).__name__})
            raise JobError("interview review could not be completed; try again") from None
        logger.info("interview review completed", extra=_cost(result.calls))
        previous = await self.store.reports(ReportKind.INTERVIEW, session.id)
        rubric_hash = hashlib.sha256(
            "".join(
                r.digest for _, r in sorted(self.interviewer.rubrics_for(session).items())
            ).encode()
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
        explored = explored_scores(result.scores, result.explored)
        report = Report(
            id=self._new_id(),
            kind=ReportKind.INTERVIEW,
            subject_id=session.id,
            version=len(previous) + 1,
            created_at=self._now(),
            language=language,
            rubric_id=self.interviewer.rubric_ref_for(session),
            rubric_hash=rubric_hash,
            model_ref=self.interviewer.model.model_ref,
            prompt_ref=self.interviewer.prompt_ref_for(session),
            input_fingerprint=fingerprint,
            snapshot_id=session.snapshot_id,
            session_id=session.id,
            scores=result.scores,
            observations=result.observations,
            checks=tuple(checks),
            # The adaptive policy counts only explored criteria; unexplored ones stay visible
            # as unavailable but neither lower nor withhold the overall score.
            overall=overall_score(explored),
            assessed=sum(s.value is not None for s in explored),
            criteria=len(explored),
            dropped=result.dropped,
            duration_s=round(self._now() - started, 2),
            disclaimer=(
                "Valutazione formativa delle risposte, non una previsione di assunzione. "
                "Le citazioni sono verificate nel trascritto; giudizi specialistici e correzioni "
                "sono generati dal modello, possono essere errati e non costituiscono "
                "una verifica esterna."
                if language == "it"
                else "A formative assessment of answers, not a hiring prediction. "
                "Quotes are checked against the transcript; specialist judgements and corrections "
                "are model-generated, may be wrong and are not external verification."
            ),
            units=result.units,
            unit_scores=result.unit_scores,
            delivery=delivery,
            revisions=tuple(
                TranscriptVersion(t.seq, t.current.number) for t in session.candidate_turns()
            ),
            policy_version=session.context.policy_version,
            assessment_profile_id=assessment_profile_id(
                session.context.role_profile, session.context.policy_version
            ),
            role_profile=session.context.role_profile,
            objectives=session.context.topics if session.context.policy_version else (),
            question_trace=tuple(
                QuestionTrace(t.seq, t.move.topic_id, t.move.utterance, t.move.intent)
                for t in session.interviewer_turns()
                if t.move.intent
            ),
            reference_documents=tuple(
                ReferenceDocument(d.id, d.title, d.kind.value)
                for d in (snapshot.documents if snapshot else ())
                if d.kind is DocumentKind.RESOURCE
            ),
        )
        await self.store.save(report)
        return {"report_id": report.id, "version": report.version, "dropped": report.dropped}


def _cost(calls: tuple[CallTrace, ...]) -> dict[str, object]:
    """Counts and timings per phase, for the log; no prompt or output text."""
    phases: dict[str, dict[str, float]] = {}
    for call in calls:
        phase = phases.setdefault(call.phase, {"calls": 0, "attempts": 0, "tokens": 0, "s": 0.0})
        phase["calls"] += 1
        phase["attempts"] += call.attempts
        phase["tokens"] += call.output_tokens or 0
        phase["s"] = round(phase["s"] + call.duration_s, 2)
    return {
        "model_calls": sum(c.attempts for c in calls),
        "output_tokens": sum(c.output_tokens or 0 for c in calls),
        "truncated": sum(r == "length" for c in calls for r in c.stop_reasons),
        "phases": phases,
    }
