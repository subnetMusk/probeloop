"""Composition root: the only place that chooses concrete adapters."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from probeloop.ai.chatgpt import ChatGptChatModel
from probeloop.ai.chatgpt_auth import ChatGptAccount, ChatGptAuth
from probeloop.ai.debuglog import DebugLogChatModel
from probeloop.ai.fake import FakeChatGptAccount, FakeChatModel
from probeloop.ai.ollama import OllamaChatModel
from probeloop.ai.ports import ChatModel, ChatRequest
from probeloop.ai.profiles import ProfiledChatModel, using_profile
from probeloop.ai.scheduled import ScheduledChatModel
from probeloop.assessment.application.cv_review import CvReviewer
from probeloop.assessment.application.delivery import DeliveryAnalyser
from probeloop.assessment.application.interview_review import InterviewReviewer
from probeloop.assessment.application.outline import ExportSources
from probeloop.assessment.application.rubrics import load_rubric
from probeloop.assessment.application.service import (
    CV_REVIEW_JOB,
    INTERVIEW_REVIEW_JOB,
    AssessmentService,
)
from probeloop.assessment.domain.model import Report
from probeloop.assessment.infrastructure.exports import export_report
from probeloop.assessment.infrastructure.fake import scripted_assessment
from probeloop.context.application.analysis import ContextAnalyser
from probeloop.context.application.service import ANALYSE_JOB, ContextService
from probeloop.context.application.snapshots import vocabulary_prompt
from probeloop.context.infrastructure.fake_analysis import scripted_analysis
from probeloop.context.infrastructure.text_extraction import TextExtractor
from probeloop.ids import new_id
from probeloop.interview.application.llm_interviewer import LlmInterviewer
from probeloop.interview.application.planner import TopicPlanner
from probeloop.interview.application.service import SessionService
from probeloop.interview.application.transcripts import REFINE_JOB, TranscriptService
from probeloop.interview.application.voice import VoiceServices
from probeloop.interview.domain.model import InterviewSession, Language, Modality
from probeloop.platform.jobs import Handler, Job, JobRunner, Progress
from probeloop.platform.model_access import BackgroundModelAccess
from probeloop.settings import Settings
from probeloop.speech.fake import FakeSpeechToText, FakeTextToSpeech
from probeloop.speech.http_stt import HttpSpeechToText
from probeloop.speech.piper import PiperTextToSpeech
from probeloop.speech.ports import SpeechToText
from probeloop.speech.silero import SileroVad
from probeloop.storage.data import SqlDataStore
from probeloop.storage.database import create_engine, migrate, sessionmaker
from probeloop.storage.session_files import SessionFiles
from probeloop.storage.sql_context import SqlContextStore
from probeloop.storage.sql_jobs import SqlJobRepository
from probeloop.storage.sql_reports import SqlReportStore
from probeloop.storage.sql_sessions import SqlSessionStore
from probeloop.workspace.execution import ExecutionProfiles, Profile
from probeloop.workspace.service import DataService


class SystemClock:
    def now(self) -> float:
        return time.time()


@dataclass(frozen=True, slots=True)
class Container:
    settings: Settings
    model: ChatModel
    sessions: SessionService
    transcripts: TranscriptService
    context: ContextService
    planner: TopicPlanner
    jobs: JobRunner
    store: SqlSessionStore
    engine: AsyncEngine
    extractor: TextExtractor
    assessment: AssessmentService
    export_report: Callable[[Report, str, ExportSources], bytes]
    data: DataService
    profiles: ExecutionProfiles
    # The interviewer, analysis and evaluation roles, each with a model per profile.
    roles: Mapping[str, ProfiledChatModel]
    account: ChatGptAccount

    async def startup(self) -> None:
        """Bring the schema up to date, then resume the background jobs."""
        await migrate(self.engine)
        await self.jobs.start()

    async def shutdown(self) -> None:
        await self.sessions.shutdown()
        await self.jobs.stop()
        await self.data.close()
        await self.engine.dispose()
        self.extractor.close()

    async def restore_backup(self, archive: Path) -> None:
        await migrate(self.engine)
        await self.data.restore(archive)


def build_voice(settings: Settings) -> VoiceServices | None:
    """The speech services for voice interviews, or None when they are not configured."""
    voices = {
        language: voice
        for language, voice in (
            (Language.ITALIAN, settings.tts_voice_it),
            (Language.ENGLISH, settings.tts_voice_en),
        )
        if voice
    }
    if settings.speech_fake:
        return VoiceServices(
            stt=FakeSpeechToText(),
            tts=FakeTextToSpeech(),
            vad=SileroVad,
            voices=voices,
            answer_warning_s=settings.answer_warning_s,
            answer_limit_s=settings.answer_limit_s,
        )
    if not (settings.stt_url and settings.tts_url):
        return None
    stt = HttpSpeechToText(settings.stt_url, timeout_s=15.0)
    tts = PiperTextToSpeech(settings.tts_url, timeout_s=15.0)
    return VoiceServices(
        stt=stt,
        tts=tts,
        vad=SileroVad,
        voices=voices,
        stt_status=stt.status,
        tts_status=tts.status,
        answer_warning_s=settings.answer_warning_s,
        answer_limit_s=settings.answer_limit_s,
    )


def scripted_moves(questions: int = 3) -> Callable[[ChatRequest], str]:
    """Interviewer moves for end-to-end tests: numbered questions, then a farewell.

    The number comes from the request itself (each earlier move is an assistant message), so
    every session gets the same script.
    """

    def move(request: ChatRequest) -> str:
        if "topics" in (request.response_schema or {}).get("properties", {}):
            return json.dumps(
                {
                    "topics": [
                        {"title": "Relevant project experience", "reason": "Candidate context."},
                        {
                            "title": "Technical reasoning and trade-offs",
                            "reason": "Role requirements.",
                        },
                    ]
                }
            )
        asked = sum(1 for message in request.messages if message.role == "assistant")
        if asked >= questions:
            action, utterance = "end", "Grazie, il colloquio di prova è terminato."
        else:
            action, utterance = "follow_up", f"Questa è la domanda di prova numero {asked + 1}?"
        return json.dumps(
            {"action": action, "topic_id": "t1", "utterance": utterance, "covered_topic_ids": []}
        )

    return move


def build(
    settings: Settings,
    *,
    model: ChatModel | None = None,
    analysis_model: ChatModel | None = None,
    assessment_model: ChatModel | None = None,
    voice: VoiceServices | None = None,
) -> Container:
    if model is None and settings.llm_fake:
        model = FakeChatModel([scripted_moves()], chunk_delay_s=0.01)
    if model is None:
        model = OllamaChatModel(
            base_url=settings.ollama_base_url,
            model=settings.interviewer_model,
            context_window=settings.context_window,
            keep_alive=settings.keep_alive,
        )
    if analysis_model is None:
        analysis_model = model
        if settings.llm_fake:
            analysis_model = FakeChatModel([scripted_analysis])
        if not settings.llm_fake and settings.analysis_model != settings.interviewer_model:
            analysis_model = OllamaChatModel(
                base_url=settings.ollama_base_url,
                model=settings.analysis_model,
                context_window=settings.analysis_context_window,
                keep_alive=settings.keep_alive,
            )
    if assessment_model is None:
        assessment_model = (
            FakeChatModel([scripted_assessment])
            if settings.llm_fake
            else OllamaChatModel(
                base_url=settings.ollama_base_url,
                model=settings.evaluation_model,
                context_window=settings.evaluation_context_window,
                keep_alive=settings.keep_alive,
                timeout_s=600.0,
            )
        )
    local = {"interviewer": model, "analysis": analysis_model, "evaluation": assessment_model}
    account: ChatGptAccount = (
        FakeChatGptAccount() if settings.llm_fake else ChatGptAuth(settings.data_dir / "chatgpt")
    )
    cloud = build_cloud(settings, local, account)
    available: tuple[Profile, ...] = ("local", "cloud")
    profiles = ExecutionProfiles(settings.data_dir / "execution-profile.json", available)
    roles = {
        role: ProfiledChatModel(
            {"local": local[role], "cloud": cloud[role]}, lambda: profiles.current
        )
        for role in local
    }
    model, analysis_model, assessment_model = (
        roles["interviewer"],
        roles["analysis"],
        roles["evaluation"],
    )
    if settings.llm_debug_log:
        log = settings.data_dir / "logs" / "llm.jsonl"
        model = DebugLogChatModel(model, log)
        analysis_model = DebugLogChatModel(analysis_model, log)
        assessment_model = DebugLogChatModel(assessment_model, log)
    if voice is None:
        voice = build_voice(settings)
    clock = SystemClock()
    engine = create_engine(settings.effective_database_url)
    db = sessionmaker(engine)
    store = SqlSessionStore(db, SessionFiles(settings.data_dir / "sessions"))
    transcripts = TranscriptService(
        store=store,
        clock=clock,
        refiner=build_refiner(settings),
        vocabulary=lambda session: vocabulary_prompt(session.context.vocabulary),
    )
    holder: dict[str, SessionService] = {}

    async def gate() -> None:
        await holder["sessions"].wait_until_idle()

    access = BackgroundModelAccess(gate, lambda: holder["sessions"].any_active())
    analysis_model = ScheduledChatModel(analysis_model, access.acquire)
    planning_model = ScheduledChatModel(model, access.acquire)
    jobs = JobRunner(SqlJobRepository(db), now=clock.now, new_id=new_id, gate=gate)
    jobs.register(REFINE_JOB, transcripts.refine)
    extractor = TextExtractor()
    context_store = SqlContextStore(db, settings.data_dir / "blobs")
    context = ContextService(
        store=context_store,
        analyser=ContextAnalyser(analysis_model, cache=context_store),
        extractor=extractor,
        submit=jobs.submit,
        now=clock.now,
        new_id=new_id,
    )
    jobs.register(ANALYSE_JOB, with_job_profile(context.analyse))
    assessment_model = ScheduledChatModel(assessment_model, access.acquire)
    assessment = AssessmentService(
        store=SqlReportStore(db),
        reviewer=CvReviewer(assessment_model, load_rubric("cv")),
        interviewer=InterviewReviewer(
            assessment_model, judge_reasoning=settings.evaluation_judge_reasoning
        ),
        sessions=store,
        delivery=DeliveryAnalyser(store, voice.vad if voice else None),
        snapshot=context.snapshot,
        submit=jobs.submit,
        now=clock.now,
        new_id=new_id,
    )
    jobs.register(CV_REVIEW_JOB, with_job_profile(assessment.review_cv))
    jobs.register(INTERVIEW_REVIEW_JOB, with_job_profile(assessment.review_interview))

    async def on_finished(session: InterviewSession) -> None:
        if session.config.modality is Modality.VOICE and transcripts.can_refine:
            await jobs.submit(REFINE_JOB, session.id)

    def interviewer_for(session: InterviewSession) -> LlmInterviewer:
        # The interviewer stays on the session's profile even if the default changes (ADR 0015).
        pinned = roles["interviewer"].pinned(session.execution_profile or profiles.current)
        if settings.llm_debug_log:
            pinned = DebugLogChatModel(pinned, settings.data_dir / "logs" / "llm.jsonl")
        return LlmInterviewer(pinned)

    sessions = SessionService(
        interviewer_for=interviewer_for,
        store=store,
        interviewer=LlmInterviewer(model),
        clock=clock,
        voice=voice,
        on_finished=on_finished,
        background_busy=lambda: jobs.running or access.busy or data.busy,
    )
    holder["sessions"] = sessions

    async def pending_jobs() -> bool:
        return bool(await jobs.pending())

    data = DataService(
        SqlDataStore(engine, settings.data_dir),
        connected=lambda: sessions.has_connections or sessions.any_active(),
        pending=pending_jobs,
        clear_live=sessions.shutdown,
    )
    return Container(
        settings=settings,
        model=model,
        sessions=sessions,
        transcripts=transcripts,
        context=context,
        planner=TopicPlanner(planning_model),
        jobs=jobs,
        store=store,
        engine=engine,
        extractor=extractor,
        assessment=assessment,
        export_report=export_report,
        data=data,
        profiles=profiles,
        roles=roles,
        account=account,
    )


def build_cloud(
    settings: Settings, local: Mapping[str, ChatModel], account: ChatGptAccount
) -> dict[str, ChatModel]:
    """The models of the cloud profile per role, used through the signed-in ChatGPT plan.

    With scripted models (`llm_fake`) the cloud profile reuses them, so that selecting a profile
    can be tested end to end without a provider.
    """
    if settings.llm_fake:
        return dict(local)

    def cloud_model(name: str, timeout_s: float) -> ChatGptChatModel:
        return ChatGptChatModel(
            model=name,
            token=account.access_token,
            context_window=settings.cloud_context_window,
            reasoning_off=settings.cloud_reasoning_off,
            timeout_s=timeout_s,
        )

    return {
        "interviewer": cloud_model(settings.cloud_interviewer_model, 60.0),
        "analysis": cloud_model(settings.cloud_analysis_model, 300.0),
        "evaluation": cloud_model(settings.cloud_evaluation_model, 600.0),
    }


def with_job_profile(handler: Handler) -> Handler:
    """Run a job's model calls on the execution profile stored in its payload (ADR 0015).

    Jobs run one at a time in a single worker task, so the scope covers exactly this job.
    """

    async def run(job: Job, progress: Progress) -> Mapping[str, Any] | None:
        profile = job.payload.get("execution")
        with using_profile(profile if isinstance(profile, str) else None):
            return await handler(job, progress)

    return run


def build_refiner(settings: Settings) -> SpeechToText | None:
    """The accurate recogniser of the refinement pass after the call."""
    if settings.speech_fake:
        return FakeSpeechToText()
    if settings.stt_url:
        # The first call loads Whisper in the worker, which takes minutes on a cold start.
        return HttpSpeechToText(settings.stt_url, engine="refine", timeout_s=900.0)
    return None
