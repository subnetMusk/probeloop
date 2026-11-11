"""What a voice interview needs from the speech module. The composition root assembles it."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field

from probeloop.interview.domain.model import Language
from probeloop.speech.audio import SAMPLE_RATE, SAMPLE_WIDTH, PcmAudio
from probeloop.speech.ports import (
    ServiceStatus,
    SpeechToText,
    TextToSpeech,
    TranscribeOptions,
    VoiceActivityDetector,
)
from probeloop.speech.segmenter import SegmenterConfig
from probeloop.speech.synthesizer import SynthesisSink, UtteranceSynthesizer
from probeloop.speech.transcriber import TranscriberSink, TurnTranscriber

logger = logging.getLogger(__name__)

type RecognitionStatus = Callable[[], Awaitable[ServiceStatus]]
type SynthesisStatus = Callable[[str], Awaitable[ServiceStatus]]  # takes the voice

READY = ServiceStatus("ready")
# Two seconds of silence: enough for the recogniser to run every layer of its model once.
RECOGNITION_WARM_UP = PcmAudio(bytes(2 * SAMPLE_RATE * SAMPLE_WIDTH))


async def _always_ready(*_: object) -> ServiceStatus:
    return READY


@dataclass(frozen=True)
class VoiceServices:
    stt: SpeechToText
    tts: TextToSpeech
    vad: Callable[[], VoiceActivityDetector]  # one detector per answer: it keeps state
    voices: Mapping[Language, str]
    stt_status: RecognitionStatus = _always_ready
    tts_status: SynthesisStatus = _always_ready
    segmenter: SegmenterConfig = field(default_factory=SegmenterConfig)
    answer_warning_s: float = 240.0  # spoken answers: a warning after 4 minutes of audio
    answer_limit_s: float = 360.0  # and an automatic end of answer after 6 (architecture §10.1)
    ready_timeout_s: float = 180.0  # how long the start waits for a service that is starting
    poll_s: float = 1.0

    def voice_for(self, language: Language) -> str | None:
        return self.voices.get(language)

    async def service_problems(self) -> list[str]:
        """What the speech services report now, for every configured voice; empty when ready."""
        statuses = [await self.recognition_status()]
        for voice in sorted(set(self.voices.values())):
            statuses.append(await self.synthesis_status(voice))
        return [s.message or s.state for s in statuses if not s.ready]

    async def recognition_status(self) -> ServiceStatus:
        return await self._safely(self.stt_status)

    async def synthesis_status(self, voice: str) -> ServiceStatus:
        return await self._safely(lambda: self.tts_status(voice))

    async def warm_recognition(self, language: Language) -> None:
        """Transcribe silence once, so the recogniser's model is in memory before the first
        answer. Raises `SpeechError` like any transcription."""
        await self.stt.transcribe(RECOGNITION_WARM_UP, TranscribeOptions(language=language.value))

    def transcriber(self, language: Language, sink: TranscriberSink) -> TurnTranscriber:
        transcriber = TurnTranscriber(
            self.stt,
            self.vad(),
            TranscribeOptions(language=language.value),
            segmenter=self.segmenter,
            sink=sink,
        )
        transcriber.start()
        return transcriber

    def synthesizer(self, language: Language, sink: SynthesisSink) -> UtteranceSynthesizer:
        voice = self.voice_for(language)
        if voice is None:
            raise LookupError(f"no voice is configured for language '{language.value}'")
        synthesizer = UtteranceSynthesizer(self.tts, voice, sink=sink)
        synthesizer.start()
        return synthesizer

    @staticmethod
    async def _safely(check: Callable[[], Awaitable[ServiceStatus]]) -> ServiceStatus:
        try:
            return await check()
        except Exception:
            logger.exception("speech service check failed")
            return ServiceStatus("failed", "a speech service could not be checked")
