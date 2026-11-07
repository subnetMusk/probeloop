"""Speaks an interviewer utterance sentence by sentence while its text is still streaming.

Text deltas go to the sentence splitter; each complete sentence is synthesised as soon as the
previous one is done, so the first sentence plays while the model is still writing the rest and
later sentences are ready before the earlier ones finish playing. Sentences are synthesised one
at a time and delivered in order.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from probeloop.speech.audio import PcmAudio
from probeloop.speech.ports import SpeechError, TextToSpeech
from probeloop.speech.sentences import SentenceSplitter

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SpokenSentence:
    index: int
    text: str
    audio: PcmAudio
    synth_s: float  # duration of the synthesis call
    ready_s: float  # from `start` until the audio was ready


@dataclass(frozen=True, slots=True)
class SentenceFailed:
    """Synthesis failed, retries included. The text is still part of the utterance."""

    index: int
    text: str
    error: str


type SynthesisEvent = SpokenSentence | SentenceFailed
type SynthesisSink = Callable[[SynthesisEvent], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class UtteranceSpeech:
    sentences: tuple[SpokenSentence, ...]
    failed: tuple[SentenceFailed, ...]

    @property
    def first_audio_s(self) -> float | None:
        """From `start` until the first sentence was ready to play."""
        return self.sentences[0].ready_s if self.sentences else None

    @property
    def audio_s(self) -> float:
        return sum(s.audio.duration_s for s in self.sentences)

    @property
    def complete(self) -> bool:
        return not self.failed


class SynthesizerClosedError(RuntimeError):
    """Text arrived after the utterance was finished or cancelled."""


class UtteranceSynthesizer:
    """Speaks one utterance. Create it inside the event loop, call `start`, then `push` text.

    `finish` waits until every sentence is synthesised; `cancel` drops what is still queued.
    """

    def __init__(
        self,
        tts: TextToSpeech,
        voice: str,
        *,
        sink: SynthesisSink | None = None,
        max_sentence_chars: int = 250,
        first_clause_chars: int | None = 40,
        attempts: int = 2,
        timer: Callable[[], float] = time.perf_counter,
    ) -> None:
        if attempts < 1:
            raise ValueError("at least one attempt is needed")
        self._tts = tts
        self._voice = voice
        self._sink = sink
        self._splitter = SentenceSplitter(
            max_chars=max_sentence_chars, first_clause_chars=first_clause_chars
        )
        self._attempts = attempts
        self._timer = timer
        self._queue: asyncio.Queue[tuple[int, str] | None] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self._started = 0.0
        self._next_index = 0
        self._closed = False
        self._spoken: list[SpokenSentence] = []
        self._failed: list[SentenceFailed] = []

    def start(self) -> None:
        if self._task is None:
            self._started = self._timer()
            self._task = asyncio.create_task(self._speak(), name="speech-synthesis")

    def push(self, text: str) -> None:
        """Add streamed utterance text. Returns immediately."""
        if self._closed:
            raise SynthesizerClosedError("the utterance is no longer accepting text")
        for sentence in self._splitter.feed(text):
            self._enqueue(sentence)

    async def finish(self) -> UtteranceSpeech:
        """Speak the text left in the splitter and wait for every sentence."""
        if self._closed:
            raise SynthesizerClosedError("the utterance was already finished or cancelled")
        self.start()
        assert self._task is not None
        self._closed = True
        for sentence in self._splitter.flush():
            self._enqueue(sentence)
        self._queue.put_nowait(None)
        try:
            await self._task
        finally:
            await self._stop()
        return UtteranceSpeech(tuple(self._spoken), tuple(self._failed))

    async def cancel(self) -> None:
        """Stop speaking: sentences not yet synthesised are dropped."""
        self._closed = True
        await self._stop()

    # ------------------------------------------------------------------ background work

    def _enqueue(self, sentence: str) -> None:
        self._queue.put_nowait((self._next_index, sentence))
        self._next_index += 1

    async def _speak(self) -> None:
        while (item := await self._queue.get()) is not None:
            index, text = item
            event = await self._synthesize(index, text)
            if isinstance(event, SpokenSentence):
                self._spoken.append(event)
            else:
                self._failed.append(event)
            await self._notify(event)

    async def _synthesize(self, index: int, text: str) -> SynthesisEvent:
        for attempt in range(1, self._attempts + 1):
            started = self._timer()
            try:
                audio = await self._tts.synthesize(text, self._voice)
            except SpeechError as exc:
                logger.warning(
                    "speech synthesis failed",
                    extra={"sentence": index, "attempt": attempt, "error": str(exc)},
                )
                continue
            now = self._timer()
            return SpokenSentence(
                index=index,
                text=text,
                audio=audio,
                synth_s=now - started,
                ready_s=now - self._started,
            )
        return SentenceFailed(index, text, "speech synthesis failed")

    async def _notify(self, event: SynthesisEvent) -> None:
        if self._sink is None:
            return
        try:
            await self._sink(event)
        except Exception:  # a broken listener must not stop the utterance
            logger.warning("speech event delivery failed")

    async def _stop(self) -> None:
        task = self._task
        if task is None:
            return
        task.cancel()
        results = await asyncio.gather(task, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.warning("speech synthesis stopped by an error", exc_info=result)
