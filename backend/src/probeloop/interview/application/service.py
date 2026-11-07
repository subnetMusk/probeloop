"""Session lifecycle: creation, lookup, deletion and the live connection of one client."""

from __future__ import annotations

import asyncio
import uuid
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from probeloop.interview.application.events import SentenceAudio, SessionEvent
from probeloop.interview.application.orchestrator import SessionOrchestrator
from probeloop.interview.application.ports import Clock, Interviewer, SessionStore, SessionSummary
from probeloop.interview.application.voice import VoiceServices
from probeloop.interview.domain.model import (
    InterviewConfig,
    InterviewContext,
    InterviewSession,
    InvalidConfigError,
    Modality,
    SessionStatus,
)

REPLAY_BUFFER = 500

# The sequence number is None for events that are delivered live but not kept for replay.
type Listener = Callable[[int | None, SessionEvent], Awaitable[None]]


class SessionNotFoundError(LookupError):
    pass


class SessionBusyError(RuntimeError):
    """The session already has a connected client."""


@dataclass
class EventLog:
    """Numbered events of a live session, kept so that a reconnecting client can catch up."""

    events: list[tuple[int, SessionEvent]] = field(default_factory=list)
    next_seq: int = 1
    listener: Listener | None = None

    async def publish(self, event: SessionEvent) -> None:
        if isinstance(event, SentenceAudio):
            # Audio is large, and after a reconnection the interviewer does not repeat itself.
            if self.listener is not None:
                await self.listener(None, event)
            return
        seq = self.next_seq
        self.next_seq += 1
        self.events.append((seq, event))
        del self.events[:-REPLAY_BUFFER]
        if self.listener is not None:
            await self.listener(seq, event)

    def since(self, seq: int) -> list[tuple[int, SessionEvent]]:
        return [(s, e) for s, e in self.events if s > seq]


@dataclass
class ClientMessageFilter:
    """Remembers recent client message ids, so a command resent after a reconnect runs once."""

    capacity: int = 200
    _seen: deque[str] = field(default_factory=deque)

    def first_time(self, client_msg_id: str | None) -> bool:
        if client_msg_id is None:
            return True
        if client_msg_id in self._seen:
            return False
        self._seen.append(client_msg_id)
        if len(self._seen) > self.capacity:
            self._seen.popleft()
        return True


@dataclass(frozen=True, slots=True)
class LiveSession:
    orchestrator: SessionOrchestrator
    log: EventLog
    client_messages: ClientMessageFilter = field(default_factory=ClientMessageFilter)


class SessionService:
    def __init__(
        self,
        *,
        store: SessionStore,
        interviewer: Interviewer,
        clock: Clock,
        voice: VoiceServices | None = None,
        new_id: Callable[[], str] = lambda: uuid.uuid4().hex,
    ) -> None:
        self._store = store
        self._interviewer = interviewer
        self._clock = clock
        self._voice = voice
        self._new_id = new_id
        self._live: dict[str, LiveSession] = {}
        self._connected: set[str] = set()
        self._lock = asyncio.Lock()

    @property
    def voice(self) -> VoiceServices | None:
        return self._voice

    async def create(self, config: InterviewConfig, context: InterviewContext) -> InterviewSession:
        if config.modality is Modality.VOICE:
            if self._voice is None:
                raise InvalidConfigError("voice interviews need the speech services")
            if self._voice.voice_for(config.language) is None:
                raise InvalidConfigError(
                    f"no voice is configured for language '{config.language.value}'"
                )
        session = InterviewSession(
            id=self._new_id(), config=config, context=context, created_at=self._clock.now()
        )
        await self._store.save(session)
        return session

    async def get(self, session_id: str) -> InterviewSession:
        live = self._live.get(session_id)
        if live is not None:
            return live.orchestrator.session
        session = await self._store.load(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    async def summaries(self) -> list[SessionSummary]:
        return await self._store.summaries()

    async def delete(self, session_id: str) -> None:
        live = self._live.pop(session_id, None)
        if live is not None:
            await live.orchestrator.close()
        self._connected.discard(session_id)
        if not await self._store.delete(session_id):
            raise SessionNotFoundError(session_id)

    async def connect(self, session_id: str, listener: Listener) -> LiveSession:
        """Attach a client. Only one client per session; a second one is rejected."""
        async with self._lock:
            if session_id in self._connected:
                raise SessionBusyError(session_id)
            live = self._live.get(session_id)
            if live is None:
                session = await self.get(session_id)
                log = EventLog()
                orchestrator = SessionOrchestrator(
                    session,
                    interviewer=self._interviewer,
                    store=self._store,
                    clock=self._clock,
                    sink=log.publish,
                    voice=self._voice,
                )
                live = LiveSession(orchestrator=orchestrator, log=log)
                self._live[session_id] = live
            live.log.listener = listener
            self._connected.add(session_id)
            return live

    async def disconnect(self, session_id: str) -> None:
        """Detach the client. A running interview is paused until the client returns."""
        async with self._lock:
            self._connected.discard(session_id)
            live = self._live.get(session_id)
            if live is None:
                return
            live.log.listener = None
        orchestrator = live.orchestrator
        if orchestrator.session.status is SessionStatus.IN_PROGRESS:
            await orchestrator.pause()
        if orchestrator.session.is_terminal:
            self._live.pop(session_id, None)

    async def shutdown(self) -> None:
        for live in list(self._live.values()):
            if live.orchestrator.session.status is SessionStatus.IN_PROGRESS:
                await live.orchestrator.pause()
            await live.orchestrator.close()
        self._live.clear()
        self._connected.clear()
