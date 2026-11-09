"""FastAPI application: REST endpoints and the live-session WebSocket."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from probeloop import logging_setup
from probeloop.ai.ports import LlmError
from probeloop.ai.profiles import using_profile
from probeloop.api.assessment_routes import assessment_router
from probeloop.api.context_routes import context_router
from probeloop.api.data_routes import data_router
from probeloop.api.history_routes import history_router
from probeloop.api.schemas import (
    MAX_AUDIO_FRAME_BYTES,
    CreateSession,
    EditAnswer,
    JobView,
    JoinMessage,
    SessionSummaryView,
    SessionView,
    SpeechStatusView,
    TurnEnd,
    error_message,
    event_frames,
    incoming_adapter,
    pong_message,
)
from probeloop.api.settings_routes import settings_router
from probeloop.bootstrap import Container, build
from probeloop.context.application.service import ContextNotFoundError
from probeloop.context.application.snapshots import candidate_brief, job_brief
from probeloop.interview.application.catalog import default_context
from probeloop.interview.application.events import SessionEvent
from probeloop.interview.application.service import (
    LiveSession,
    SessionBusyError,
    SessionNotFoundError,
)
from probeloop.interview.application.transcripts import REFINE_JOB, TranscriptNotFoundError
from probeloop.interview.domain.model import (
    InterviewConfig,
    InterviewContext,
    InterviewSession,
    InvalidConfigError,
    InvalidTransitionError,
    Language,
)
from probeloop.settings import Settings

logger = logging.getLogger(__name__)

WS_POLICY_VIOLATION = 1008
WS_SESSION_BUSY = 4409
WS_SESSION_NOT_FOUND = 4404

type Frame = dict[str, Any] | bytes


def create_app(container: Container | None = None) -> FastAPI:
    if container is None:
        settings = Settings()
        logging_setup.configure(settings.log_level)
        container = build(settings)
    settings = container.settings
    sessions = container.sessions

    transcripts = container.transcripts
    jobs = container.jobs
    store = container.store

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await container.startup()
        yield
        await container.shutdown()

    app = FastAPI(title="ProbeLoop", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def serialise_mutations(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if (
            request.method in ("POST", "PUT", "PATCH", "DELETE")
            and request.url.path.startswith("/api/")
            and not request.url.path.startswith("/api/data/")
        ):
            if container.data.busy:
                return Response("data maintenance is running", status_code=409)
            async with container.data.write_lock:
                return await call_next(request)
        return await call_next(request)

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )

    def execution_for(requested: str | None) -> str:
        """The execution profile of new work: the requested one or the default (ADR 0015)."""
        profile = requested or container.profiles.current
        if profile == "cloud" and not container.account.status().plan_usage:
            raise HTTPException(409, "sign in with ChatGPT first")
        return profile

    async def require_json(request: Request) -> None:
        if not request.headers.get("content-type", "").startswith("application/json"):
            raise HTTPException(status_code=415, detail="content type must be application/json")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/llm")
    async def llm_status() -> dict[str, Any]:
        try:
            caps = await container.model.capabilities()
        except LlmError as exc:
            raise HTTPException(status_code=503, detail="model unavailable") from exc
        return {"model": container.model.model_ref, "context_window": caps.context_window}

    @app.get("/api/speech")
    async def speech_status() -> SpeechStatusView:
        """Whether voice interviews can start now, for the microphone check page."""
        voice = sessions.voice
        if voice is None:
            return SpeechStatusView(
                ready=False, problems=["speech services not configured"], voices={}
            )
        problems = await voice.service_problems()
        return SpeechStatusView(
            ready=not problems,
            problems=problems,
            voices={language.value: voice.voice_for(language) for language in Language},
        )

    @app.post("/api/sessions", status_code=201, dependencies=[Depends(require_json)])
    async def create_session(body: CreateSession) -> SessionView:
        try:
            config = InterviewConfig(
                interview_type=body.interview_type,
                difficulty=body.difficulty,
                language=body.language,
                target_duration_s=body.duration_minutes * 60,
                custom_instructions=body.custom_instructions,
                modality=body.modality,
            )
            profile = execution_for(body.execution_profile)
            if body.snapshot_id is None:
                context = default_context(
                    body.interview_type,
                    candidate_brief=body.candidate_brief,
                    job_brief=body.job_brief,
                )
            else:
                with using_profile(profile):
                    context = await prepared_context(config, body.snapshot_id)
            return session_view(
                await sessions.create(
                    config,
                    context,
                    snapshot_id=body.snapshot_id,
                    execution_profile=profile,
                    profile_id=body.profile_id,
                )
            )
        except InvalidConfigError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    async def prepared_context(config: InterviewConfig, snapshot_id: str) -> InterviewContext:
        """The interviewer's context from an approved snapshot, with a topic plan for it."""
        if sessions.background_busy or sessions.any_active():
            raise HTTPException(
                409, "background processing or another interview is using the models"
            )
        try:
            snapshot = await container.context.snapshot(snapshot_id)
        except ContextNotFoundError as exc:
            raise HTTPException(status_code=404, detail="context not found") from exc
        candidate, job = candidate_brief(snapshot), job_brief(snapshot)
        questions = await container.assessment.practice_questions(snapshot_id)
        topics = await container.planner.plan(config, candidate, job, questions)
        return InterviewContext(
            candidate_brief=candidate,
            job_brief=job,
            topics=topics,
            vocabulary=snapshot.vocabulary,
            role_profile=snapshot.role_profile,
            facts=(*snapshot.candidate_facts, *snapshot.job_facts),
        )

    @app.get("/api/sessions")
    async def list_sessions() -> list[SessionSummaryView]:
        return [SessionSummaryView.of(s) for s in await sessions.summaries()]

    def session_view(session: InterviewSession) -> SessionView:
        def audio(seq: int, speaker: str) -> str | None:
            name = f"audio/turn-{seq:04d}-{speaker}.wav"
            if store.artifact(session.id, name) is None:
                return None
            return f"/api/sessions/{session.id}/files/{name}"

        return SessionView.of(session, audio)

    @app.get("/api/sessions/{session_id}")
    async def get_session(session_id: str) -> SessionView:
        try:
            return session_view(await sessions.get(session_id))
        except (SessionNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="session not found") from exc

    @app.put("/api/sessions/{session_id}/answers/{turn_seq}", dependencies=[Depends(require_json)])
    async def edit_answer(session_id: str, turn_seq: int, body: EditAnswer) -> SessionView:
        """Correct the transcript of an answer: the text becomes a new revision."""
        try:
            await transcripts.edit(session_id, turn_seq, body.text)
            return session_view(await sessions.get(session_id))
        except (TranscriptNotFoundError, SessionNotFoundError) as exc:
            raise HTTPException(status_code=404, detail="session not found") from exc
        except (InvalidTransitionError, InvalidConfigError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/refine", status_code=202)
    async def refine_transcript(session_id: str) -> JobView:
        """Transcribe the answers again from their audio, with the accurate recogniser."""
        try:
            session = await sessions.get(session_id)
        except (SessionNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="session not found") from exc
        if not session.is_terminal:
            raise HTTPException(status_code=409, detail="the interview is not over")
        if not transcripts.can_refine:
            raise HTTPException(status_code=503, detail="speech recognition is not configured")
        return JobView.of(await jobs.submit(REFINE_JOB, session_id))

    @app.get("/api/sessions/{session_id}/jobs")
    async def session_jobs(session_id: str) -> list[JobView]:
        return [JobView.of(j) for j in await jobs.for_subject(session_id)]

    @app.get("/api/sessions/{session_id}/metrics")
    async def session_metrics(session_id: str) -> list[dict[str, Any]]:
        return await store.metrics(session_id)

    @app.get("/api/sessions/{session_id}/files/{name:path}")
    async def session_file(session_id: str, name: str) -> FileResponse:
        path = store.artifact(session_id, name)
        if path is None:
            raise HTTPException(status_code=404, detail="file not found")
        return FileResponse(path, headers={"Cache-Control": "no-cache"})

    @app.get("/api/jobs")
    async def pending_jobs() -> list[JobView]:
        return [JobView.of(job) for job in await jobs.pending()]

    @app.get("/api/jobs/{job_id}")
    async def get_job(job_id: str) -> JobView:
        job = await jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return JobView.of(job)

    @app.delete("/api/sessions/{session_id}", status_code=204)
    async def delete_session(session_id: str) -> Response:
        try:
            await sessions.delete(session_id)
        except (SessionNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="session not found") from exc
        return Response(status_code=204)

    @app.websocket("/ws/sessions/{session_id}")
    async def live_session(websocket: WebSocket, session_id: str) -> None:
        origin = websocket.headers.get("origin")
        if origin is not None and origin not in settings.allowed_origins:
            await websocket.close(code=WS_POLICY_VIOLATION)
            return
        await websocket.accept()
        await _serve(websocket, session_id)

    async def _serve(websocket: WebSocket, session_id: str) -> None:
        outbox: asyncio.Queue[Frame | None] = asyncio.Queue()
        sender = asyncio.create_task(_send_loop(websocket, outbox))
        live: LiveSession | None = None
        try:
            join = await _receive_join(websocket)
            if join is None:
                return

            async def listener(seq: int | None, event: SessionEvent) -> None:
                for frame in event_frames(seq, event):
                    outbox.put_nowait(frame)

            try:
                async with container.data.write_lock:
                    live = await sessions.connect(session_id, listener)
            except SessionBusyError:
                await websocket.close(code=WS_SESSION_BUSY)
                return
            except (SessionNotFoundError, ValueError):
                await websocket.close(code=WS_SESSION_NOT_FOUND)
                return

            for seq, event in live.log.since(join.last_seq):
                for frame in event_frames(seq, event):
                    outbox.put_nowait(frame)
            orchestrator = live.orchestrator
            for frame in event_frames(None, orchestrator.snapshot()):
                outbox.put_nowait(frame)
            await _command_loop(websocket, live, outbox)
        except WebSocketDisconnect:
            pass
        finally:
            outbox.put_nowait(None)
            if live is not None:
                # Shielded: the connection task may be cancelled while the client goes away, but
                # the session must still be paused and saved.
                cleanup = asyncio.ensure_future(sessions.disconnect(session_id))
                await asyncio.shield(cleanup)
            await sender

    async def _command_loop(
        websocket: WebSocket, live: LiveSession, outbox: asyncio.Queue[Frame | None]
    ) -> None:
        orchestrator = live.orchestrator
        commands: dict[str, Callable[[], Awaitable[None]]] = {
            "session.start": lambda: sessions.start(orchestrator.session.id),
            "session.pause": orchestrator.pause,
            "session.resume": lambda: sessions.resume(orchestrator.session.id),
            "session.end": orchestrator.end,
            "playback.finished": orchestrator.playback_finished,
            "turn.start": orchestrator.start_answer,
        }
        while True:
            received = await websocket.receive()
            if received["type"] == "websocket.disconnect":
                raise WebSocketDisconnect(received.get("code", 1000))
            audio = received.get("bytes")
            if audio is not None:
                if not audio or len(audio) % 2 or len(audio) > MAX_AUDIO_FRAME_BYTES:
                    outbox.put_nowait(
                        error_message("invalid_audio_frame", "expected 16-bit PCM, at most 64 KiB")
                    )
                    continue
                try:
                    await orchestrator.audio_frame(audio)
                except InvalidTransitionError as exc:
                    outbox.put_nowait(error_message("invalid_command", str(exc)))
                continue
            try:
                message = incoming_adapter.validate_json(received.get("text") or "")
            except ValidationError:
                outbox.put_nowait(error_message("invalid_message", "unknown or malformed message"))
                continue
            if not live.client_messages.first_time(message.client_msg_id):
                continue
            try:
                if message.type == "ping":
                    outbox.put_nowait(pong_message())
                elif isinstance(message, TurnEnd):
                    await orchestrator.end_answer(message.text)
                elif isinstance(message, JoinMessage):
                    outbox.put_nowait(error_message("already_joined", "session already joined"))
                else:
                    await commands[message.type]()
            except (InvalidTransitionError, ValueError) as exc:
                outbox.put_nowait(error_message("invalid_command", str(exc)))

    app.include_router(context_router(container.context, jobs, execution_for))
    app.include_router(
        assessment_router(container.assessment, jobs, container.export_report, execution_for)
    )
    app.include_router(history_router(container.assessment, container.context))
    app.include_router(data_router(container.data))
    app.include_router(
        settings_router(
            container.profiles,
            container.roles,
            container.data,
            container.account,
            settings.allowed_origins,
        )
    )

    if settings.static_dir is not None:
        _serve_spa(app, settings.static_dir)
    return app


def _serve_spa(app: FastAPI, directory: Path) -> None:
    """Serve the built frontend. Client-side routes get index.html; API paths never do."""
    index = directory / "index.html"
    if not index.is_file():
        logger.warning("no built frontend found", extra={"static_dir": str(directory)})
        return
    app.mount("/assets", StaticFiles(directory=directory / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        if path.split("/", 1)[0] in ("api", "ws", "health", "assets"):
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


async def _receive_join(websocket: WebSocket) -> JoinMessage | None:
    received = await websocket.receive()
    if received["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(received.get("code", 1000))
    try:
        message = incoming_adapter.validate_json(received.get("text") or "")
    except ValidationError:
        message = None
    if not isinstance(message, JoinMessage):
        await websocket.close(code=WS_POLICY_VIOLATION)
        return None
    return message


async def _send_loop(websocket: WebSocket, outbox: asyncio.Queue[Frame | None]) -> None:
    while (frame := await outbox.get()) is not None:
        with contextlib.suppress(Exception):  # the client may already be gone
            if isinstance(frame, bytes):
                await websocket.send_bytes(frame)
            else:
                await websocket.send_json(frame)
