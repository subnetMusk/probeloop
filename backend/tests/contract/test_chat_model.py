"""The same contract for every ChatModel adapter. Live adapters need `-m live` and Ollama."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator

import pytest

from probeloop.ai.fake import FakeChatModel
from probeloop.ai.ollama import OllamaChatModel
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


@pytest.fixture(
    params=[
        pytest.param("fake", id="fake"),
        pytest.param("ollama", id="ollama", marks=pytest.mark.live),
    ]
)
async def model(request: pytest.FixtureRequest) -> AsyncIterator[ChatModel]:
    if request.param == "fake":
        yield FakeChatModel(['{"answer": "ok", "n": 3}'])
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
