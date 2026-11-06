from __future__ import annotations

import pytest
from pydantic import BaseModel

from probeloop.ai.fake import FakeChatModel
from probeloop.ai.ports import ChatMessage, ChatRequest
from probeloop.ai.structured import (
    FieldDelta,
    StructuredOutputError,
    StructuredResult,
    partial_field,
    stream_structured,
)


class Out(BaseModel):
    kind: str
    text: str
    tags: list[str]


REQUEST = ChatRequest(instructions="x", messages=(ChatMessage("user", "y"),))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", ""),
        ('{"kind": "a", "te', ""),
        ('{"kind": "a", "text": "Buongio', "Buongio"),
        ('{"kind": "a", "text": "Buongiorno, \\"Marco\\"", "tags": [', 'Buongiorno, "Marco"'),
        ("not json", ""),
    ],
)
def test_partial_field(raw: str, expected: str) -> None:
    assert partial_field(raw, "text") == expected


async def test_streams_field_deltas_then_validated_result() -> None:
    model = FakeChatModel(
        ['{"kind": "q", "text": "Mi racconta il progetto?", "tags": ["a"]}'], chunk_size=5
    )
    items = [i async for i in stream_structured(model, REQUEST, Out, stream_field="text")]
    deltas = [i for i in items if isinstance(i, FieldDelta)]
    result = items[-1]
    assert isinstance(result, StructuredResult)
    assert "".join(d.text for d in deltas) == "Mi racconta il progetto?"
    assert result.value == Out(kind="q", text="Mi racconta il progetto?", tags=["a"])
    assert deltas[-1].partial["kind"] == "q"
    assert model.requests[0].response_schema == Out.model_json_schema()


async def test_invalid_output_raises() -> None:
    model = FakeChatModel(['{"kind": "q", "text": "ok"}'])
    with pytest.raises(StructuredOutputError):
        _ = [i async for i in stream_structured(model, REQUEST, Out, stream_field="text")]
