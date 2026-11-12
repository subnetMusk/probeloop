"""Stated-limit reading with TypeSafe Jev, an optional cloud service (ADR 0020).

One request per answer: the interviewer's question and the answer's sentences form the state,
and one Noul question per sentence asks whether it states a limit of the candidate. The model
version, the question wording and the threshold are fixed and recorded with every reading. The
shared client in `probeloop.platform.jev` keeps the key and sends the request.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from probeloop.interview.application.limits import answer_sentences
from probeloop.interview.application.ports import LimitReaderUnavailable, LimitReading
from probeloop.platform.jev import (
    API_URL,
    ATTEMPTS,
    MAX_KEY_CHARS,
    TIMEOUT_S,
    Failure,
    JevClient,
    JevError,
    JevKeyFile,
    KeyCheck,
    noul_scores,
    served_model,
)

__all__ = [
    "API_URL",
    "ATTEMPTS",
    "CRITERIA",
    "FAILED",
    "INSTRUCTIONS",
    "KEY_MISSING",
    "KEY_REJECTED",
    "MAX_KEY_CHARS",
    "MODEL",
    "THRESHOLD",
    "TIMEOUT_S",
    "UNREACHABLE",
    "WORDING",
    "JevKeyFile",
    "JevStatedLimitReader",
    "KeyCheck",
    "request_body",
]

logger = logging.getLogger(__name__)

MODEL = "jev-1.14.0"
THRESHOLD = 0.5
WORDING = "limits.v2"

KEY_MISSING = "add a Jev API key in Settings"
KEY_REJECTED = "the Jev API key was rejected; check it in Settings"
UNREACHABLE = "Jev is unreachable; check the connection and try again"
FAILED = "Jev could not read the answer; try again"
_MESSAGES: dict[Failure, str] = {
    "key_missing": KEY_MISSING,
    "key_rejected": KEY_REJECTED,
    "unreachable": UNREACHABLE,
    "failed": FAILED,
}

# Fixed before the evaluation of 2026-11-11 on synthetic interview sentences; changing it
# requires a new evaluation and a new WORDING identifier.
INSTRUCTIONS = (
    "Does `candidate_answer_sentences[{index}]` say that the candidate does not remember "
    "something, or has not had the experience the interviewer asked about?"
)
CRITERIA = {
    "true": "The candidate says that they themselves do not remember something, do not have the "
    "details or information about it, or have not had the experience the interviewer asked "
    "about.",
    "false": "Anything else, including assumptions, hedged conclusions, limits of a dataset, "
    "method or analysis being described, statements about other people, and statements of "
    "what the candidate does remember.",
}


def request_body(question: str, sentences: list[str]) -> dict[str, Any]:
    return {
        "model": MODEL,
        "state": {"interviewer_question": question, "candidate_answer_sentences": sentences},
        "questions": {
            f"s{i}": {
                "type": "noul",
                "instructions": INSTRUCTIONS.format(index=i),
                "criteria": CRITERIA,
            }
            for i in range(len(sentences))
        },
    }


class JevStatedLimitReader:
    def __init__(
        self,
        key: JevKeyFile,
        *,
        base_url: str = API_URL,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.key = key
        self._client = JevClient(
            key, base_url=base_url, timeout_s=TIMEOUT_S, transport=transport, sleep=sleep
        )

    @property
    def model_ref(self) -> str:
        return f"typesafe:{MODEL}:{WORDING}:threshold={THRESHOLD}"

    async def verify(self, key: str) -> KeyCheck:
        """Whether `key` is accepted, checked by listing the account's models."""
        return await self._client.verify(key)

    async def check(self) -> None:
        try:
            await self._client.check()
        except JevError as exc:
            raise LimitReaderUnavailable(_MESSAGES[exc.failure]) from None

    async def read(self, question: str, answer: str) -> LimitReading:
        sentences = answer_sentences(answer)
        if not sentences:
            return LimitReading((), self.model_ref)
        started = time.perf_counter()
        ids = [f"s{i}" for i in range(len(sentences))]
        try:
            payload = await self._client.systemone(request_body(question, sentences))
            scores = noul_scores(payload, ids)
        except JevError as exc:
            raise LimitReaderUnavailable(_MESSAGES[exc.failure]) from None
        quotes = [s for s, i in zip(sentences, ids, strict=True) if scores[i] >= THRESHOLD]
        model = served_model(payload, MODEL)
        logger.info(
            "stated-limit reading completed",
            extra={
                "engine": "jev",
                "model": model,
                "duration_ms": round(1000 * (time.perf_counter() - started), 1),
            },
        )
        return LimitReading(
            tuple(dict.fromkeys(quotes)), f"typesafe:{model}:{WORDING}:threshold={THRESHOLD}"
        )

    async def aclose(self) -> None:
        await self._client.aclose()
