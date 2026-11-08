"""Scripted ChatModel for tests and offline development."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from dataclasses import dataclass, field

from probeloop.ai.chatgpt_auth import SIGN_IN_AGAIN, AccountStatus
from probeloop.ai.ports import (
    ChatChunk,
    ChatRequest,
    ChatResult,
    ChatUsage,
    ModelCapabilities,
    UserActionRequiredError,
)

type Script = str | Exception | Callable[[ChatRequest], str]


@dataclass
class FakeChatModel:
    """Replays scripted responses in order and records every request.

    A script item is a response text, an exception to raise, or a function of the request. Once
    the script is exhausted, the last item is repeated.
    """

    script: Sequence[Script]
    chunk_size: int = 8
    chunk_delay_s: float = 0.0
    requests: list[ChatRequest] = field(default_factory=list)

    @property
    def model_ref(self) -> str:
        return "fake:scripted"

    async def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(context_window=8192, structured_output="json_schema")

    async def complete(self, request: ChatRequest) -> ChatResult:
        text = "".join([c.text async for c in self.stream(request)])
        return ChatResult(text=text, usage=ChatUsage(prompt_tokens=0, output_tokens=len(text)))

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        item = self.script[min(len(self.requests), len(self.script) - 1)]
        self.requests.append(request)
        if isinstance(item, Exception):
            raise item
        text = item(request) if callable(item) else item
        for start in range(0, len(text), self.chunk_size):
            if self.chunk_delay_s:
                await asyncio.sleep(self.chunk_delay_s)
            yield ChatChunk(text=text[start : start + self.chunk_size])
        yield ChatChunk(
            text="", done=True, usage=ChatUsage(prompt_tokens=0, output_tokens=len(text))
        )


@dataclass
class FakeChatGptAccount:
    """A ChatGPT account for end-to-end tests: signing in returns straight to the callback."""

    signed_in: bool = True

    def status(self) -> AccountStatus:
        email = "synthetic@example.test" if self.signed_in else None
        return AccountStatus(self.signed_in, email, self.signed_in)

    def begin(self, redirect_uri: str) -> str:
        return f"{redirect_uri}?code=synthetic&state=synthetic"

    async def complete(self, query: Mapping[str, str]) -> AccountStatus:
        self.signed_in = True
        return self.status()

    async def access_token(self, *, refresh: bool = False) -> str:
        if not self.signed_in:
            raise UserActionRequiredError(SIGN_IN_AGAIN)
        return "synthetic-token"

    async def sign_out(self) -> None:
        self.signed_in = False
