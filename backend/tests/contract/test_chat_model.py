"""The same contract for every ChatModel adapter.

Live adapters need `-m live`: Ollama, and for OpenAI `PROBELOOP_CLOUD_API_KEY` (billed).
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator

import httpx
import pytest

from probeloop.ai.fake import FakeChatModel
from probeloop.ai.ollama import OllamaChatModel
from probeloop.ai.openai import OpenAIChatModel
from probeloop.ai.ports import ChatMessage, ChatModel, ChatRequest, ContextOverflowError

SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}, "n": {"type": "integer"}},
    "required": ["answer", "n"],
}
REQUEST = ChatRequest(
    instructions="Reply in JSON.",
    messages=(ChatMessage("user", 'Return {"answer": "ok", "n": 3}.'),),
    response_schema=SCHEMA,
    temperature=0.0,
    max_output_tokens=40,
)


def ollama_model() -> OllamaChatModel:
    return OllamaChatModel(
        base_url=os.environ.get("PROBELOOP_OLLAMA_BASE_URL", "http://host.docker.internal:11434"),
        model=os.environ.get("PROBELOOP_INTERVIEWER_MODEL", "ministral-3:8b"),
        context_window=8192,
    )


def scripted_openai(request: httpx.Request) -> httpx.Response:
    """A Chat Completions stream as the provider sends it, for the offline contract run."""
    events = [
        {"choices": [{"index": 0, "delta": {"content": '{"answer": '}}]},
        {"choices": [{"index": 0, "delta": {"content": '"ok", "n": 3}'}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
        {"choices": [], "usage": {"prompt_tokens": 30, "completion_tokens": 9}},
    ]
    body = "".join(f"data: {json.dumps(e)}\n\n" for e in events) + "data: [DONE]\n\n"
    return httpx.Response(200, content=body.encode())


def openai_model(transport: httpx.AsyncBaseTransport | None = None) -> OpenAIChatModel:
    return OpenAIChatModel(
        model=os.environ.get("PROBELOOP_CLOUD_INTERVIEWER_MODEL", "gpt-6.1-terra"),
        api_key=os.environ.get("PROBELOOP_CLOUD_API_KEY", "offline"),
        transport=transport,
    )


@pytest.fixture(
    params=[
        pytest.param("fake", id="fake"),
        pytest.param("openai-offline", id="openai-offline"),
        pytest.param("ollama", id="ollama", marks=pytest.mark.live),
        pytest.param("openai", id="openai", marks=pytest.mark.live),
    ]
)
async def model(request: pytest.FixtureRequest) -> AsyncIterator[ChatModel]:
    if request.param == "fake":
        yield FakeChatModel(['{"answer": "ok", "n": 3}'])
    elif request.param == "openai-offline":
        yield openai_model(httpx.MockTransport(scripted_openai))
    elif request.param == "openai":
        if "PROBELOOP_CLOUD_API_KEY" not in os.environ:
            pytest.skip("PROBELOOP_CLOUD_API_KEY is not set")
        yield openai_model()
    else:
        yield ollama_model()


async def test_capabilities(model: ChatModel) -> None:
    caps = await model.capabilities()
    assert caps.context_window > 0
    assert caps.structured_output == "json_schema"


async def test_stream_ends_with_usage_and_matches_complete(model: ChatModel) -> None:
    chunks = [c async for c in model.stream(REQUEST)]
    assert chunks[-1].done
    assert chunks[-1].usage is not None
    assert all(not c.done for c in chunks[:-1])
    text = "".join(c.text for c in chunks)
    assert json.loads(text) == {"answer": "ok", "n": 3}


async def test_model_ref_is_stable(model: ChatModel) -> None:
    assert model.model_ref == model.model_ref
    assert ":" in model.model_ref


@pytest.mark.live
async def test_ollama_rejects_prompts_that_cannot_fit() -> None:
    model = OllamaChatModel(
        base_url=os.environ.get("PROBELOOP_OLLAMA_BASE_URL", "http://host.docker.internal:11434"),
        model=os.environ.get("PROBELOOP_INTERVIEWER_MODEL", "ministral-3:8b"),
        context_window=1024,
    )
    huge = ChatRequest(instructions="x", messages=(ChatMessage("user", "parola " * 3000),))
    with pytest.raises(ContextOverflowError):
        _ = [c async for c in model.stream(huge)]
