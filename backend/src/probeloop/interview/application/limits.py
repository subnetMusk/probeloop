"""Read stated limits through a port and retain only quotations grounded in the answer."""

from __future__ import annotations

import json
import re

from probeloop.ai.ports import ChatMessage, ChatModel, ChatRequest
from probeloop.ai.prompts import PromptRenderer
from probeloop.ai.structured import StructuredOutputError, complete_structured
from probeloop.interview.application.adaptive_interviewer import StatedLimits
from probeloop.interview.application.ports import (
    LimitReading,
)


def answer_sentences(answer: str) -> list[str]:
    """The sentence units that classifiers score: the segmentation of the training labels."""
    return [s.strip() for s in re.split(r"(?<=[.!?;])\s+", answer) if len(s.strip()) > 3]


def grounded_quotes(answer: str, quotes: tuple[str, ...]) -> tuple[str, ...]:
    text = " ".join(answer.split()).casefold()
    return tuple(
        quote
        for quote in dict.fromkeys(" ".join(q.split()) for q in quotes)
        if quote and " ".join(quote.split()).casefold() in text
    )


class LlmStatedLimitReader:
    def __init__(self, model: ChatModel) -> None:
        self._model = model
        self._prompt = PromptRenderer("probeloop.interview").render("interviewer_limits", 1)

    async def check(self) -> None:
        await self._model.capabilities()

    async def read(self, question: str, answer: str) -> LimitReading:
        if not answer.strip():
            return LimitReading((), self._prompt.ref)
        request = ChatRequest(
            instructions=self._prompt.text,
            messages=(ChatMessage("user", json.dumps({"question": question, "answer": answer})),),
            temperature=0.0,
            max_output_tokens=400,
        )
        try:
            result = await complete_structured(self._model, request, StatedLimits, attempts=1)
            quotes = grounded_quotes(answer, tuple(result.value.quotes))
        except StructuredOutputError:
            quotes = ()
        return LimitReading(quotes, f"{self._prompt.ref}:{self._model.model_ref}")
