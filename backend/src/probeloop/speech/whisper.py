"""faster-whisper large-v3-turbo: the refinement recogniser (ADR 0009).

Too slow for live segments on the CPU (its fixed 30 s window gave an 11-13 s tail in M1), but the
most accurate engine, and its `initial_prompt` fixes technical vocabulary. It runs a full pass
over the stored audio of a turn. The guards against hallucinated text are always on: VAD
filtering and no conditioning on previous text.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

import onnxruntime
from faster_whisper import WhisperModel

from probeloop.speech.arrays import float_samples
from probeloop.speech.audio import SAMPLE_RATE, PcmAudio
from probeloop.speech.ports import (
    RecognizedSegment,
    RecognizedWord,
    SpeechError,
    TranscribeOptions,
    Transcription,
)


class WhisperSpeechToText:
    def __init__(
        self,
        *,
        model: str = "large-v3-turbo",
        compute_type: str = "int8",
        threads: int = 6,
        beam_size: int = 1,
    ) -> None:
        self._model_name = model
        self._compute_type = compute_type
        self._threads = threads
        self._beam_size = beam_size
        self._model: Any = None
        self._lock = threading.Lock()

    @property
    def engine_ref(self) -> str:
        return f"faster-whisper/{self._model_name}/{self._compute_type}/beam{self._beam_size}"

    def load(self) -> None:
        """Load the model (downloading it if the Hugging Face cache allows). Idempotent."""
        with self._lock:
            if self._model is None:
                onnxruntime.disable_telemetry_events()  # used by faster-whisper's VAD
                self._model = WhisperModel(
                    self._model_name,
                    device="cpu",
                    compute_type=self._compute_type,
                    cpu_threads=self._threads,
                )

    async def transcribe(self, audio: PcmAudio, options: TranscribeOptions) -> Transcription:
        if audio.sample_rate != SAMPLE_RATE:
            raise SpeechError("Whisper needs 16 kHz audio")
        if not audio.data:
            return Transcription((), options.language, self.engine_ref)
        try:
            segments = await asyncio.to_thread(self._recognise, audio, options)
        except Exception as exc:
            raise SpeechError(f"Whisper failed: {type(exc).__name__}") from exc
        return Transcription(tuple(segments), options.language, self.engine_ref)

    def _recognise(self, audio: PcmAudio, options: TranscribeOptions) -> list[RecognizedSegment]:
        self.load()
        segments, _ = self._model.transcribe(
            float_samples(audio),
            language=options.language,
            beam_size=self._beam_size,
            condition_on_previous_text=False,
            initial_prompt=options.initial_prompt,
            vad_filter=True,
            word_timestamps=options.word_timestamps,
        )
        out = []
        for segment in segments:  # a generator: decoding happens while iterating
            text = " ".join(str(segment.text).split())
            if not text:
                continue
            words = tuple(
                RecognizedWord(
                    start_s=float(w.start),
                    end_s=float(w.end),
                    text=str(w.word).strip(),
                    probability=float(w.probability),
                )
                for w in (segment.words or ())
            )
            out.append(
                RecognizedSegment(
                    start_s=float(segment.start),
                    end_s=float(segment.end),
                    text=text,
                    avg_logprob=float(segment.avg_logprob),
                    words=words,
                )
            )
        return out
