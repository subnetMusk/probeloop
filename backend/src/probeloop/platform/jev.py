"""The TypeSafe Jev service, shared by the adapters that ask it questions (ADR 0020).

Jev is an optional cloud service. Each adapter fixes its own model, question wording and
threshold; this client only sends a request and returns the parsed reply. The API key is machine
configuration stored next to the other account material, outside portable backups. It is only
ever sent in the Authorization header and never logged, and neither are the texts sent.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Literal

import httpx

logger = logging.getLogger(__name__)

API_URL = "https://api.typesafe.ai"
ATTEMPTS = 3
TIMEOUT_S = 4.0
MAX_KEY_CHARS = 512

type KeyCheck = Literal["ready", "key_rejected", "unreachable"]
type Failure = Literal["key_missing", "key_rejected", "unreachable", "failed"]


class JevError(Exception):
    """A request that did not produce a usable reply; `failure` says why, never with content."""

    def __init__(self, failure: Failure) -> None:
        super().__init__(failure)
        self.failure: Failure = failure


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


class JevClient:
    def __init__(
        self,
        key: JevKeyFile,
        *,
        base_url: str = API_URL,
        timeout_s: float = TIMEOUT_S,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.key = key
        self._sleep = sleep
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(timeout_s), transport=transport
        )

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
            raise JevError("key_missing")
        outcome = await self.verify(key)
        if outcome != "ready":
            raise JevError(outcome)

    async def systemone(self, body: dict[str, Any]) -> dict[str, Any]:
        """Send one System One request, retrying transient overload, and return its reply."""
        key = self.key.read()
        if key is None:
            raise JevError("key_missing")
        for attempt in range(1, ATTEMPTS + 1):
            last = attempt == ATTEMPTS
            try:
                response = await self._client.post(
                    "/v1/systemone", content=json.dumps(body), headers=_headers(key)
                )
            except httpx.HTTPError as exc:
                if last:
                    logger.warning("Jev unreachable", extra={"error_type": type(exc).__name__})
                    raise JevError("unreachable") from None
                await self._sleep(0.5 * attempt)
                continue
            status = response.status_code
            if status in (401, 403):
                raise JevError("key_rejected")
            if status in (429, 500, 502, 503, 504, 529) and not last:
                await self._sleep(_retry_wait(response, attempt))
                continue
            if status >= 400:
                logger.warning("Jev request failed", extra={"status": status})
                raise JevError("unreachable" if status >= 429 else "failed")
            try:
                payload = response.json()
            except ValueError:
                raise JevError("failed") from None
            if not isinstance(payload, dict):
                raise JevError("failed")
            return payload
        raise JevError("unreachable")  # pragma: no cover - the loop always returns

    async def aclose(self) -> None:
        await self._client.aclose()


def noul_scores(payload: dict[str, Any], ids: list[str]) -> dict[str, float]:
    """The probability of each question id, or JevError when one is missing or out of range."""
    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise JevError("failed")
    scores = {}
    for question in ids:
        entry = answers.get(question)
        score = entry.get("noul") if isinstance(entry, dict) else None
        if not isinstance(score, int | float) or not 0.0 <= score <= 1.0:
            raise JevError("failed")
        scores[question] = float(score)
    return scores


def served_model(payload: dict[str, Any], requested: str) -> str:
    served = payload.get("model")
    return served if isinstance(served, str) and served else requested


def _headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _retry_wait(response: httpx.Response, attempt: int) -> float:
    try:
        wait = float(response.headers.get("retry-after", ""))
    except ValueError:
        wait = 0.5 * attempt
    return min(max(wait, 0.0), 2.0)
