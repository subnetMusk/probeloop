"""Route each model call to the execution profile selected when the call starts."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping

from probeloop.ai.ports import ChatChunk, ChatModel, ChatRequest, ChatResult, ModelCapabilities


class ProfiledChatModel:
    """One role (interviewer, analysis or evaluation) with a model per execution profile.

    `current` names the selected profile; it must be a key of `models`.
    """

    def __init__(self, models: Mapping[str, ChatModel], current: Callable[[], str]) -> None:
        self._models = dict(models)
        self._current = current

    @property
    def model_ref(self) -> str:
        return self._model().model_ref

    def model_refs(self) -> dict[str, str]:
        return {name: model.model_ref for name, model in self._models.items()}

    async def capabilities(self) -> ModelCapabilities:
        return await self._model().capabilities()

    async def complete(self, request: ChatRequest) -> ChatResult:
        return await self._model().complete(request)

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        async for chunk in self._model().stream(request):
            yield chunk

    def _model(self) -> ChatModel:
        return self._models[self._current()]
