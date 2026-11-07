"""What a voice interview needs from the speech module. The composition root assembles it."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field

from probeloop.interview.domain.model import Language
from probeloop.speech.ports import (
    SpeechToText,
    TextToSpeech,
    TranscribeOptions,
    VoiceActivityDetector,
)
from probeloop.speech.segmenter import SegmenterConfig
from probeloop.speech.synthesizer import SynthesisSink, UtteranceSynthesizer
from probeloop.speech.transcriber import TranscriberSink, TurnTranscriber

logger = logging.getLogger(__name__)

type HealthCheck = Callable[[], Awaitable[str | None]]  # a problem description, or None


@dataclass(frozen=True)
class VoiceServices:
    stt: SpeechToText
    tts: TextToSpeech
    vad: Callable[[], VoiceActivityDetector]  # one detector per answer: it keeps state
    voices: Mapping[Language, str]
    checks: Sequence[HealthCheck] = ()
    segmenter: SegmenterConfig = field(default_factory=SegmenterConfig)
    answer_warning_s: float = 240.0  # spoken answers: a warning after 4 minutes of audio
    answer_limit_s: float = 360.0  # and an automatic end of answer after 6 (architecture §10.1)

    def voice_for(self, language: Language) -> str | None:
        return self.voices.get(language)

    async def problems(self, language: Language) -> list[str]:
        """Why a voice interview in `language` cannot start now; empty when it can."""
        problems = []
        if self.voice_for(language) is None:
            problems.append(f"no voice is configured for language '{language.value}'")
        return problems + await self.service_problems()

    async def service_problems(self) -> list[str]:
        """What the health checks of the speech services report; empty when all are ready."""
        problems = []
        for check in self.checks:
            try:
                problem = await check()
            except Exception:
                logger.exception("speech service check failed")
                problem = "a speech service could not be checked"
            if problem is not None:
                problems.append(problem)
        return problems

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
