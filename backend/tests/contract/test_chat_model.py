"""The same contract for every ChatModel adapter.

Live adapters need `-m live`: Ollama, and for ChatGPT a sign-in stored in the data directory
(calls count against the ChatGPT plan).
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from probeloop.ai.chatgpt import ChatGptChatModel, TokenSource
from probeloop.ai.chatgpt_auth import ChatGptAuth
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


def scripted_responses(request: httpx.Request) -> httpx.Response:
    """A Responses API stream as the provider sends it, for the offline contract run."""
    events = [
        {"type": "response.output_text.delta", "delta": '{"answer": '},
        {"type": "response.output_text.delta", "delta": '"ok", "n": 3}'},
        {
            "type": "response.completed",
            "response": {"status": "completed", "usage": {"input_tokens": 30, "output_tokens": 9}},
        },
    ]
    body = "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events)
    return httpx.Response(200, content=body.encode())


async def offline_token(*, refresh: bool = False) -> str:
    return "offline"


def chatgpt_model(
    token: TokenSource = offline_token, transport: httpx.AsyncBaseTransport | None = None
) -> ChatGptChatModel:
    return ChatGptChatModel(
        model=os.environ.get("PROBELOOP_CLOUD_INTERVIEWER_MODEL", "gpt-6.1-terra"),
        token=token,
        transport=transport,
    )


@pytest.fixture(
    params=[
        pytest.param("fake", id="fake"),
        pytest.param("chatgpt-offline", id="chatgpt-offline"),
        pytest.param("ollama", id="ollama", marks=pytest.mark.live),
        pytest.param("chatgpt", id="chatgpt", marks=pytest.mark.live),
    ]
)
async def model(request: pytest.FixtureRequest) -> AsyncIterator[ChatModel]:
    if request.param == "fake":
        yield FakeChatModel(['{"answer": "ok", "n": 3}'])
    elif request.param == "chatgpt-offline":
        yield chatgpt_model(transport=httpx.MockTransport(scripted_responses))
    elif request.param == "chatgpt":
        # Uses the sign-in stored by the application in its data directory.
        account = ChatGptAuth(Path(os.environ.get("PROBELOOP_DATA_DIR", "/data")) / "chatgpt")
        if not account.status().plan_usage:
            pytest.skip("not signed in with ChatGPT plan usage")
        yield chatgpt_model(account.access_token)
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
