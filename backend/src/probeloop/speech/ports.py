"""Speech ports. Adapters live next to them; only the composition root picks one."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from probeloop.speech.audio import PcmAudio

VAD_WINDOW_SAMPLES = 512  # 32 ms at 16 kHz: the window size Silero VAD expects


class SpeechError(Exception):
    """A speech recognition or synthesis call failed.

    The message is safe to log: it never contains audio or text.
    """


@dataclass(frozen=True, slots=True)
class ServiceStatus:
    """Health of a speech service. `starting` is worth waiting for; `failed` is not."""

    state: Literal["ready", "starting", "failed"]
    message: str | None = None  # for the user, when not ready

    @property
    def ready(self) -> bool:
        return self.state == "ready"


@dataclass(frozen=True, slots=True)
class TranscribeOptions:
    language: str
    initial_prompt: str | None = None  # vocabulary hint; engines without prompting ignore it
    word_timestamps: bool = False


@dataclass(frozen=True, slots=True)
class RecognizedWord:
    start_s: float
    end_s: float
    text: str
    probability: float | None = None


@dataclass(frozen=True, slots=True)
class RecognizedSegment:
    start_s: float
    end_s: float
    text: str
    avg_logprob: float | None = None
    words: tuple[RecognizedWord, ...] = ()


@dataclass(frozen=True, slots=True)
class Transcription:
    segments: tuple[RecognizedSegment, ...]
    language: str
    engine_ref: str

    @property
    def text(self) -> str:
        return " ".join(" ".join(s.text.split()) for s in self.segments if s.text.strip())


class SpeechToText(Protocol):
    @property
    def engine_ref(self) -> str:
        """Engine, model and relevant settings, for provenance records."""
        ...

    async def transcribe(self, audio: PcmAudio, options: TranscribeOptions) -> Transcription:
        """Transcribe 16 kHz audio. Every failure is raised as `SpeechError`."""
        ...


class TextToSpeech(Protocol):
    async def synthesize(self, text: str, voice: str) -> PcmAudio:
        """Speech for one sentence, at the voice's own sample rate.

        Every failure, blank text included, is raised as `SpeechError`.
        """
        ...


class VoiceActivityDetector(Protocol):
    """Speech probability of consecutive windows of one audio stream.

    Implementations keep state between windows, so an instance serves a single stream and the
    windows must arrive in order.
    """

    def speech_probability(self, window: bytes) -> float:
        """Probability in [0, 1] that a window of `VAD_WINDOW_SAMPLES` 16 kHz samples is speech."""
        ...
