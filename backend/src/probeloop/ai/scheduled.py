"""Model decorator for background analysis and planning, wired only in bootstrap."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager

from probeloop.ai.ports import ChatChunk, ChatModel, ChatRequest, ChatResult, ModelCapabilities


class ScheduledChatModel:
    def __init__(
        self, model: ChatModel, access: Callable[[], AbstractAsyncContextManager[None]]
    ) -> None:
        self._model = model
        self._access = access

    @property
    def model_ref(self) -> str:
        return self._model.model_ref

    async def capabilities(self) -> ModelCapabilities:
        return await self._model.capabilities()

    async def complete(self, request: ChatRequest) -> ChatResult:
        async with self._access():
            return await self._model.complete(request)

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        async with self._access():
            async for chunk in self._model.stream(request):
                yield chunk
