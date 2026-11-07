"""Incremental transcription of one candidate answer.

Audio frames arrive while the candidate speaks. The voice activity detector cuts them into
segments, and each segment is transcribed as soon as it closes, one at a time and in order, so
the partial transcript grows during the answer. "End of answer" closes the last segment; the
final transcript is ready once that segment is transcribed (the tail measured in M1).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from probeloop.speech.audio import SAMPLE_WIDTH, PcmAudio
from probeloop.speech.filters import FilterConfig, rejection_reason
from probeloop.speech.ports import (
    SpeechError,
    SpeechToText,
    TranscribeOptions,
    Transcription,
    VoiceActivityDetector,
)
from probeloop.speech.segmenter import SegmenterConfig, SpeechSegment, SpeechSegmenter

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    index: int
    start_s: float
    end_s: float
    text: str
    forced: bool


@dataclass(frozen=True, slots=True)
class PartialTranscript:
    """A segment was recognised. `text` is the whole answer recognised so far."""

    segment: TranscriptSegment
    text: str


@dataclass(frozen=True, slots=True)
class SegmentFailed:
    """The recogniser failed on a segment, retries included. Its audio is still stored."""

    index: int
    start_s: float
    end_s: float
    error: str


@dataclass(frozen=True, slots=True)
class DroppedSegment:
    """A segment whose text was rejected by the hallucination filters."""

    index: int
    start_s: float
    end_s: float
    reason: str


type TranscriberEvent = PartialTranscript | SegmentFailed
type TranscriberSink = Callable[[TranscriberEvent], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class TurnTranscript:
    text: str
    segments: tuple[TranscriptSegment, ...]
    dropped: tuple[DroppedSegment, ...]
    failed: tuple[SegmentFailed, ...]
    audio: PcmAudio
    engine_ref: str
    discarded_bursts: int  # speech too short to transcribe
    finalize_s: float  # from "end of answer" to the final transcript

    @property
    def complete(self) -> bool:
        return not self.failed


class TranscriberClosedError(RuntimeError):
    """Audio arrived after the turn was finished or cancelled."""


class TurnTranscriber:
    """Transcribes one answer. Create it inside the event loop, call `start`, then `push` frames.

    `finish` returns the final transcript; `cancel` stops the work and keeps the audio.
    """

    def __init__(
        self,
        stt: SpeechToText,
        vad: VoiceActivityDetector,
        options: TranscribeOptions,
        *,
        segmenter: SegmenterConfig | None = None,
        filters: FilterConfig | None = None,
        sink: TranscriberSink | None = None,
        attempts: int = 2,
        timer: Callable[[], float] = time.perf_counter,
    ) -> None:
        if attempts < 1:
            raise ValueError("at least one attempt is needed")
        self._stt = stt
        self._options = options
        self._segmenter = SpeechSegmenter(vad, segmenter)
        self._filters = filters or FilterConfig()
        self._sink = sink
        self._attempts = attempts
        self._timer = timer
        self._frames: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._segments: asyncio.Queue[SpeechSegment | None] = asyncio.Queue()
        self._tasks: tuple[asyncio.Task[None], asyncio.Task[None]] | None = None
        self._closed = False
        self._audio = bytearray()
        self._recognised: list[TranscriptSegment] = []
        self._dropped: list[DroppedSegment] = []
        self._failed: list[SegmentFailed] = []
        self._engine_ref: str | None = None  # as reported by the recogniser's results

    # ------------------------------------------------------------------ public API

    @property
    def text(self) -> str:
        """The answer recognised so far."""
        return " ".join(s.text for s in self._recognised)

    @property
    def audio(self) -> PcmAudio:
        """All the audio received so far."""
        return PcmAudio(bytes(self._audio))

    def start(self) -> None:
        if self._tasks is None:
            self._tasks = (
                asyncio.create_task(self._detect(), name="speech-detect"),
                asyncio.create_task(self._recognise(), name="speech-recognise"),
            )

    def push(self, pcm: bytes) -> None:
        """Queue a frame of 16 kHz PCM16 audio. Returns immediately."""
        if self._closed:
            raise TranscriberClosedError("the turn is no longer accepting audio")
        if len(pcm) % SAMPLE_WIDTH:
            raise ValueError("16-bit PCM needs an even number of bytes")
        if pcm:
            self._audio += pcm
            self._frames.put_nowait(pcm)

    async def finish(self) -> TurnTranscript:
        """Close the last segment and wait until every segment has been transcribed."""
        if self._closed:
            raise TranscriberClosedError("the turn was already finished or cancelled")
        self.start()
        assert self._tasks is not None
        self._closed = True
        started = self._timer()
        self._frames.put_nowait(None)
        try:
            for task in self._tasks:
                await task
        finally:
            await self._stop()
        return TurnTranscript(
            text=self.text,
            segments=tuple(self._recognised),
            dropped=tuple(self._dropped),
            failed=tuple(self._failed),
            audio=self.audio,
            engine_ref=self._engine_ref or self._stt.engine_ref,
            discarded_bursts=self._segmenter.discarded,
            finalize_s=self._timer() - started,
        )

    async def cancel(self) -> PcmAudio:
        """Stop without transcribing what is left. Returns the audio received so far."""
        self._closed = True
        for error in await self._stop():
            logger.warning("transcription failed before cancellation", exc_info=error)
        return self.audio

    # ------------------------------------------------------------------ background work

    async def _detect(self) -> None:
        """Run the detector on the queued frames. It runs in a worker thread, off the event loop."""
        while True:
            frames = [await self._frames.get()]
            while not self._frames.empty():
                frames.append(self._frames.get_nowait())
            ended = frames[-1] is None
            data = b"".join(f for f in frames if f is not None)
            if data:
                for segment in await asyncio.to_thread(self._segmenter.feed, data):
                    self._segments.put_nowait(segment)
            if ended:
                for segment in self._segmenter.flush():
                    self._segments.put_nowait(segment)
                self._segments.put_nowait(None)
                return

    async def _recognise(self) -> None:
        while (segment := await self._segments.get()) is not None:
            await self._transcribe(segment)

    async def _transcribe(self, segment: SpeechSegment) -> None:
        result = await self._call_engine(segment)
        if result is None:
            failed = SegmentFailed(
                segment.index, segment.start_s, segment.end_s, "speech recognition failed"
            )
            self._failed.append(failed)
            await self._notify(failed)
            return
        self._engine_ref = result.engine_ref
        text = result.text
        reason = rejection_reason(text, segment.duration_s, self._filters)
        if reason is not None:
            logger.info(
                "recognised text discarded",
                extra={"segment": segment.index, "reason": reason, "audio_s": segment.duration_s},
            )
            self._dropped.append(
                DroppedSegment(segment.index, segment.start_s, segment.end_s, reason)
            )
            return
        recognised = TranscriptSegment(
            segment.index, segment.start_s, segment.end_s, text, segment.forced
        )
        self._recognised.append(recognised)
        await self._notify(PartialTranscript(recognised, self.text))

    async def _call_engine(self, segment: SpeechSegment) -> Transcription | None:
        for attempt in range(1, self._attempts + 1):
            started = self._timer()
            try:
                result = await self._stt.transcribe(segment.audio, self._options)
            except SpeechError as exc:
                logger.warning(
                    "speech recognition failed",
                    extra={"segment": segment.index, "attempt": attempt, "error": str(exc)},
                )
                continue
            logger.debug(
                "segment transcribed",
                extra={
                    "segment": segment.index,
                    "audio_s": round(segment.duration_s, 2),
                    "stt_s": round(self._timer() - started, 3),
                    "forced": segment.forced,
                },
            )
            return result
        return None

    async def _notify(self, event: TranscriberEvent) -> None:
        if self._sink is None:
            return
        try:
            await self._sink(event)
        except Exception:  # a broken listener must not stop the transcription
            logger.warning("transcript event delivery failed")

    async def _stop(self) -> list[Exception]:
        """Cancel the background tasks and return the errors they ended with, if any."""
        if self._tasks is None:
            return []
        for task in self._tasks:
            task.cancel()
        results = await asyncio.gather(*self._tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, Exception)]
