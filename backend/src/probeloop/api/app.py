"""FastAPI application: REST endpoints and the live-session WebSocket."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
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
from pydantic import ValidationError

from probeloop import logging_setup
from probeloop.ai.ports import LlmError
from probeloop.api.schemas import (
    CreateSession,
    JoinMessage,
    SessionSummaryView,
    SessionView,
    TurnEnd,
    error_message,
    event_message,
    incoming_adapter,
)
from probeloop.bootstrap import Container, build
from probeloop.interview.application.catalog import default_context
from probeloop.interview.application.events import SessionEvent
from probeloop.interview.application.service import (
    LiveSession,
    SessionBusyError,
    SessionNotFoundError,
)
from probeloop.interview.domain.model import (
    InterviewConfig,
    InvalidConfigError,
    InvalidTransitionError,
)
from probeloop.settings import Settings

logger = logging.getLogger(__name__)

WS_POLICY_VIOLATION = 1008
WS_SESSION_BUSY = 4409
WS_SESSION_NOT_FOUND = 4404


def create_app(container: Container | None = None) -> FastAPI:
    if container is None:
        settings = Settings()
        logging_setup.configure(settings.log_level)
        container = build(settings)
    settings = container.settings
    sessions = container.sessions

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await sessions.shutdown()

    app = FastAPI(title="ProbeLoop", version="0.1.0", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )

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

    @app.post("/api/sessions", status_code=201, dependencies=[Depends(require_json)])
    async def create_session(body: CreateSession) -> SessionView:
        try:
            config = InterviewConfig(
                interview_type=body.interview_type,
                difficulty=body.difficulty,
                language=body.language,
                target_duration_s=body.duration_minutes * 60,
                custom_instructions=body.custom_instructions,
            )
            context = default_context(
                body.interview_type,
                candidate_brief=body.candidate_brief,
                job_brief=body.job_brief,
            )
        except InvalidConfigError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return SessionView.of(await sessions.create(config, context))

    @app.get("/api/sessions")
    async def list_sessions() -> list[SessionSummaryView]:
        return [SessionSummaryView.of(s) for s in await sessions.summaries()]

    @app.get("/api/sessions/{session_id}")
    async def get_session(session_id: str) -> SessionView:
        try:
            return SessionView.of(await sessions.get(session_id))
        except (SessionNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="session not found") from exc

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
        outbox: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        sender = asyncio.create_task(_send_loop(websocket, outbox))
        live: LiveSession | None = None
        try:
            join = await _receive_join(websocket)
            if join is None:
                return

            async def listener(seq: int, event: SessionEvent) -> None:
                outbox.put_nowait(event_message(seq, event))

            try:
                live = await sessions.connect(session_id, listener)
            except SessionBusyError:
                await websocket.close(code=WS_SESSION_BUSY)
                return
            except (SessionNotFoundError, ValueError):
                await websocket.close(code=WS_SESSION_NOT_FOUND)
                return

            for seq, event in live.log.since(join.last_seq):
                outbox.put_nowait(event_message(seq, event))
            orchestrator = live.orchestrator
            outbox.put_nowait({**event_message(0, orchestrator.snapshot()), "seq": None})
            orchestrator.prepare()
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
        websocket: WebSocket, live: LiveSession, outbox: asyncio.Queue[dict[str, Any] | None]
    ) -> None:
        orchestrator = live.orchestrator
        commands: dict[str, Callable[[], Awaitable[None]]] = {
            "session.start": orchestrator.start,
            "session.pause": orchestrator.pause,
            "session.resume": orchestrator.resume,
            "session.end": orchestrator.end,
            "playback.finished": orchestrator.playback_finished,
            "turn.start": orchestrator.start_answer,
        }
        while True:
            raw = await websocket.receive_json()
            try:
                message = incoming_adapter.validate_python(raw)
            except ValidationError:
                outbox.put_nowait(error_message("invalid_message", "unknown or malformed message"))
                continue
            if not live.client_messages.first_time(message.client_msg_id):
                continue
            try:
                if message.type == "ping":
                    outbox.put_nowait({"seq": None, "type": "pong"})
                elif isinstance(message, TurnEnd):
                    await orchestrator.end_answer(message.text)
                elif isinstance(message, JoinMessage):
                    outbox.put_nowait(error_message("already_joined", "session already joined"))
                else:
                    await commands[message.type]()
            except InvalidTransitionError as exc:
                outbox.put_nowait(error_message("invalid_command", str(exc)))

    return app


async def _receive_join(websocket: WebSocket) -> JoinMessage | None:
    try:
        message = incoming_adapter.validate_python(await websocket.receive_json())
    except ValidationError:
        message = None
    if not isinstance(message, JoinMessage):
        await websocket.close(code=WS_POLICY_VIOLATION)
        return None
    return message


async def _send_loop(websocket: WebSocket, outbox: asyncio.Queue[dict[str, Any] | None]) -> None:
    while (message := await outbox.get()) is not None:
        with contextlib.suppress(Exception):  # the client may already be gone
            await websocket.send_json(message)
