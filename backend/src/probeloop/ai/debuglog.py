"""Opt-in JSONL log of LLM calls, for debugging prompts.

The log contains prompts and outputs, which may include personal data. It is disabled by default
and, when enabled, written only inside the data directory.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from dataclasses import asdict
from pathlib import Path

from probeloop.ai.ports import ChatChunk, ChatModel, ChatRequest, ChatResult, ModelCapabilities


class DebugLogChatModel:
    def __init__(self, inner: ChatModel, path: Path) -> None:
        self._inner = inner
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def model_ref(self) -> str:
        return self._inner.model_ref

    async def capabilities(self) -> ModelCapabilities:
        return await self._inner.capabilities()

    async def complete(self, request: ChatRequest) -> ChatResult:
        started = time.time()
        result = await self._inner.complete(request)
        self._write(request, result.text, asdict(result.usage), started)
        return result

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        started = time.time()
        parts: list[str] = []
        usage: dict[str, object] = {}
        async for chunk in self._inner.stream(request):
            parts.append(chunk.text)
            if chunk.done and chunk.usage is not None:
                usage = asdict(chunk.usage)
            yield chunk
        self._write(request, "".join(parts), usage, started)

    def _write(
        self, request: ChatRequest, output: str, usage: dict[str, object], started: float
    ) -> None:
        record = {
            "at": started,
            "duration_s": round(time.time() - started, 3),
            "model": self._inner.model_ref,
            "request": asdict(request),
            "output": output,
            "usage": usage,
        }
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
