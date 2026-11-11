"""The fine-tuned stated-limit classifier, loaded once without blocking application startup."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Literal

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from probeloop.interview.application.ports import LimitReaderUnavailable, LimitReading

logger = logging.getLogger(__name__)
type LoadState = Literal["missing", "loading", "ready", "failed", "closed"]


@dataclass(frozen=True)
class ModelSpec:
    id: str
    threshold: float
    max_tokens: int
    question_chars: int
    files: dict[str, str]
    sizes: dict[str, int]


def model_spec() -> ModelSpec:
    value = json.loads(files(__package__).joinpath("limits_model.json").read_text("utf-8"))
    return ModelSpec(**value)


def verify_model(directory: Path, spec: ModelSpec) -> None:
    for name, expected in spec.files.items():
        path = directory / name
        if path.stat().st_size != spec.sizes[name]:
            raise ValueError("stated-limit model checksum or size mismatch")
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            raise ValueError("stated-limit model checksum mismatch")


def answer_sentences(answer: str) -> list[str]:
    # This is the segmentation used to construct the training labels and the ONNX pilot.
    return [s.strip() for s in re.split(r"(?<=[.!?;])\s+", answer) if len(s.strip()) > 3]


class OnnxStatedLimitReader:
    def __init__(self, directory: Path, *, threads: int = 2) -> None:
        if threads < 1:
            raise ValueError("stated-limit threads must be positive")
        self._directory = directory
        self._threads = threads
        self._spec = model_spec()
        self._state: LoadState = "missing"
        self._task: asyncio.Task[None] | None = None
        self._bundle: tuple[ort.InferenceSession, Tokenizer] | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> LoadState:
        return self._state

    @property
    def model_ref(self) -> str:
        digest = self._spec.files["limits-int8.onnx"][:12]
        return f"{self._spec.id}@{digest}:threshold={self._spec.threshold}"

    def start(self) -> None:
        if self._task is not None or self._state == "closed":
            return
        if not all((self._directory / name).is_file() for name in self._spec.files):
            self._state = "missing"
            return
        self._state = "loading"
        self._task = asyncio.create_task(self._load(), name="stated-limit-model")

    async def _load(self) -> None:
        started = time.perf_counter()
        try:
            bundle = await asyncio.to_thread(self._load_sync)
        except Exception as exc:
            self._state = "failed"
            logger.warning(
                "stated-limit model could not load", extra={"error_type": type(exc).__name__}
            )
            return
        self._bundle = bundle
        self._state = "ready"
        logger.info(
            "stated-limit model ready", extra={"load_s": round(time.perf_counter() - started, 3)}
        )

    def _load_sync(self) -> tuple[ort.InferenceSession, Tokenizer]:
        verify_model(self._directory, self._spec)
        options = ort.SessionOptions()
        options.intra_op_num_threads = self._threads
        options.inter_op_num_threads = 1
        options.add_session_config_entry("session.intra_op.allow_spinning", "0")
        options.add_session_config_entry("session.inter_op.allow_spinning", "0")
        session = ort.InferenceSession(
            str(self._directory / "limits-int8.onnx"), options, providers=["CPUExecutionProvider"]
        )
        inputs = {item.name: item.type for item in session.get_inputs()}
        if inputs != {"input_ids": "tensor(int64)", "attention_mask": "tensor(int64)"}:
            raise ValueError("unsupported stated-limit model inputs")
        tokenizer = Tokenizer.from_file(str(self._directory / "tokenizer/tokenizer.json"))
        tokenizer.enable_truncation(max_length=self._spec.max_tokens, strategy="longest_first")
        tokenizer.enable_padding()
        self._score(session, tokenizer, "Question?", ["A synthetic answer."])
        return session, tokenizer

    def _score(
        self,
        session: ort.InferenceSession,
        tokenizer: Tokenizer,
        question: str,
        sentences: list[str],
    ) -> list[float]:
        encoded = tokenizer.encode_batch(
            [(question[-self._spec.question_chars :], s) for s in sentences]
        )
        feeds = {
            "input_ids": np.asarray([item.ids for item in encoded], dtype=np.int64),
            "attention_mask": np.asarray([item.attention_mask for item in encoded], dtype=np.int64),
        }
        logits = np.asarray(session.run(None, feeds)[0])
        if logits.shape != (len(sentences), 2) or not np.isfinite(logits).all():
            raise ValueError("invalid stated-limit scores")
        scores = np.exp(logits - logits.max(axis=1, keepdims=True))
        return [float(p) for p in scores[:, 1] / scores.sum(axis=1)]

    def _read_sync(self, question: str, answer: str) -> LimitReading:
        assert self._bundle is not None
        session, tokenizer = self._bundle
        sentences = answer_sentences(answer)
        quotes: list[str] = []
        for offset in range(0, len(sentences), 16):
            batch = sentences[offset : offset + 16]
            scores = self._score(session, tokenizer, question, batch)
            quotes.extend(
                s for s, score in zip(batch, scores, strict=True) if score >= self._spec.threshold
            )
        return LimitReading(tuple(dict.fromkeys(quotes)), self.model_ref)

    async def read(self, question: str, answer: str) -> LimitReading:
        if self._state != "ready":
            raise LimitReaderUnavailable("stated-limit model is not ready")
        async with self._lock:
            if self._state != "ready":
                raise LimitReaderUnavailable("stated-limit model is not ready")
            started = time.perf_counter()
            try:
                result = await asyncio.to_thread(self._read_sync, question, answer)
            except Exception as exc:
                self._state = "failed"
                logger.warning(
                    "stated-limit inference failed", extra={"error_type": type(exc).__name__}
                )
                raise LimitReaderUnavailable("stated-limit inference failed") from None
            logger.info(
                "stated-limit reading completed",
                extra={"duration_ms": round(1000 * (time.perf_counter() - started), 1)},
            )
            return result

    async def check(self) -> None:
        if self._state != "ready":
            raise LimitReaderUnavailable("Laya is unavailable; check its model in Settings")

    async def reload(self) -> None:
        """Retry a missing/failed installation without replacing a healthy loaded model."""
        if self._state in ("loading", "ready", "closed"):
            return
        if self._task is not None:
            await self._task
        self._task = None
        self.start()

    async def close(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        async with self._lock:
            self._state = "closed"
            self._bundle = None
