"""Structured output: schema-constrained generation validated with Pydantic.

`stream_structured` streams a JSON object and reports the growing value of one string field as
it is generated, so that callers (for example text-to-speech) can act before the object is
complete.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from pydantic import BaseModel, ValidationError
from pydantic_core import from_json

from probeloop.ai.ports import ChatMessage, ChatModel, ChatRequest, ChatUsage, LlmError


class StructuredOutputError(LlmError):
    """The model output did not validate against the expected schema."""


@dataclass(frozen=True, slots=True)
class FieldDelta:
    """New characters of the streamed field, plus the partially parsed object so far."""

    text: str
    partial: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StructuredResult[T: BaseModel]:
    value: T
    raw: str
    usage: ChatUsage
    # Usage of every provider call, including failed attempts before a repair.
    attempts: tuple[ChatUsage, ...] = ()


def partial_object(raw: str) -> dict[str, Any]:
    """Parse a possibly incomplete JSON object; trailing strings are kept as far as they go."""
    try:
        partial = from_json(raw, allow_partial="trailing-strings")
    except ValueError:
        return {}
    return partial if isinstance(partial, dict) else {}


def partial_field(raw: str, name: str) -> str:
    """Current value of a string field in a possibly incomplete JSON object."""
    value = partial_object(raw).get(name)
    return value if isinstance(value, str) else ""


async def stream_structured[T: BaseModel](
    model: ChatModel,
    request: ChatRequest,
    output: type[T],
    *,
    stream_field: str,
) -> AsyncGenerator[FieldDelta | StructuredResult[T]]:
    """Yield `FieldDelta`s for `stream_field`, then one final `StructuredResult`.

    The field should come early in the schema's property order. Constrained decoding in Ollama
    follows that order.
    """
    constrained = replace(request, response_schema=output.model_json_schema())
    raw = ""
    emitted = 0
    usage = ChatUsage()
    async for chunk in model.stream(constrained):
        raw += chunk.text
        if chunk.done and chunk.usage is not None:
            usage = chunk.usage
        partial = partial_object(raw)
        current = partial.get(stream_field)
        if isinstance(current, str) and len(current) > emitted:
            yield FieldDelta(current[emitted:], partial)
            emitted = len(current)
    try:
        value = output.model_validate_json(raw)
    except ValidationError as exc:
        raise StructuredOutputError(
            f"{model.model_ref} returned invalid {output.__name__}: {exc.error_count()} errors"
        ) from exc
    yield StructuredResult(value=value, raw=raw, usage=usage, attempts=(usage,))


async def complete_structured[T: BaseModel](
    model: ChatModel,
    request: ChatRequest,
    output: type[T],
    *,
    attempts: int = 2,
) -> StructuredResult[T]:
    """Generate a JSON object constrained to `output`'s schema and validate it.

    When validation fails, the errors are sent back to the model for one repair attempt (ADR
    0011): constrained decoding guarantees the shape, not the lengths and limits.
    """
    constrained = replace(request, response_schema=output.model_json_schema())
    last_error: ValidationError | None = None
    messages = constrained.messages
    usages: list[ChatUsage] = []
    for _ in range(max(1, attempts)):
        result = await model.complete(replace(constrained, messages=messages))
        usages.append(result.usage)
        try:
            value = output.model_validate_json(result.text)
        except ValidationError as exc:
            last_error = exc
            problems = "; ".join(
                f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:10]
            )
            messages = (
                *constrained.messages,
                ChatMessage(role="assistant", content=result.text),
                ChatMessage(
                    role="user",
                    content=f"The JSON is not valid: {problems}. Return the corrected JSON only.",
                ),
            )
            continue
        return StructuredResult(
            value=value, raw=result.text, usage=result.usage, attempts=tuple(usages)
        )
    assert last_error is not None
    raise StructuredOutputError(
        f"{model.model_ref} returned invalid {output.__name__}: {last_error.error_count()} errors"
    ) from last_error
