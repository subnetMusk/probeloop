"""Fakes of the speech ports, for tests and offline development."""

from __future__ import annotations

import asyncio
import math
import sys
from array import array
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from probeloop.speech.audio import PcmAudio
from probeloop.speech.ports import (
    RecognizedSegment,
    RecognizedWord,
    TranscribeOptions,
    Transcription,
)

type SttScript = str | Exception | Callable[[PcmAudio], str]


def describe_duration(audio: PcmAudio) -> str:
    return f"Segmento di prova di {audio.duration_s:.1f} secondi."


@dataclass
class FakeSpeechToText:
    """Replays scripted results in order and records every call.

    A script item is a text, an exception to raise, or a function of the audio. Once the script
    is exhausted, `default` produces the text.
    """

    script: Sequence[SttScript] = ()
    default: Callable[[PcmAudio], str] = describe_duration
    delay_s: float = 0.0
    calls: list[tuple[PcmAudio, TranscribeOptions]] = field(default_factory=list)

    @property
    def engine_ref(self) -> str:
        return "fake:stt"

    async def transcribe(self, audio: PcmAudio, options: TranscribeOptions) -> Transcription:
        index = len(self.calls)
        self.calls.append((audio, options))
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        item = self.script[index] if index < len(self.script) else self.default
        if isinstance(item, Exception):
            raise item
        text = (item(audio) if callable(item) else item) if audio.data else ""
        if not text.strip():
            return Transcription((), options.language, self.engine_ref)
        words = _even_words(text, audio.duration_s) if options.word_timestamps else ()
        segment = RecognizedSegment(0.0, audio.duration_s, " ".join(text.split()), words=words)
        return Transcription((segment,), options.language, self.engine_ref)


def _even_words(text: str, duration_s: float) -> tuple[RecognizedWord, ...]:
    """Spread the words evenly over the audio."""
    tokens = text.split()
    step = duration_s / len(tokens)
    return tuple(
        RecognizedWord(round(i * step, 3), round((i + 1) * step, 3), token, 1.0)
        for i, token in enumerate(tokens)
    )


@dataclass
class EnergyVad:
    """Treats every window louder than `threshold_dbfs` as speech. Deterministic."""

    threshold_dbfs: float = -40.0

    def speech_probability(self, window: bytes) -> float:
        samples = array("h")
        samples.frombytes(window)
        if sys.byteorder == "big":
            samples.byteswap()
        if not samples:
            return 0.0
        rms = math.sqrt(sum(s * s for s in samples) / len(samples))
        if rms == 0:
            return 0.0
        return 1.0 if 20 * math.log10(rms / 32768) >= self.threshold_dbfs else 0.0
