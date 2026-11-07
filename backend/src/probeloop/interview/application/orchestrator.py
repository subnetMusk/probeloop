"""Drives one live interview session: interviewer moves, answers, pauses and limits.

In a voice session the orchestrator also runs the speech path. The interviewer's utterance is
synthesised sentence by sentence while it streams. The candidate's audio goes to a
`TurnTranscriber` between "answer" and "end of answer"; frames that arrive at any other time are
dropped, which keeps the interviewer's own voice out of the transcript.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, replace

from probeloop.ai.ports import LlmError
from probeloop.interview.application.events import (
    AnswerRecorded,
    AnswerTimeWarning,
    ErrorRaised,
    EventSink,
    MoveCompleted,
    SentenceAudio,
    SessionEnded,
    SessionEvent,
    SpeechFinished,
    StateChanged,
    TranscriptPartial,
    UtteranceDelta,
)
from probeloop.interview.application.metrics import TurnMetrics
from probeloop.interview.application.phrases import FALLBACK, FAREWELL
from probeloop.interview.application.ports import (
    Clock,
    Interviewer,
    MoveDelta,
    MoveDone,
    MoveRequest,
    SessionStore,
)
from probeloop.interview.application.voice import VoiceServices
from probeloop.interview.domain.model import (
    EndReason,
    InterviewerMove,
    InterviewSession,
    Modality,
    MoveAction,
    MoveStatus,
    Phase,
    SessionStatus,
)
from probeloop.interview.domain.time_policy import TimeDirective, remaining_s, time_directive
from probeloop.speech.synthesizer import SpokenSentence, SynthesisEvent, UtteranceSynthesizer
from probeloop.speech.transcriber import (
    PartialTranscript,
    TranscriberEvent,
    TurnTranscriber,
    TurnTranscript,
)

logger = logging.getLogger(__name__)


@dataclass
class _ReplyTiming:
    """Timestamps of the reply to one spoken answer, for `TurnMetrics`."""

    transcript: TurnTranscript
    answer_seq: int
    ended_at: float
    first_text_at: float | None = None
    move_recorded_at: float | None = None
    first_audio_at: float | None = None


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
        voice: VoiceServices | None = None,
        llm_attempts: int = 2,
        timer: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.session = session
        self._interviewer = interviewer
        self._store = store
        self._clock = clock
        self._sink = sink
        self._voice = voice
        self._llm_attempts = llm_attempts
        self._timer = timer
        self._lock = asyncio.Lock()
        self._prepare_task: asyncio.Task[None] | None = None
        self._move_task: asyncio.Task[None] | None = None
        self._partial: MoveDelta | None = None
        self._partial_text = ""
        self._transcriber: TurnTranscriber | None = None
        self._answer_seq = 0
        self._answer_warned = False
        self.dropped_frames = 0

    @property
    def is_voice(self) -> bool:
        return self.session.config.modality is Modality.VOICE

    # ------------------------------------------------------------------ commands

    def prepare(self) -> None:
        """Warm up the model while the session is READY, so the opening move starts quickly."""
        if self.session.status is SessionStatus.READY and self._prepare_task is None:
            self._prepare_task = asyncio.create_task(
                self._prepare(), name=f"prepare-{self.session.id}"
            )

    async def start(self) -> None:
        if self.is_voice and self.session.status is SessionStatus.READY:
            problems = await self.voice_problems()
            if problems:
                await self._emit(
                    ErrorRaised(
                        code="speech_unavailable", message="; ".join(problems), recoverable=True
                    )
                )
                return
        if self._prepare_task is not None:
            await asyncio.gather(self._prepare_task, return_exceptions=True)
        async with self._lock:
            self.session.start(self._clock.now())
            await self._commit()
            self._schedule_move()

    async def voice_problems(self) -> list[str]:
        if self._voice is None:
            return ["the speech services are not configured"]
        return await self._voice.problems(self.session.config.language)

    async def playback_finished(self) -> None:
        async with self._lock:
            self.session.finish_speaking(self._clock.now())
            await self._commit()

    async def start_answer(self) -> None:
        async with self._lock:
            self.session.start_answer(self._clock.now())
            if self.is_voice and self._transcriber is None:
                # After a reconnection the same answer continues: the transcriber is kept.
                assert self._voice is not None
                self._answer_seq = len(self.session.turns)
                self._answer_warned = False
                self._transcriber = self._voice.transcriber(
                    self.session.config.language, self._on_transcript
                )
            await self._commit()

    async def audio_frame(self, pcm: bytes) -> bool:
        """Add answer audio (16 kHz PCM16). Returns False when the frame was dropped."""
        transcriber = self._transcriber
        if (
            transcriber is None
            or self.session.status is not SessionStatus.IN_PROGRESS
            or self.session.phase is not Phase.CANDIDATE_SPEAKING
        ):
            self.dropped_frames += 1
            return False
        transcriber.push(pcm)
        await self._check_answer_length(transcriber.audio_s)
        return True

    async def end_answer(self, text: str | None = None) -> None:
        """Close the candidate's answer: typed `text` in a text session, audio in a voice one."""
        if self.is_voice and text is not None:
            raise ValueError("a voice session takes spoken answers")
        if not self.is_voice and text is None:
            raise ValueError("a text session needs the answer text")
        async with self._lock:
            now = self._clock.now()
            self.session.finish_answer(now)
            timing = None
            if text is None:
                timing = await self._finish_spoken_answer()
                text = timing.transcript.text
                complete = timing.transcript.complete
            else:
                text, complete = text.strip(), True
            self.session.record_answer(text, self._clock.now())
            turn = self.session.turns[-1]
            await self._emit(AnswerRecorded(turn_seq=turn.seq, text=text, complete=complete))
            await self._commit()
            self._schedule_move(timing)

    async def pause(self) -> None:
        await self._cancel_move()
        async with self._lock:
            if self.session.status is not SessionStatus.IN_PROGRESS:
                return
            await self._cancel_move()  # one may have been scheduled while waiting for the lock
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
            await self._cancel_move()  # one may have been scheduled while waiting for the lock
            await self._drop_answer()
            self.session.end(reason, self._clock.now(), partial_move=self._take_partial())
            await self._commit()

    async def close(self) -> None:
        """Stop background work without changing the session (used on shutdown)."""
        if self._prepare_task is not None and not self._prepare_task.done():
            self._prepare_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._prepare_task
        await self._cancel_move()
        await self._drop_answer()

    async def wait_for_move(self) -> None:
        """Wait until the current move, and its speech, are done. Used by tests and the CLI."""
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

    # ------------------------------------------------------------------ spoken answers

    async def _finish_spoken_answer(self) -> _ReplyTiming:
        """Wait for the final transcript and store the answer's audio. Runs under the lock."""
        transcriber = self._transcriber
        assert transcriber is not None, "start_answer creates the transcriber"
        self._transcriber = None
        ended_at = self._timer()
        transcript = await transcriber.finish()
        try:
            await self._store.save_answer_audio(self.session.id, self._answer_seq, transcript.audio)
        except OSError:
            logger.exception("answer audio not stored", extra={"session_id": self.session.id})
        return _ReplyTiming(transcript=transcript, answer_seq=self._answer_seq, ended_at=ended_at)

    async def _check_answer_length(self, audio_s: float) -> None:
        assert self._voice is not None
        if not self._answer_warned and audio_s >= self._voice.answer_warning_s:
            self._answer_warned = True
            await self._emit(
                AnswerTimeWarning(
                    turn_seq=self._answer_seq,
                    remaining_s=round(self._voice.answer_limit_s - audio_s, 1),
                )
            )
        if audio_s >= self._voice.answer_limit_s and not self._lock.locked():
            logger.info("answer reached its time limit", extra={"session_id": self.session.id})
            await self.end_answer()

    async def _on_transcript(self, event: TranscriberEvent) -> None:
        if isinstance(event, PartialTranscript):
            await self._emit(TranscriptPartial(turn_seq=self._answer_seq, text=event.text))
        else:
            await self._emit(
                ErrorRaised(
                    code="stt_failed",
                    message="part of the answer could not be transcribed; its audio is kept",
                    recoverable=True,
                )
            )

    async def _drop_answer(self) -> None:
        transcriber, self._transcriber = self._transcriber, None
        if transcriber is not None:
            await transcriber.cancel()

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

    def _schedule_move(self, timing: _ReplyTiming | None = None) -> None:
        self._partial = None
        self._partial_text = ""
        self._move_task = asyncio.create_task(
            self._run_move(timing), name=f"move-{self.session.id}"
        )

    async def _run_move(self, timing: _ReplyTiming | None) -> None:
        turn_seq = len(self.session.turns)
        speaker = None
        try:
            if self.is_voice and self._voice is not None:
                speaker = self._voice.synthesizer(
                    self.session.config.language,
                    lambda event: self._on_sentence(turn_seq, event, timing),
                )
            recorded = await self._generate_and_record(turn_seq, speaker, timing)
            if recorded and speaker is not None:
                await self._finish_speech(turn_seq, speaker, timing)
                speaker = None
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # the session must not stay stuck in THINKING
            logger.exception("interviewer move failed", extra={"session_id": self.session.id})
            async with self._lock:
                if not self.session.is_terminal:
                    self.session.fail(f"internal error: {type(exc).__name__}", self._clock.now())
                    await self._commit()
        finally:
            if speaker is not None:
                await speaker.cancel()

    async def _generate_and_record(
        self,
        turn_seq: int,
        speaker: UtteranceSynthesizer | None,
        timing: _ReplyTiming | None,
    ) -> bool:
        session = self.session
        now = self._clock.now()
        elapsed = session.elapsed_s(now)
        target = session.config.target_duration_s
        directive = time_directive(
            elapsed, target, final_question_asked=session.final_question_asked
        )

        if directive is TimeDirective.FORCE_CLOSE:
            move = InterviewerMove(
                action=MoveAction.END,
                topic_id=session.current_topic_id(),
                utterance=FAREWELL[session.config.language],
                fallback=True,
            )
            await self._say(turn_seq, move.utterance, speaker, timing)
        else:
            move = await self._generate(
                self._request(directive, elapsed), turn_seq, speaker, timing
            )

        move = self._normalise(move, directive)
        async with self._lock:
            if session.status is not SessionStatus.IN_PROGRESS:
                return False
            if session.phase is not Phase.INTERVIEWER_THINKING:
                return False
            session.record_move(
                move, self._clock.now(), final_question=directive is TimeDirective.FINAL_QUESTION
            )
            self._partial = None
            self._partial_text = ""
            if timing is not None:
                timing.move_recorded_at = self._timer()
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
        return True

    async def _generate(
        self,
        request: MoveRequest,
        turn_seq: int,
        speaker: UtteranceSynthesizer | None,
        timing: _ReplyTiming | None,
    ) -> InterviewerMove:
        for attempt in range(1, self._llm_attempts + 1):
            try:
                async for item in self._interviewer.next_move(request):
                    if isinstance(item, MoveDelta):
                        self._partial = item
                        self._partial_text += item.text
                        await self._say(turn_seq, item.text, speaker, timing)
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
        fallback = FALLBACK[self.session.config.language]
        if self._partial_text.strip():
            await self._say(turn_seq, f" … {fallback}", speaker, timing)
        else:
            await self._say(turn_seq, fallback, speaker, timing)
        return InterviewerMove(
            action=MoveAction.FOLLOW_UP,
            topic_id=self.session.current_topic_id(),
            utterance=_join_partial(self._partial_text, fallback),
            fallback=True,
        )

    async def _say(
        self,
        turn_seq: int,
        text: str,
        speaker: UtteranceSynthesizer | None,
        timing: _ReplyTiming | None,
    ) -> None:
        """Show utterance text to the client and, in a voice session, speak it."""
        if timing is not None and timing.first_text_at is None and text.strip():
            timing.first_text_at = self._timer()
        await self._emit(UtteranceDelta(turn_seq=turn_seq, text=text))
        if speaker is not None:
            speaker.push(text)

    async def _on_sentence(
        self, turn_seq: int, event: SynthesisEvent, timing: _ReplyTiming | None
    ) -> None:
        if isinstance(event, SpokenSentence):
            if timing is not None and timing.first_audio_at is None:
                timing.first_audio_at = self._timer()
            await self._emit(
                SentenceAudio(
                    turn_seq=turn_seq, index=event.index, text=event.text, audio=event.audio
                )
            )
        else:
            await self._emit(
                ErrorRaised(
                    code="tts_failed",
                    message="a sentence could not be spoken; its text is shown",
                    recoverable=True,
                )
            )

    async def _finish_speech(
        self, turn_seq: int, speaker: UtteranceSynthesizer, timing: _ReplyTiming | None
    ) -> None:
        speech = await speaker.finish()
        await self._emit(
            SpeechFinished(
                turn_seq=turn_seq, sentences=len(speech.sentences), failed=len(speech.failed)
            )
        )
        if timing is None:
            return
        assert self._voice is not None
        transcript = timing.transcript

        def since_end(at: float | None) -> float | None:
            return None if at is None else round(at - timing.ended_at, 3)

        metrics = TurnMetrics(
            answer_turn_seq=timing.answer_seq,
            answer_audio_s=round(transcript.audio.duration_s, 2),
            stt_engine=transcript.engine_ref,
            stt_segments=len(transcript.segments),
            stt_dropped_segments=len(transcript.dropped),
            stt_failed_segments=len(transcript.failed),
            stt_finalize_s=round(transcript.finalize_s, 3),
            llm_first_text_s=since_end(timing.first_text_at),
            move_recorded_s=since_end(timing.move_recorded_at),
            tts_voice=self._voice.voice_for(self.session.config.language) or "",
            tts_first_audio_s=since_end(timing.first_audio_at),
            tts_sentences=len(speech.sentences),
            tts_failed_sentences=len(speech.failed),
        )
        logger.info("turn metrics", extra={"session_id": self.session.id, **metrics.as_record()})
        try:
            await self._store.append_metrics(self.session.id, metrics.as_record())
        except OSError:
            logger.exception("turn metrics not stored", extra={"session_id": self.session.id})

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
