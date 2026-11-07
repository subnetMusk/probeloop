"""The stt-worker's internal HTTP API, shared by the worker and its client.

`POST /transcribe` takes raw PCM16 little-endian mono audio as the body
(`application/octet-stream`) and the options as query parameters:

- `engine`: `live` (Parakeet) or `refine` (Whisper turbo);
- `language`, `initial_prompt`, `word_timestamps`, `sample_rate` (only 16000 is accepted).

It answers with `TranscriptionBody`. `GET /health` answers 200 once the preloaded engines are
ready, 503 while they load or after they failed.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from probeloop.speech.ports import RecognizedSegment, RecognizedWord, Transcription

Engine = Literal["live", "refine"]  # a plain alias: FastAPI validates it as a query parameter

MAX_AUDIO_S = 600  # above the 6-minute limit on a single answer (architecture §10.1)
MAX_PROMPT_CHARS = 1000  # Whisper reads at most 224 prompt tokens anyway


class WordBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_s: float
    end_s: float
    text: str
    probability: float | None = None


class SegmentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_s: float
    end_s: float
    text: str
    avg_logprob: float | None = None
    words: list[WordBody] = []


class TranscriptionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine_ref: str
    language: str
    segments: list[SegmentBody]
    processing_s: float

    @classmethod
    def of(cls, transcription: Transcription, processing_s: float) -> TranscriptionBody:
        return cls(
            engine_ref=transcription.engine_ref,
            language=transcription.language,
            processing_s=round(processing_s, 3),
            segments=[
                SegmentBody(
                    start_s=s.start_s,
                    end_s=s.end_s,
                    text=s.text,
                    avg_logprob=s.avg_logprob,
                    words=[
                        WordBody(
                            start_s=w.start_s, end_s=w.end_s, text=w.text, probability=w.probability
                        )
                        for w in s.words
                    ],
                )
                for s in transcription.segments
            ],
        )

    def to_transcription(self) -> Transcription:
        return Transcription(
            segments=tuple(
                RecognizedSegment(
                    start_s=s.start_s,
                    end_s=s.end_s,
                    text=s.text,
                    avg_logprob=s.avg_logprob,
                    words=tuple(
                        RecognizedWord(w.start_s, w.end_s, w.text, w.probability) for w in s.words
                    ),
                )
                for s in self.segments
            ),
            language=self.language,
            engine_ref=self.engine_ref,
        )


class HealthBody(BaseModel):
    status: Literal["loading", "ready", "failed"]
    engines: dict[str, str]  # engine name -> engine_ref
