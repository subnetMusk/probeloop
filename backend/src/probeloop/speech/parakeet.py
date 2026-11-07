"""Parakeet TDT 0.6B v3 through onnx-asr: the live recogniser (ADR 0009).

Parakeet has no prompt biasing, so `initial_prompt` is ignored, and it detects the language by
itself. It accepts about 20-30 s per call, so longer audio is split at pauses first.
"""

from __future__ import annotations

import asyncio
import math
import threading
from collections.abc import Sequence

import onnx_asr
import onnxruntime
from onnx_asr.adapters import TimestampedResultsAsrAdapter
from onnx_asr.asr import TimestampedResult

from probeloop.speech.arrays import float_samples
from probeloop.speech.audio import SAMPLE_RATE, PcmAudio
from probeloop.speech.ports import (
    RecognizedSegment,
    RecognizedWord,
    SpeechError,
    TranscribeOptions,
    Transcription,
)
from probeloop.speech.segmenter import SegmenterConfig, SpeechSegmenter
from probeloop.speech.silero import SileroVad

TOKEN_S = 0.08  # Parakeet's encoder frame: the duration given to the last token


class ParakeetSpeechToText:
    def __init__(
        self,
        *,
        model: str = "nemo-parakeet-tdt-0.6b-v3",
        quantization: str | None = "int8",
        threads: int = 6,
        max_chunk_s: float = 20.0,
    ) -> None:
        self._model_name = model
        self._quantization = quantization
        self._threads = threads
        self._max_chunk_s = max_chunk_s
        self._model: TimestampedResultsAsrAdapter | None = None
        self._lock = threading.Lock()

    @property
    def engine_ref(self) -> str:
        return f"onnx-asr/{self._model_name}/{self._quantization or 'fp32'}"

    def load(self) -> None:
        """Load the model (downloading it if the Hugging Face cache allows). Idempotent."""
        with self._lock:
            if self._model is not None:
                return
            onnxruntime.disable_telemetry_events()
            options = onnxruntime.SessionOptions()
            options.intra_op_num_threads = self._threads
            options.inter_op_num_threads = 1
            model = onnx_asr.load_model(
                self._model_name,
                quantization=self._quantization,
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )
            self._model = model.with_timestamps()

    async def transcribe(self, audio: PcmAudio, options: TranscribeOptions) -> Transcription:
        if audio.sample_rate != SAMPLE_RATE:
            raise SpeechError("Parakeet needs 16 kHz audio")
        if not audio.data:
            return Transcription((), options.language, self.engine_ref)
        try:
            segments = await asyncio.to_thread(self._recognise, audio)
        except SpeechError:
            raise
        except Exception as exc:
            raise SpeechError(f"Parakeet failed: {type(exc).__name__}") from exc
        return Transcription(tuple(segments), options.language, self.engine_ref)

    def _recognise(self, audio: PcmAudio) -> list[RecognizedSegment]:
        self.load()
        assert self._model is not None
        out = []
        for start_s, chunk in self._chunks(audio):
            result = self._model.recognize(float_samples(chunk), sample_rate=SAMPLE_RATE)
            if not isinstance(result, TimestampedResult):
                raise SpeechError("unexpected result type from onnx-asr")
            text = " ".join(result.text.split())
            if not text:
                continue
            words = assemble_words(
                result.tokens or [], result.timestamps or [], result.logprobs, offset_s=start_s
            )
            logprobs = result.logprobs or []
            out.append(
                RecognizedSegment(
                    start_s=start_s,
                    end_s=start_s + chunk.duration_s,
                    text=text,
                    avg_logprob=sum(logprobs) / len(logprobs) if logprobs else None,
                    words=_clip(words, start_s + chunk.duration_s),
                )
            )
        return out

    def _chunks(self, audio: PcmAudio) -> list[tuple[float, PcmAudio]]:
        if audio.duration_s <= self._max_chunk_s:
            return [(0.0, audio)]
        segmenter = SpeechSegmenter(SileroVad(), SegmenterConfig(max_segment_s=self._max_chunk_s))
        segments = segmenter.feed(audio.data) + segmenter.flush()
        return [(s.start_s, s.audio) for s in segments]


def assemble_words(
    tokens: Sequence[str],
    timestamps: Sequence[float],
    logprobs: Sequence[float] | None,
    *,
    offset_s: float = 0.0,
) -> tuple[RecognizedWord, ...]:
    """Join SentencePiece tokens into words: a leading space starts a new word.

    A word lasts until the next word starts; its probability is the geometric mean of the
    probabilities of its tokens.
    """
    groups: list[list[int]] = []
    for i, token in enumerate(tokens):
        if not groups or token.startswith(" "):
            groups.append([i])
        else:
            groups[-1].append(i)
    words = []
    for n, group in enumerate(groups):
        text = "".join(tokens[i] for i in group).strip()
        if not text:
            continue
        start = timestamps[group[0]]
        end = (
            timestamps[groups[n + 1][0]] if n + 1 < len(groups) else timestamps[group[-1]] + TOKEN_S
        )
        probability = None
        if logprobs:
            probability = math.exp(sum(logprobs[i] for i in group) / len(group))
        words.append(
            RecognizedWord(
                start_s=round(offset_s + start, 3),
                end_s=round(offset_s + end, 3),
                text=text,
                probability=probability,
            )
        )
    return tuple(words)


def _clip(words: tuple[RecognizedWord, ...], end_s: float) -> tuple[RecognizedWord, ...]:
    return tuple(
        RecognizedWord(w.start_s, min(w.end_s, end_s), w.text, w.probability) for w in words
    )
