"""ChatModel adapter for Ollama's native API (`/api/chat`, `/api/show`)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Mapping
from typing import Any

import httpx
import ollama

from probeloop.ai.ports import (
    ChatChunk,
    ChatRequest,
    ChatResult,
    ChatUsage,
    ContextOverflowError,
    LlmError,
    ModelCapabilities,
    estimated_tokens,
)

logger = logging.getLogger(__name__)

# Conservative characters-per-token ratio used only for the pre-flight check. The authoritative
# check uses the `prompt_eval_count` reported by Ollama after the call.
_NS = 1e9


class OllamaChatModel:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        context_window: int,
        keep_alive: str = "30m",
        timeout_s: float = 300.0,
        client: ollama.AsyncClient | None = None,
    ) -> None:
        self._model = model
        self._context_window = context_window
        self._keep_alive = keep_alive
        self._timeout_s = timeout_s
        self._client = client or ollama.AsyncClient(host=base_url, timeout=timeout_s)
        self._capabilities: ModelCapabilities | None = None

    @property
    def model_ref(self) -> str:
        return f"ollama:{self._model}@ctx{self._context_window}"

    async def reconfigure(self, base_url: str) -> None:
        """Replace the connection while the composition root holds the idle guard."""
        previous = self._client
        self._client = ollama.AsyncClient(host=base_url, timeout=self._timeout_s)
        self._capabilities = None
        await previous._client.aclose()

    async def available(self) -> bool:
        """Fresh, bounded installation check; neither loads nor generates with the model."""
        try:
            async with asyncio.timeout(2.0):
                info = await self._client.show(self._model)
            return not info.capabilities or "completion" in info.capabilities
        except (ollama.ResponseError, httpx.HTTPError, TimeoutError):
            return False

    async def capabilities(self) -> ModelCapabilities:
        if self._capabilities is None:
            try:
                info = await self._client.show(self._model)
            except (ollama.ResponseError, httpx.HTTPError) as exc:
                raise LlmError(f"cannot describe model {self._model}: {exc}") from exc
            caps = set(info.capabilities or [])
            self._capabilities = ModelCapabilities(
                context_window=min(self._context_window, _model_context(info.modelinfo)),
                structured_output="json_schema",
                tool_calling="tools" in caps,
                reasoning="thinking" in caps,
                vision="vision" in caps,
            )
        return self._capabilities

    async def complete(self, request: ChatRequest) -> ChatResult:
        parts: list[str] = []
        usage = ChatUsage()
        async for chunk in self.stream(request):
            parts.append(chunk.text)
            if chunk.done and chunk.usage is not None:
                usage = chunk.usage
        return ChatResult(text="".join(parts), usage=usage)

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        caps = await self.capabilities()
        self._preflight(request)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": _messages(request),
            "stream": True,
            "keep_alive": self._keep_alive,
            "options": self._options(request),
        }
        if request.response_schema is not None:
            kwargs["format"] = request.response_schema
        if caps.reasoning:
            kwargs["think"] = request.reasoning != "off"
        try:
            responses = await self._client.chat(**kwargs)
            async for part in responses:
                text = part.message.content or ""
                if part.done:
                    usage = _usage(part)
                    self._check_context(usage)
                    yield ChatChunk(text=text, done=True, usage=usage)
                elif text:
                    yield ChatChunk(text=text)
        except (ollama.ResponseError, httpx.HTTPError) as exc:
            raise LlmError(f"{self.model_ref} request failed: {exc}") from exc

    async def preload(self) -> None:
        """Load the model so the first interview move does not pay the cold-load cost."""
        try:
            await self._client.generate(
                model=self._model,
                keep_alive=self._keep_alive,
                options={"num_ctx": self._context_window},
            )
        except (ollama.ResponseError, httpx.HTTPError) as exc:
            raise LlmError(f"cannot load {self.model_ref}: {exc}") from exc

    def _options(self, request: ChatRequest) -> dict[str, Any]:
        options: dict[str, Any] = {"num_ctx": self._context_window}
        if request.temperature is not None:
            options["temperature"] = request.temperature
        if request.top_p is not None:
            options["top_p"] = request.top_p
        if request.presence_penalty is not None:
            options["presence_penalty"] = request.presence_penalty
        if request.max_output_tokens is not None:
            options["num_predict"] = request.max_output_tokens
        return options

    def _preflight(self, request: ChatRequest) -> None:
        estimated = estimated_tokens(request)
        if estimated > self._context_window:
            raise ContextOverflowError(
                f"estimated {estimated:.0f} tokens exceed the context window of "
                f"{self._context_window}"
            )

    def _check_context(self, usage: ChatUsage) -> None:
        used = (usage.prompt_tokens or 0) + (usage.output_tokens or 0)
        if used >= 0.9 * self._context_window:
            logger.warning(
                "context window nearly full",
                extra={"model": self.model_ref, "used_tokens": used},
            )


def _messages(request: ChatRequest) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": request.instructions}]
    messages += [{"role": m.role, "content": m.content} for m in request.messages]
    return messages


def _usage(part: ollama.ChatResponse) -> ChatUsage:
    return ChatUsage(
        prompt_tokens=part.prompt_eval_count,
        output_tokens=part.eval_count,
        load_s=(part.load_duration or 0) / _NS,
        prompt_s=(part.prompt_eval_duration or 0) / _NS,
        output_s=(part.eval_duration or 0) / _NS,
        stop_reason=part.done_reason,
    )


def _model_context(modelinfo: Mapping[str, Any] | None) -> int:
    for key, value in (modelinfo or {}).items():
        if key.endswith(".context_length") and isinstance(value, int):
            return value
    return 2**31
