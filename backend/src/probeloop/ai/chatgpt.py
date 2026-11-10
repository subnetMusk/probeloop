"""ChatModel adapter for the Responses API with ChatGPT plan usage (ADR 0013).

Requests carry the access token of Sign in with ChatGPT and follow the documented preview rules
(https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations): `store` false
and `stream` true on every request; instructions in the `instructions` field; no temperature,
`top_p` or output cap.

Structured output and reasoning effort are not documented for plan usage. They are requested,
and when the provider reports one of them as unsupported the adapter drops it for the rest of
the process: a response schema then becomes a JSON format specification appended to the
instructions, and the application layer validates the output as always. Plan usage errors stop
the call; nothing switches silently to another model or billing path.
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

from probeloop.ai.chatgpt_auth import RESOURCE, SIGN_IN_AGAIN
from probeloop.ai.ports import (
    ChatChunk,
    ChatRequest,
    ChatResult,
    ChatUsage,
    ContextOverflowError,
    LlmError,
    ModelCapabilities,
    UserActionRequiredError,
    estimated_tokens,
)

logger = logging.getLogger(__name__)

type TokenSource = Callable[..., Awaitable[str]]

# Conservative characters-per-token ratio, used only for the pre-flight check.
_MAX_RETRIES = 2
_MAX_RETRY_WAIT_S = 20.0
_SCHEMA_NAME = "response"
USAGE_LIMIT = "ChatGPT plan usage limit reached; see your ChatGPT usage settings"
NOT_ELIGIBLE = "this ChatGPT account cannot use its plan in ProbeLoop"
# Optional request features, by the parameter names a rejection can report.
_FEATURES = {
    "reasoning": "reasoning",
    "reasoning.effort": "reasoning",
    "text": "text",
    "text.format": "text",
    "text.format.schema": "strict",
}


class ChatGptChatModel:
    """A model used through the signed-in user's ChatGPT plan.

    `token` returns a valid access token; called with `refresh=True` it renews it first.
    `reasoning_off` is the effort sent when a request turns reasoning off, or None to send none.
    """

    def __init__(
        self,
        *,
        model: str,
        token: TokenSource,
        context_window: int = 128_000,
        reasoning_off: str | None = "none",
        timeout_s: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._model = model
        self._token = token
        self._context_window = context_window
        self._reasoning_off = reasoning_off
        self._sleep = sleep
        self._disabled: set[str] = set()
        self._client = httpx.AsyncClient(
            base_url=RESOURCE + "/",
            timeout=httpx.Timeout(timeout_s, connect=10.0),
            transport=transport,
        )

    @property
    def model_ref(self) -> str:
        return f"chatgpt:{self._model}"

    async def capabilities(self) -> ModelCapabilities:
        # Doubles as a readiness check: it fails when the user has to sign in again.
        await self._token()
        return ModelCapabilities(
            context_window=self._context_window,
            structured_output="none" if "text" in self._disabled else "json_schema",
            reasoning="reasoning" not in self._disabled,
            sampling_params=False,
            system_role=False,
            preload=False,
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
        usage = ChatUsage()
        finished = refused = False
        try:
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                event = json.loads(line[len("data:") :].strip())
                kind = event.get("type")
                if kind == "response.output_text.delta" and event.get("delta"):
                    yield ChatChunk(text=str(event["delta"]))
                elif kind == "response.refusal.delta":
                    refused = True
                elif kind in ("response.completed", "response.incomplete"):
                    usage = _usage(event.get("response") or {}, time.monotonic() - started)
                    finished = True
                elif kind == "response.failed":
                    error = (event.get("response") or {}).get("error") or {}
                    raise _error(error, status=None, ref=self.model_ref)
                elif kind == "error":
                    raise _error(event, status=None, ref=self.model_ref)
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise LlmError(f"{self.model_ref} stream failed: {type(exc).__name__}") from exc
        finally:
            await response.aclose()
        if refused:
            raise LlmError(f"{self.model_ref} refused the request")
        if not finished:
            raise LlmError(f"{self.model_ref} stream ended before the response completed")
        yield ChatChunk(text="", done=True, usage=usage)

    def body(self, request: ChatRequest) -> dict[str, Any]:
        """The Responses API request body for `request`."""
        instructions = request.instructions
        body: dict[str, Any] = {
            "model": self._model,
            "input": [{"role": m.role, "content": m.content} for m in request.messages],
            "store": False,
            "stream": True,
        }
        schema = request.response_schema
        if schema is not None and "text" not in self._disabled:
            strict = "strict" not in self._disabled
            body["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": _SCHEMA_NAME,
                    "schema": strict_schema(schema) if strict else schema,
                    "strict": strict,
                }
            }
        elif schema is not None:
            instructions += (
                "\n\nReply with one JSON object, and nothing else, that conforms to this JSON "
                f"Schema:\n{json.dumps(schema, ensure_ascii=False)}"
            )
        body["instructions"] = instructions
        if (
            request.reasoning == "off"
            and self._reasoning_off is not None
            and "reasoning" not in self._disabled
        ):
            body["reasoning"] = {"effort": self._reasoning_off}
        return body

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _open(self, request: ChatRequest) -> httpx.Response:
        attempt = 0
        renewed = False
        while True:
            token = await self._token(refresh=renewed)
            body = self.body(request)
            try:
                response = await self._client.send(
                    self._client.build_request(
                        "POST",
                        "responses",
                        json=body,
                        headers={"Authorization": f"Bearer {token}"},
                    ),
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
            code = str(detail.get("code") or "")
            feature = _FEATURES.get(str(detail.get("param") or ""))
            if feature is None and code == "subscription_sharing_unsupported_capability":
                # Without a parameter name, give up the optional features one at a time.
                feature = next((f for f in ("reasoning", "strict", "text") if _sent(f, body)), None)
            if response.status_code == 400 and feature and feature not in self._disabled:
                logger.warning(
                    "request feature unsupported for ChatGPT plan usage; continuing without it",
                    extra={"model": self.model_ref, "feature": feature, "code": code},
                )
                self._disabled.add(feature)
                continue
            if response.status_code == 401 and not renewed:
                renewed = True  # the access token may have been revoked or rotated
                continue
            temporary = code == "subscription_sharing_usage_unavailable" or (
                response.status_code in (429, 500, 502, 503, 504)
                and code != "subscription_sharing_usage_limit_exceeded"
            )
            if temporary and attempt < _MAX_RETRIES:
                attempt += 1
                await self._sleep(_retry_wait(response, attempt))
                continue
            raise _error(detail, status=response.status_code, ref=self.model_ref)

    def _preflight(self, request: ChatRequest) -> None:
        estimated = estimated_tokens(request)
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
        # provider's rejection then switches the model to non-strict schema following.
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


def _sent(feature: str, body: dict[str, Any]) -> bool:
    output_format = (body.get("text") or {}).get("format") or {}
    if feature == "strict":
        return bool(output_format.get("strict"))
    return feature in body


def _usage(response: dict[str, Any], elapsed_s: float) -> ChatUsage:
    usage = response.get("usage") or {}
    incomplete = (response.get("incomplete_details") or {}).get("reason")
    stop = "stop" if response.get("status", "completed") == "completed" else incomplete
    return ChatUsage(
        prompt_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        output_s=elapsed_s,
        stop_reason="length" if stop == "max_output_tokens" else stop,
    )


def _error_body(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    if not isinstance(body, dict):
        return {}
    error = body.get("error")
    if isinstance(error, dict):
        return error
    return {"message": body.get("detail")} if body.get("detail") else {}


def _error(detail: dict[str, Any], *, status: int | None, ref: str) -> LlmError:
    code = str(detail.get("code") or "")
    if code == "subscription_sharing_usage_limit_exceeded":
        return UserActionRequiredError(USAGE_LIMIT)
    if code == "subscription_sharing_user_not_eligible":
        return UserActionRequiredError(NOT_ELIGIBLE)
    if code == "subscription_sharing_invalid_user" or status == 401:
        return UserActionRequiredError(SIGN_IN_AGAIN)
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
