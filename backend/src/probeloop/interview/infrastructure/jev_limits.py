"""Stated-limit reading with TypeSafe Jev, an optional cloud service (ADR 0020).

One request per answer: the interviewer's question and the answer's sentences form the state,
and one Noul question per sentence asks whether it states a limit of the candidate. The model
version, the question wording and the threshold are fixed and recorded with every reading.

The API key is machine configuration stored next to the other account material, outside
portable backups. It is only ever sent in the Authorization header and never logged.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Literal

import httpx

from probeloop.interview.application.limits import answer_sentences
from probeloop.interview.application.ports import LimitReaderUnavailable, LimitReading

logger = logging.getLogger(__name__)

API_URL = "https://api.typesafe.ai"
MODEL = "jev-1.14.0"
THRESHOLD = 0.5
WORDING = "limits.v2"
ATTEMPTS = 3
TIMEOUT_S = 4.0
MAX_KEY_CHARS = 512

KEY_MISSING = "add a Jev API key in Settings"
KEY_REJECTED = "the Jev API key was rejected; check it in Settings"
UNREACHABLE = "Jev is unreachable; check the connection and try again"
FAILED = "Jev could not read the answer; try again"

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

type KeyCheck = Literal["ready", "key_rejected", "unreachable"]


class JevKeyFile:
    """The API key in its own owner-only file in the data volume."""

    def __init__(self, directory: Path) -> None:
        self._path = directory / "api-key"

    @property
    def configured(self) -> bool:
        return self.read() is not None

    def read(self) -> str | None:
        try:
            key = self._path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return None
        except OSError:
            logger.warning("unreadable Jev API key; add it again in Settings")
            return None
        return key or None

    def save(self, key: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(key)
        temporary.replace(self._path)

    def clear(self) -> None:
        self._path.unlink(missing_ok=True)


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
        self._sleep = sleep
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(TIMEOUT_S), transport=transport
        )

    @property
    def model_ref(self) -> str:
        return f"typesafe:{MODEL}:{WORDING}:threshold={THRESHOLD}"

    async def verify(self, key: str) -> KeyCheck:
        """Whether `key` is accepted, checked by listing the account's models."""
        try:
            response = await self._client.get("/v1/models", headers=_headers(key))
        except httpx.HTTPError:
            return "unreachable"
        if response.status_code in (401, 403):
            return "key_rejected"
        return "ready" if response.status_code < 400 else "unreachable"

    async def check(self) -> None:
        key = self.key.read()
        if key is None:
            raise LimitReaderUnavailable(KEY_MISSING)
        outcome = await self.verify(key)
        if outcome == "key_rejected":
            raise LimitReaderUnavailable(KEY_REJECTED)
        if outcome == "unreachable":
            raise LimitReaderUnavailable(UNREACHABLE)

    async def read(self, question: str, answer: str) -> LimitReading:
        sentences = answer_sentences(answer)
        if not sentences:
            return LimitReading((), self.model_ref)
        key = self.key.read()
        if key is None:
            raise LimitReaderUnavailable(KEY_MISSING)
        started = time.perf_counter()
        payload = await self._post(key, request_body(question, sentences))
        answers = payload.get("answers")
        if not isinstance(answers, dict):
            raise LimitReaderUnavailable(FAILED)
        quotes = []
        for i, sentence in enumerate(sentences):
            entry = answers.get(f"s{i}")
            score = entry.get("noul") if isinstance(entry, dict) else None
            if not isinstance(score, int | float) or not 0.0 <= score <= 1.0:
                raise LimitReaderUnavailable(FAILED)
            if score >= THRESHOLD:
                quotes.append(sentence)
        served = payload.get("model")
        model = served if isinstance(served, str) and served else MODEL
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

    async def _post(self, key: str, body: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(1, ATTEMPTS + 1):
            last = attempt == ATTEMPTS
            try:
                response = await self._client.post(
                    "/v1/systemone", content=json.dumps(body), headers=_headers(key)
                )
            except httpx.HTTPError as exc:
                if last:
                    logger.warning("Jev unreachable", extra={"error_type": type(exc).__name__})
                    raise LimitReaderUnavailable(UNREACHABLE) from None
                await self._sleep(0.5 * attempt)
                continue
            status = response.status_code
            if status in (401, 403):
                raise LimitReaderUnavailable(KEY_REJECTED)
            if status in (429, 500, 502, 503, 504, 529) and not last:
                await self._sleep(_retry_wait(response, attempt))
                continue
            if status >= 400:
                logger.warning("Jev request failed", extra={"status": status})
                raise LimitReaderUnavailable(UNREACHABLE if status >= 429 else FAILED)
            try:
                payload = response.json()
            except ValueError:
                raise LimitReaderUnavailable(FAILED) from None
            if not isinstance(payload, dict):
                raise LimitReaderUnavailable(FAILED)
            return payload
        raise LimitReaderUnavailable(UNREACHABLE)  # pragma: no cover - the loop always returns


def _headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _retry_wait(response: httpx.Response, attempt: int) -> float:
    try:
        wait = float(response.headers.get("retry-after", ""))
    except ValueError:
        wait = 0.5 * attempt
    return min(max(wait, 0.0), 2.0)
