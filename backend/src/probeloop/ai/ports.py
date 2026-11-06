"""The ChatModel port. Adapters live next to it; only the composition root picks one."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Role = Literal["user", "assistant"]


class LlmError(Exception):
    """A provider call failed. The message is safe to log: it never contains prompt text."""


class ContextOverflowError(LlmError):
    """The prompt does not fit in the configured context window."""


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Role
    content: str


@dataclass(frozen=True, slots=True)
class ChatRequest:
    """A provider-neutral request.

    `instructions` is kept apart from `messages` because providers differ in how (and whether)
    they accept system-role messages.
    """

    instructions: str
    messages: tuple[ChatMessage, ...]
    response_schema: dict[str, Any] | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_output_tokens: int | None = None
    reasoning: Literal["off", "default"] = "off"


@dataclass(frozen=True, slots=True)
class ChatUsage:
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    load_s: float | None = None
    prompt_s: float | None = None
    output_s: float | None = None


@dataclass(frozen=True, slots=True)
class ChatChunk:
    """A streamed piece of output. The final chunk has `done=True` and carries usage."""

    text: str
    done: bool = False
    usage: ChatUsage | None = None


@dataclass(frozen=True, slots=True)
class ChatResult:
    text: str
    usage: ChatUsage = field(default_factory=ChatUsage)


@dataclass(frozen=True, slots=True)
class ModelCapabilities:
    context_window: int
    streaming: bool = True
    structured_output: Literal["json_schema", "json_object", "none"] = "none"
    tool_calling: bool = False
    reasoning: bool = False
    vision: bool = False
    sampling_params: bool = True
    system_role: bool = True


class ChatModel(Protocol):
    @property
    def model_ref(self) -> str:
        """Provider, model and relevant options, for provenance records."""
        ...

    async def capabilities(self) -> ModelCapabilities: ...

    async def complete(self, request: ChatRequest) -> ChatResult: ...

    def stream(self, request: ChatRequest) -> AsyncIterator[ChatChunk]: ...
