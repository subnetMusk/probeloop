"""ChatModel adapter for the OpenAI Chat Completions API and servers compatible with it.

Plain HTTP through httpx: one endpoint is used, and the same code then works with any server
that implements Chat Completions. Prompts never appear in errors or logs.
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import httpx

from probeloop.ai.ports import (
    ChatChunk,
    ChatRequest,
    ChatResult,
    ChatUsage,
    ContextOverflowError,
    LlmError,
    ModelCapabilities,
)

logger = logging.getLogger(__name__)

OPENAI_BASE_URL = "https://api.openai.com/v1"
# Conservative characters-per-token ratio, used only for the pre-flight check.
_CHARS_PER_TOKEN = 3.0
_RETRY_STATUS = frozenset({408, 409, 429, 500, 502, 503, 504})
_MAX_RETRIES = 2
_MAX_RETRY_WAIT_S = 20.0
_SCHEMA_NAME = "response"


class OpenAIChatModel:
    """A Chat Completions model.

    `reasoning_off` is the `reasoning_effort` sent when a request turns reasoning off: "none" for
    models that support it, "low" for those that do not, or None for models without reasoning
    control. Sampling parameters and output caps are sent only when no reasoning tokens are
    generated, as reasoning models reject sampling parameters and count reasoning tokens against
    the cap.
    """

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str = OPENAI_BASE_URL,
        context_window: int = 128_000,
        reasoning_off: str | None = "none",
        timeout_s: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._model = model
        self._context_window = context_window
        self._reasoning_off = reasoning_off
        self._official = base_url.rstrip("/") == OPENAI_BASE_URL
        self._strict = True
        self._sleep = sleep
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(timeout_s, connect=10.0),
            transport=transport,
        )

    @property
    def model_ref(self) -> str:
        provider = "openai" if self._official else "openai-compatible"
        return f"{provider}:{self._model}"

    async def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            context_window=self._context_window,
            structured_output="json_schema",
            reasoning=self._reasoning_off is not None,
        )

    async def complete(self, request: ChatRequest) -> ChatResult:
        parts: list[str] = []
        usage = ChatUsage()
        async for chunk in self.stream(request):
            parts.append(chunk.text)
            if chunk.done and chunk.usage is not None:
                usage = chunk.usage
        return ChatResult(text="".join(parts), usage=usage)

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        self._preflight(request)
        started = time.monotonic()
        response = await self._open(request)
        prompt_tokens: int | None = None
        output_tokens: int | None = None
        stop_reason: str | None = None
        refused = False
        try:
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[len("data:") :].strip()
                if data == "[DONE]":
                    break
                event = json.loads(data)
                if isinstance(event.get("error"), dict):
                    raise _error(event["error"], status=None, ref=self.model_ref)
                if isinstance(event.get("usage"), dict):
                    prompt_tokens = event["usage"].get("prompt_tokens")
                    output_tokens = event["usage"].get("completion_tokens")
                for choice in event.get("choices") or ():
                    delta = choice.get("delta") or {}
                    refused = refused or bool(delta.get("refusal"))
                    if delta.get("content"):
                        yield ChatChunk(text=delta["content"])
                    stop_reason = choice.get("finish_reason") or stop_reason
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise LlmError(f"{self.model_ref} stream failed: {type(exc).__name__}") from exc
        finally:
            await response.aclose()
        if refused:
            raise LlmError(f"{self.model_ref} refused the request")
        yield ChatChunk(
            text="",
            done=True,
            usage=ChatUsage(
                prompt_tokens=prompt_tokens,
                output_tokens=output_tokens,
                output_s=time.monotonic() - started,
                stop_reason=stop_reason,
            ),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def body(self, request: ChatRequest) -> dict[str, Any]:
        """The Chat Completions request body for `request`."""
        if self._reasoning_off is None:
            effort, reasoning_free = None, True
        elif request.reasoning == "off":
            effort, reasoning_free = self._reasoning_off, self._reasoning_off == "none"
        else:
            effort, reasoning_free = None, False
        body: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": "system", "content": request.instructions}]
            + [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if effort is not None:
            body["reasoning_effort"] = effort
        if reasoning_free:
            if request.temperature is not None:
                body["temperature"] = request.temperature
            if request.top_p is not None:
                body["top_p"] = request.top_p
            # The provider default is 0, so only a non-zero penalty changes anything.
            if request.presence_penalty:
                body["presence_penalty"] = request.presence_penalty
            if request.max_output_tokens is not None:
                body["max_completion_tokens"] = request.max_output_tokens
        if request.response_schema is not None:
            schema = (
                strict_schema(request.response_schema) if self._strict else request.response_schema
            )
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": _SCHEMA_NAME, "schema": schema, "strict": self._strict},
            }
        return body

    async def _open(self, request: ChatRequest) -> httpx.Response:
        attempt = 0
        while True:
            try:
                response = await self._client.send(
                    self._client.build_request("POST", "chat/completions", json=self.body(request)),
                    stream=True,
                )
            except httpx.TransportError as exc:
                if attempt < _MAX_RETRIES:
                    attempt += 1
                    await self._sleep(2.0**attempt)
                    continue
                raise LlmError(f"{self.model_ref} unreachable: {type(exc).__name__}") from exc
            if response.status_code < 400:
                return response
            await response.aread()
            await response.aclose()
            detail = _error_body(response)
            if (
                response.status_code == 400
                and self._strict
                and request.response_schema is not None
                and detail.get("param") == "response_format"
            ):
                # Some schemas fall outside the strict subset. The output is validated in the
                # application layer anyway, so continue with best-effort schema following.
                logger.warning(
                    "strict structured output rejected; continuing without strict mode",
                    extra={"model": self.model_ref, "code": detail.get("code")},
                )
                self._strict = False
                continue
            if response.status_code in _RETRY_STATUS and attempt < _MAX_RETRIES:
                attempt += 1
                await self._sleep(_retry_wait(response, attempt))
                continue
            raise _error(detail, status=response.status_code, ref=self.model_ref)

    def _preflight(self, request: ChatRequest) -> None:
        chars = len(request.instructions) + sum(len(m.content) for m in request.messages)
        estimated = chars / _CHARS_PER_TOKEN + (request.max_output_tokens or 0)
        if estimated > self._context_window:
            raise ContextOverflowError(
                f"estimated {estimated:.0f} tokens exceed the context window of "
                f"{self._context_window}"
            )


def strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """`schema` in the form strict structured outputs require.

    Every object lists all its properties as required and forbids others; a property that was
    optional keeps its type, which already admits its default. `None` defaults carry no
    information and are dropped, and a `$ref` with sibling keywords is inlined.
    """
    root = copy.deepcopy(schema)
    result: dict[str, Any] = _strict(root, root)
    return result


def _strict(node: Any, root: dict[str, Any]) -> Any:
    if isinstance(node, list):
        return [_strict(item, root) for item in node]
    if not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if isinstance(ref, str) and len(node) > 1:
        target = _resolve(ref, root)
        node = {**target, **{k: v for k, v in node.items() if k != "$ref"}}
    all_of = node.get("allOf")
    if isinstance(all_of, list) and len(all_of) == 1 and isinstance(all_of[0], dict):
        node = {**{k: v for k, v in node.items() if k != "allOf"}, **all_of[0]}
    if "default" in node and node["default"] is None:
        node = {k: v for k, v in node.items() if k != "default"}
    result = {key: _strict(value, root) for key, value in node.items()}
    properties = result.get("properties")
    if result.get("type") == "object" or isinstance(properties, dict):
        # An explicit schema for extra keys (a mapping) has no strict form; it is kept, and the
        # provider's rejection then switches the model to best-effort schema following.
        result.setdefault("additionalProperties", False)
        result["required"] = list(properties) if isinstance(properties, dict) else []
    return result


def _resolve(ref: str, root: dict[str, Any]) -> dict[str, Any]:
    node: Any = root
    for part in ref.removeprefix("#/").split("/"):
        node = node[part]
    if not isinstance(node, dict):
        raise LlmError(f"unsupported schema reference {ref}")
    return {str(key): value for key, value in node.items()}


def _error_body(response: httpx.Response) -> dict[str, Any]:
    try:
        error = response.json().get("error")
    except (json.JSONDecodeError, AttributeError):
        return {}
    return error if isinstance(error, dict) else {}


def _error(detail: dict[str, Any], *, status: int | None, ref: str) -> LlmError:
    code = detail.get("code")
    # Provider messages describe parameters and limits, not the prompt; keep them short.
    message = str(detail.get("message") or "no detail")[:300]
    prefix = f"{ref} request failed" + (f" ({status})" if status else "")
    if code == "context_length_exceeded":
        return ContextOverflowError(f"{prefix}: {message}")
    return LlmError(f"{prefix}: {code or detail.get('type') or 'error'}: {message}")


def _retry_wait(response: httpx.Response, attempt: int) -> float:
    try:
        wait = float(response.headers.get("retry-after", ""))
    except ValueError:
        wait = 2.0**attempt
    return min(max(wait, 0.0), _MAX_RETRY_WAIT_S)
