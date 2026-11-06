"""Drives one live interview session: interviewer moves, answers, pauses and limits."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import replace

from probeloop.ai.ports import LlmError
from probeloop.interview.application.events import (
    AnswerRecorded,
    ErrorRaised,
    EventSink,
    MoveCompleted,
    SessionEnded,
    SessionEvent,
    StateChanged,
    UtteranceDelta,
)
from probeloop.interview.application.phrases import FALLBACK, FAREWELL
from probeloop.interview.application.ports import (
    Clock,
    Interviewer,
    MoveDelta,
    MoveDone,
    MoveRequest,
    SessionStore,
)
from probeloop.interview.domain.model import (
    EndReason,
    InterviewerMove,
    InterviewSession,
    MoveAction,
    MoveStatus,
    Phase,
    SessionStatus,
)
from probeloop.interview.domain.time_policy import TimeDirective, remaining_s, time_directive

logger = logging.getLogger(__name__)


class SessionOrchestrator:
    """Serialises every state change of one session and runs interviewer moves as tasks.

    Moves run in a background task so that pause and end can cancel them. All other operations
    take a lock, so the session is never changed concurrently.
    """

    def __init__(
        self,
        session: InterviewSession,
        *,
        interviewer: Interviewer,
        store: SessionStore,
        clock: Clock,
        sink: EventSink,
        llm_attempts: int = 2,
    ) -> None:
        self.session = session
        self._interviewer = interviewer
        self._store = store
        self._clock = clock
        self._sink = sink
        self._llm_attempts = llm_attempts
        self._lock = asyncio.Lock()
        self._prepare_task: asyncio.Task[None] | None = None
        self._move_task: asyncio.Task[None] | None = None
        self._partial: MoveDelta | None = None
        self._partial_text = ""

    # ------------------------------------------------------------------ commands

    def prepare(self) -> None:
        """Warm up the model while the session is READY, so the opening move starts quickly."""
        if self.session.status is SessionStatus.READY and self._prepare_task is None:
            self._prepare_task = asyncio.create_task(
                self._prepare(), name=f"prepare-{self.session.id}"
            )

    async def start(self) -> None:
        if self._prepare_task is not None:
            await asyncio.gather(self._prepare_task, return_exceptions=True)
        async with self._lock:
            self.session.start(self._clock.now())
            await self._commit()
            self._schedule_move()

    async def playback_finished(self) -> None:
        async with self._lock:
            self.session.finish_speaking(self._clock.now())
            await self._commit()

    async def start_answer(self) -> None:
        async with self._lock:
            self.session.start_answer(self._clock.now())
            await self._commit()

    async def end_answer(self, text: str) -> None:
        """Record the candidate's answer. In text mode the transcript is final immediately."""
        async with self._lock:
            now = self._clock.now()
            self.session.finish_answer(now)
            self.session.record_answer(text, now)
            turn = self.session.turns[-1]
            await self._emit(AnswerRecorded(turn_seq=turn.seq, text=text.strip()))
            await self._commit()
            self._schedule_move()

    async def pause(self) -> None:
        await self._cancel_move()
        async with self._lock:
            if self.session.status is not SessionStatus.IN_PROGRESS:
                return
            self.session.pause(self._clock.now(), partial_move=self._take_partial())
            await self._commit()

    async def resume(self) -> None:
        async with self._lock:
            self.session.resume(self._clock.now())
            await self._commit()
            if self.session.phase is Phase.INTERVIEWER_THINKING:
                self._schedule_move()

    async def end(self, reason: EndReason = EndReason.USER_ENDED) -> None:
        await self._cancel_move()
        async with self._lock:
            if self.session.is_terminal:
                return
            self.session.end(reason, self._clock.now(), partial_move=self._take_partial())
            await self._commit()

    async def close(self) -> None:
        """Stop background work without changing the session (used on shutdown)."""
        if self._prepare_task is not None and not self._prepare_task.done():
            self._prepare_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._prepare_task
        await self._cancel_move()

    async def wait_for_move(self) -> None:
        """Wait until the current move, if any, has been recorded. Used by tests and the CLI."""
        task = self._move_task
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)

    def snapshot(self) -> StateChanged:
        now = self._clock.now()
        elapsed = self.session.elapsed_s(now)
        return StateChanged(
            status=self.session.status,
            phase=self.session.phase,
            elapsed_s=round(elapsed, 1),
            remaining_s=round(remaining_s(elapsed, self.session.config.target_duration_s), 1),
        )

    # ------------------------------------------------------------------ moves

    async def _prepare(self) -> None:
        try:
            await self._interviewer.prepare(self._request(TimeDirective.NORMAL, 0.0))
        except LlmError as exc:
            logger.warning(
                "model warm-up failed", extra={"session_id": self.session.id, "error": str(exc)}
            )
            await self._emit(
                ErrorRaised(
                    code="llm_unavailable", message="the model is not reachable", recoverable=True
                )
            )

    def _request(self, directive: TimeDirective, elapsed: float) -> MoveRequest:
        return MoveRequest(
            config=self.session.config,
            context=self.session.context,
            turns=tuple(self.session.turns),
            coverage=dict(self.session.coverage),
            directive=directive,
            remaining_s=remaining_s(elapsed, self.session.config.target_duration_s),
        )

    def _schedule_move(self) -> None:
        self._partial = None
        self._partial_text = ""
        self._move_task = asyncio.create_task(self._run_move(), name=f"move-{self.session.id}")

    async def _run_move(self) -> None:
        try:
            await self._generate_and_record()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # the session must not stay stuck in THINKING
            logger.exception("interviewer move failed", extra={"session_id": self.session.id})
            async with self._lock:
                if not self.session.is_terminal:
                    self.session.fail(f"internal error: {type(exc).__name__}", self._clock.now())
                    await self._commit()

    async def _generate_and_record(self) -> None:
        session = self.session
        now = self._clock.now()
        elapsed = session.elapsed_s(now)
        target = session.config.target_duration_s
        directive = time_directive(
            elapsed, target, final_question_asked=session.final_question_asked
        )
        turn_seq = len(session.turns)

        if directive is TimeDirective.FORCE_CLOSE:
            move = InterviewerMove(
                action=MoveAction.END,
                topic_id=session.current_topic_id(),
                utterance=FAREWELL[session.config.language],
                fallback=True,
            )
            await self._emit(UtteranceDelta(turn_seq=turn_seq, text=move.utterance))
        else:
            move = await self._generate(self._request(directive, elapsed), turn_seq)

        move = self._normalise(move, directive)
        async with self._lock:
            if session.status is not SessionStatus.IN_PROGRESS:
                return
            if session.phase is not Phase.INTERVIEWER_THINKING:
                return
            session.record_move(
                move, self._clock.now(), final_question=directive is TimeDirective.FINAL_QUESTION
            )
            self._partial = None
            self._partial_text = ""
            await self._emit(
                MoveCompleted(
                    turn_seq=turn_seq,
                    action=move.action,
                    topic_id=move.topic_id,
                    utterance=move.utterance,
                    fallback=move.fallback,
                )
            )
            await self._commit()

    async def _generate(self, request: MoveRequest, turn_seq: int) -> InterviewerMove:
        for attempt in range(1, self._llm_attempts + 1):
            try:
                async for item in self._interviewer.next_move(request):
                    if isinstance(item, MoveDelta):
                        self._partial = item
                        self._partial_text += item.text
                        await self._emit(UtteranceDelta(turn_seq=turn_seq, text=item.text))
                    elif isinstance(item, MoveDone):
                        return item.move
                raise LlmError("interviewer stream ended without a move")
            except LlmError as exc:
                logger.warning(
                    "interviewer move attempt failed",
                    extra={"session_id": self.session.id, "attempt": attempt, "error": str(exc)},
                )
                if self._partial_text or attempt == self._llm_attempts:
                    break
        await self._emit(
            ErrorRaised(code="llm_unavailable", message="LLM call failed", recoverable=True)
        )
        return InterviewerMove(
            action=MoveAction.FOLLOW_UP,
            topic_id=self.session.current_topic_id(),
            utterance=_join_partial(self._partial_text, FALLBACK[self.session.config.language]),
            fallback=True,
        )

    def _normalise(self, move: InterviewerMove, directive: TimeDirective) -> InterviewerMove:
        """Repair what the schema cannot guarantee: known topic ids and closing on time."""
        topic_id = move.topic_id
        if not self.session.context.has_topic(topic_id):
            logger.info("move referenced an unknown topic", extra={"session_id": self.session.id})
            topic_id = self.session.current_topic_id()
        covered = tuple(t for t in move.covered_topic_ids if self.session.context.has_topic(t))
        action = MoveAction.END if directive is TimeDirective.CLOSE else move.action
        return replace(move, topic_id=topic_id, covered_topic_ids=covered, action=action)

    def _take_partial(self) -> InterviewerMove | None:
        if not self._partial_text.strip():
            return None
        partial = self._partial
        topic_id = partial.topic_id if partial and partial.topic_id else None
        if topic_id is None or not self.session.context.has_topic(topic_id):
            topic_id = self.session.current_topic_id()
        move = InterviewerMove(
            action=(partial.action if partial and partial.action else MoveAction.FOLLOW_UP),
            topic_id=topic_id,
            utterance=self._partial_text.strip(),
            status=MoveStatus.INTERRUPTED,
        )
        self._partial = None
        self._partial_text = ""
        return move

    async def _cancel_move(self) -> None:
        task = self._move_task
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._move_task = None

    # ------------------------------------------------------------------ persistence and events

    async def _commit(self) -> None:
        await self._store.save(self.session)
        await self._emit(self.snapshot())
        if self.session.is_terminal:
            await self._emit(
                SessionEnded(reason=self.session.end_reason, failure=self.session.failure)
            )

    async def _emit(self, event: SessionEvent) -> None:
        try:
            await self._sink(event)
        except Exception:  # a broken client connection must not break the session
            logger.warning("event delivery failed", extra={"session_id": self.session.id})


def _join_partial(partial: str, fallback: str) -> str:
    return f"{partial.strip()} … {fallback}" if partial.strip() else fallback
