"""The ChatGPT plan adapter against scripted Responses API streams; no provider is contacted."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from probeloop.ai.chatgpt import USAGE_LIMIT, ChatGptChatModel, strict_schema
from probeloop.ai.ports import (
    ChatMessage,
    ChatRequest,
    ContextOverflowError,
    LlmError,
    UserActionRequiredError,
)

PROMPT = "Synthetic answer about database indexes."
SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]}
REQUEST = ChatRequest(
    instructions="Reply in JSON.",
    messages=(ChatMessage("user", PROMPT), ChatMessage("assistant", "Earlier reply.")),
    response_schema=SCHEMA,
    temperature=0.1,
    presence_penalty=1.5,
    max_output_tokens=200,
)


def stream(text: str = '{"answer": "ok"}', final: str = "response.completed") -> bytes:
    half = len(text) // 2
    events: list[dict[str, Any]] = [
        {"type": "response.created", "response": {"status": "in_progress"}},
        {"type": "response.output_text.delta", "delta": text[:half]},
        {"type": "response.output_text.delta", "delta": text[half:]},
        {
            "type": final,
            "response": {
                "status": "completed" if final == "response.completed" else "incomplete",
                "incomplete_details": {"reason": "max_output_tokens"},
                "usage": {"input_tokens": 40, "output_tokens": 9},
            },
        },
    ]
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


def failure(status: int, code: str, param: str | None = None) -> httpx.Response:
    error = {"code": code, "param": param, "message": "Synthetic provider error."}
    return httpx.Response(status, json={"error": error})


class Provider:
    def __init__(self, *responses: httpx.Response) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []
        self.waits: list[float] = []
        self.refreshes = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responses.pop(0)

    def body(self, index: int = -1) -> Any:
        return json.loads(self.requests[index].content)

    async def token(self, *, refresh: bool = False) -> str:
        self.refreshes += refresh
        return f"token-{self.refreshes}"

    async def sleep(self, seconds: float) -> None:
        self.waits.append(seconds)


def model(provider: Provider, **options: Any) -> ChatGptChatModel:
    return ChatGptChatModel(
        model="gpt-test",
        token=provider.token,
        transport=httpx.MockTransport(provider),
        sleep=provider.sleep,
        **options,
    )


def ok(text: str = '{"answer": "ok"}') -> httpx.Response:
    return httpx.Response(200, content=stream(text))


async def test_requests_follow_the_plan_usage_rules() -> None:
    provider = Provider(ok())
    result = await model(provider).complete(REQUEST)
    assert result.text == '{"answer": "ok"}'
    assert (result.usage.prompt_tokens, result.usage.output_tokens) == (40, 9)
    assert result.usage.stop_reason == "stop"
    request = provider.requests[0]
    assert str(request.url) == "https://api.openai.com/v1/responses"
    assert request.headers["authorization"] == "Bearer token-0"
    body = provider.body()
    assert (body["store"], body["stream"]) == (False, True)
    assert body["instructions"] == "Reply in JSON."
    assert body["input"] == [
        {"role": "user", "content": PROMPT},
        {"role": "assistant", "content": "Earlier reply."},
    ]
    for rejected in ("temperature", "top_p", "max_output_tokens", "presence_penalty"):
        assert rejected not in body
    assert body["reasoning"] == {"effort": "none"}
    output_format = body["text"]["format"]
    assert (output_format["type"], output_format["strict"]) == ("json_schema", True)
    assert output_format["schema"]["additionalProperties"] is False


async def test_an_unsupported_schema_becomes_a_format_specification() -> None:
    provider = Provider(
        failure(400, "subscription_sharing_unsupported_capability", "text"), ok(), ok()
    )
    chat = model(provider)
    await chat.complete(REQUEST)
    await chat.complete(REQUEST)
    retried = provider.body(1)
    assert "text" not in retried
    assert retried["instructions"].startswith("Reply in JSON.\n\nReply with one JSON object")
    assert '"answer"' in retried["instructions"]
    assert "text" not in provider.body(2)  # remembered for later calls
    assert (await chat.capabilities()).structured_output == "none"


async def test_unnamed_unsupported_features_are_dropped_reasoning_first() -> None:
    unsupported = "subscription_sharing_unsupported_capability"
    provider = Provider(failure(400, unsupported), failure(400, unsupported), ok())
    await model(provider).complete(REQUEST)
    assert "reasoning" not in provider.body(1)
    assert provider.body(1)["text"]["format"]["strict"] is True
    assert provider.body(2)["text"]["format"]["strict"] is False


async def test_a_rejected_token_is_renewed_once() -> None:
    provider = Provider(httpx.Response(401, json={"detail": "denied"}), ok())
    await model(provider).complete(REQUEST)
    assert provider.requests[1].headers["authorization"] == "Bearer token-1"
    provider = Provider(httpx.Response(401, json={}), httpx.Response(401, json={}))
    with pytest.raises(UserActionRequiredError, match="sign in with ChatGPT again"):
        await model(provider).complete(REQUEST)


async def test_the_usage_limit_stops_without_retrying() -> None:
    provider = Provider(failure(429, "subscription_sharing_usage_limit_exceeded"))
    with pytest.raises(UserActionRequiredError) as raised:
        await model(provider).complete(REQUEST)
    assert str(raised.value) == USAGE_LIMIT
    assert len(provider.requests) == 1


async def test_temporary_unavailability_is_retried_with_backoff() -> None:
    provider = Provider(
        failure(503, "subscription_sharing_usage_unavailable"),
        httpx.Response(429, headers={"retry-after": "3"}, json={"error": {}}),
        ok(),
    )
    assert (await model(provider).complete(REQUEST)).text == '{"answer": "ok"}'
    assert provider.waits == [2.0, 3.0]


async def test_a_failed_response_in_the_stream_is_an_error() -> None:
    failed = {
        "type": "response.failed",
        "response": {"error": {"code": "subscription_sharing_usage_limit_exceeded"}},
    }
    body = f"data: {json.dumps(failed)}\n\n".encode()
    with pytest.raises(UserActionRequiredError):
        await model(Provider(httpx.Response(200, content=body))).complete(REQUEST)


async def test_incomplete_and_refused_responses() -> None:
    incomplete = httpx.Response(200, content=stream(final="response.incomplete"))
    result = await model(Provider(incomplete)).complete(REQUEST)
    assert result.usage.stop_reason == "length"
    refusal = {"type": "response.refusal.delta", "delta": "No."}
    done = {"type": "response.completed", "response": {"status": "completed"}}
    body = "".join(f"data: {json.dumps(e)}\n\n" for e in (refusal, done)).encode()
    with pytest.raises(LlmError, match="refused"):
        await model(Provider(httpx.Response(200, content=body))).complete(REQUEST)
    truncated = b'data: {"type": "response.output_text.delta", "delta": "{"}\n\n'
    with pytest.raises(LlmError, match="before the response completed"):
        await model(Provider(httpx.Response(200, content=truncated))).complete(REQUEST)


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (lambda: failure(403, "subscription_sharing_user_not_eligible"), UserActionRequiredError),
        (lambda: failure(400, "context_length_exceeded", "input"), ContextOverflowError),
        (lambda: failure(400, "invalid_value", "model"), LlmError),
    ],
)
async def test_errors_never_carry_the_prompt_or_the_token(response: Any, error: type) -> None:
    with pytest.raises(error) as raised:
        await model(Provider(response())).complete(REQUEST)
    assert PROMPT not in str(raised.value)
    assert "token-" not in str(raised.value)


async def test_capabilities_check_the_sign_in_and_skip_the_warm_up() -> None:
    async def signed_out(*, refresh: bool = False) -> str:
        raise UserActionRequiredError("sign in with ChatGPT again in Settings")

    caps = await model(Provider(ok())).capabilities()
    assert (caps.preload, caps.sampling_params, caps.system_role) == (False, False, False)
    chat = ChatGptChatModel(model="gpt-test", token=signed_out)
    with pytest.raises(UserActionRequiredError):
        await chat.capabilities()
    assert chat.model_ref == "chatgpt:gpt-test"


async def test_prompts_that_cannot_fit_are_rejected_before_the_call() -> None:
    provider = Provider(ok())
    huge = ChatRequest(instructions="x", messages=(ChatMessage("user", "word " * 3000),))
    with pytest.raises(ContextOverflowError):
        await model(provider, context_window=1024).complete(huge)
    assert provider.requests == []


class Inner(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quote: str
    turn: int | None = None


class Outer(BaseModel):
    items: list[Inner] = []
    note: str | None = None
    mapping: dict[str, int] = {}


def test_strict_schemas_require_every_property_and_forbid_others() -> None:
    schema = strict_schema(Outer.model_json_schema())
    assert schema["required"] == ["items", "note", "mapping"]
    assert schema["additionalProperties"] is False
    inner = schema["$defs"]["Inner"]
    assert inner["required"] == ["quote", "turn"]
    assert inner["additionalProperties"] is False
    assert "default" not in inner["properties"]["turn"]  # a None default carries nothing
    # A mapping has no strict form; it is kept for the provider to reject.
    assert schema["properties"]["mapping"]["additionalProperties"] == {"type": "integer"}
    assert "additionalProperties" not in Outer.model_json_schema()  # the input is unchanged
