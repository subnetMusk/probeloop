"""The SDK's translated connection error stays inside the provider boundary."""

import httpx
import ollama
import pytest

from probeloop.ai.ollama import OllamaChatModel
from probeloop.ai.ports import ChatMessage, ChatRequest, LlmError


async def test_missing_ollama_is_unavailable_and_exposes_provider_errors() -> None:
    def disconnected(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic unavailable service", request=request)

    client = ollama.AsyncClient(host="http://ollama", transport=httpx.MockTransport(disconnected))
    adapter = OllamaChatModel(
        model="synthetic-model", base_url="http://ollama", context_window=8192, client=client
    )
    assert not await adapter.available()
    with pytest.raises(LlmError, match="cannot describe"):
        await adapter.capabilities()
    with pytest.raises(LlmError, match="cannot load"):
        await adapter.preload()
    await client._client.aclose()


async def test_ollama_disconnect_after_readiness_is_a_provider_failure() -> None:
    def reply(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"capabilities": ["completion"], "model_info": {}})
        raise httpx.ConnectError("synthetic disconnected provider", request=request)

    client = ollama.AsyncClient(host="http://ollama", transport=httpx.MockTransport(reply))
    adapter = OllamaChatModel(
        model="synthetic-model", base_url="http://ollama", context_window=8192, client=client
    )
    assert await adapter.available()
    with pytest.raises(LlmError, match="request failed"):
        await adapter.complete(ChatRequest("", (ChatMessage("user", "Synthetic answer"),)))
    await client._client.aclose()
