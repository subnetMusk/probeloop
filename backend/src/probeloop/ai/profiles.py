"""Route each model call to the execution profile selected when the call starts (ADR 0015).

The profile comes from the innermost `using_profile` scope, or else from the default selection.
Requests and jobs open a scope with the profile of their preparation or interview; the
interviewer of a session is pinned to its profile instead.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar

from probeloop.ai.ports import ChatChunk, ChatModel, ChatRequest, ChatResult, ModelCapabilities
from probeloop.workspace.execution import tool_for

_scope: ContextVar[str | None] = ContextVar("execution_profile", default=None)


@contextmanager
def using_profile(profile: str | None) -> Iterator[None]:
    """Model calls made inside use `profile`; None keeps the enclosing choice."""
    token = _scope.set(profile or _scope.get())
    try:
        yield
    finally:
        _scope.reset(token)


class ProfiledChatModel:
    """One role (interviewer, analysis or evaluation) with a model per execution profile.

    `current` names the selected profile; it must be a key of `models`.
    """

    def __init__(
        self,
        models: Mapping[str, ChatModel],
        current: Callable[[], str],
        *,
        role: str = "interviewer",
    ) -> None:
        self._models = dict(models)
        self._current = current
        self._role = role

    @property
    def model_ref(self) -> str:
        return self._model().model_ref

    def model_refs(self) -> dict[str, str]:
        return {name: model.model_ref for name, model in self._models.items()}

    def pinned(self, profile: str) -> ChatModel:
        """The model of `profile`, regardless of later changes to the selection."""
        return self._models[tool_for(profile, self._role)]

    async def capabilities(self) -> ModelCapabilities:
        return await self._model().capabilities()

    async def complete(self, request: ChatRequest) -> ChatResult:
        return await self._model().complete(request)

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        async for chunk in self._model().stream(request):
            yield chunk

    def _model(self) -> ChatModel:
        return self.pinned(_scope.get() or self._current())
