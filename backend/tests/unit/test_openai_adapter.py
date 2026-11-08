"""The Chat Completions adapter against a scripted HTTP transport; no provider is contacted."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from probeloop.ai.openai import OpenAIChatModel, strict_schema
from probeloop.ai.ports import ChatMessage, ChatRequest, ContextOverflowError, LlmError

KEY = "sk-test-not-a-real-key"
PROMPT = "Synthetic answer about database indexes."
REQUEST = ChatRequest(
    instructions="Reply in JSON.",
    messages=(ChatMessage("user", PROMPT),),
    response_schema={
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
    },
    temperature=0.1,
    presence_penalty=0.0,
    max_output_tokens=200,
)


def sse(*events: object) -> bytes:
    lines = [f"data: {json.dumps(event)}\n\n" for event in events]
    return ("".join(lines) + "data: [DONE]\n\n").encode()


def completion(text: str, finish: str = "stop") -> bytes:
    half = len(text) // 2
    return sse(
        {"choices": [{"index": 0, "delta": {"role": "assistant", "content": text[:half]}}]},
        {"choices": [{"index": 0, "delta": {"content": text[half:]}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": finish}]},
        {"choices": [], "usage": {"prompt_tokens": 21, "completion_tokens": 7}},
    )


class Recorder:
    def __init__(self, *responses: httpx.Response) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []
        self.waits: list[float] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]

    def body(self, index: int = -1) -> Any:
        return json.loads(self.requests[index].content)

    async def sleep(self, seconds: float) -> None:
        self.waits.append(seconds)


def model(recorder: Recorder, **options: object) -> OpenAIChatModel:
    return OpenAIChatModel(
        model="gpt-test",
        api_key=KEY,
        transport=httpx.MockTransport(recorder),
        sleep=recorder.sleep,
        **options,  # type: ignore[arg-type]
    )


def ok(text: str = '{"answer": "ok"}') -> httpx.Response:
    return httpx.Response(200, content=completion(text))


def failure(status: int, code: str | None = None, param: str | None = None) -> httpx.Response:
    error = {"message": "Synthetic provider error.", "type": "invalid_request_error"}
    return httpx.Response(status, json={"error": error | {"code": code, "param": param}})


async def test_a_streamed_completion_ends_with_usage_and_the_stop_reason() -> None:
    recorder = Recorder(ok())
    chunks = [c async for c in model(recorder).stream(REQUEST)]
    assert "".join(c.text for c in chunks) == '{"answer": "ok"}'
    assert chunks[-1].done
    assert chunks[-1].usage is not None
    assert (chunks[-1].usage.prompt_tokens, chunks[-1].usage.output_tokens) == (21, 7)
    assert chunks[-1].usage.stop_reason == "stop"
    assert recorder.requests[0].url == "https://api.openai.com/v1/chat/completions"
    assert recorder.requests[0].headers["authorization"] == f"Bearer {KEY}"


async def test_reasoning_off_sends_none_and_the_sampling_parameters() -> None:
    recorder = Recorder(ok())
    await model(recorder).complete(REQUEST)
    body = recorder.body()
    assert body["reasoning_effort"] == "none"
    assert body["temperature"] == 0.1
    assert body["max_completion_tokens"] == 200
    assert "presence_penalty" not in body  # 0 is the provider default
    assert body["stream_options"] == {"include_usage": True}
    assert body["messages"] == [
        {"role": "system", "content": "Reply in JSON."},
        {"role": "user", "content": PROMPT},
    ]
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["response_format"]["json_schema"]["schema"]["additionalProperties"] is False


@pytest.mark.parametrize(
    ("reasoning_off", "reasoning", "effort", "sampling"),
    [
        ("low", "off", "low", False),  # models without "none" still generate reasoning tokens
        ("none", "default", None, False),  # the provider's default effort
        (None, "default", None, True),  # a model without reasoning control
    ],
)
async def test_sampling_parameters_are_sent_only_without_reasoning_tokens(
    reasoning_off: str | None, reasoning: str, effort: str | None, sampling: bool
) -> None:
    recorder = Recorder(ok())
    request = ChatRequest(
        instructions="x",
        messages=(ChatMessage("user", "y"),),
        temperature=0.1,
        presence_penalty=1.5,
        max_output_tokens=50,
        reasoning=reasoning,  # type: ignore[arg-type]
    )
    await model(recorder, reasoning_off=reasoning_off).complete(request)
    body = recorder.body()
    assert body.get("reasoning_effort") == effort
    for name in ("temperature", "presence_penalty", "max_completion_tokens"):
        assert (name in body) is sampling


async def test_rate_limits_and_server_errors_are_retried_with_backoff() -> None:
    limited = httpx.Response(429, headers={"retry-after": "3"}, json={"error": {}})
    recorder = Recorder(limited, failure(503), ok())
    result = await model(recorder).complete(REQUEST)
    assert result.text == '{"answer": "ok"}'
    assert recorder.waits == [3.0, 4.0]


async def test_a_rejected_strict_schema_falls_back_to_best_effort_once() -> None:
    recorder = Recorder(failure(400, "invalid_json_schema", "response_format"), ok(), ok())
    chat = model(recorder)
    await chat.complete(REQUEST)
    await chat.complete(REQUEST)
    bodies: list[Any] = [json.loads(request.content) for request in recorder.requests]
    assert [b["response_format"]["json_schema"]["strict"] for b in bodies] == [True, False, False]


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (lambda: failure(401, "invalid_api_key"), LlmError),
        (lambda: failure(400, "context_length_exceeded", "messages"), ContextOverflowError),
        (lambda: failure(400, "unsupported_parameter", "temperature"), LlmError),
    ],
)
async def test_errors_name_the_problem_but_never_the_prompt_or_the_key(
    response: Callable[[], httpx.Response], error: type[LlmError]
) -> None:
    with pytest.raises(error) as raised:
        await model(Recorder(response())).complete(REQUEST)
    message = str(raised.value)
    assert "Synthetic provider error." in message
    assert PROMPT not in message
    assert KEY not in message


async def test_a_refusal_is_an_error() -> None:
    refusal = sse({"choices": [{"index": 0, "delta": {"refusal": "No."}, "finish_reason": "stop"}]})
    with pytest.raises(LlmError, match="refused"):
        await model(Recorder(httpx.Response(200, content=refusal))).complete(REQUEST)


async def test_unreachable_providers_fail_after_the_retries() -> None:
    recorder = Recorder(ok())

    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic", request=request)

    chat = OpenAIChatModel(
        model="gpt-test",
        api_key=KEY,
        transport=httpx.MockTransport(unreachable),
        sleep=recorder.sleep,
    )
    with pytest.raises(LlmError, match="unreachable"):
        await chat.complete(REQUEST)
    assert recorder.waits == [2.0, 4.0]


async def test_prompts_that_cannot_fit_are_rejected_before_the_call() -> None:
    recorder = Recorder(ok())
    huge = ChatRequest(instructions="x", messages=(ChatMessage("user", "word " * 3000),))
    with pytest.raises(ContextOverflowError):
        await model(recorder, context_window=1024).complete(huge)
    assert recorder.requests == []


async def test_model_references_name_the_provider() -> None:
    assert model(Recorder(ok())).model_ref == "openai:gpt-test"
    other = model(Recorder(ok()), base_url="http://127.0.0.1:8080/v1")
    assert other.model_ref == "openai-compatible:gpt-test"


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
    assert schema["properties"]["items"]["default"] == []
    # A mapping has no strict form; it is kept for the provider to reject.
    assert schema["properties"]["mapping"]["additionalProperties"] == {"type": "integer"}
    assert "additionalProperties" not in Outer.model_json_schema()  # the input is unchanged
