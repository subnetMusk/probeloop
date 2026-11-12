"""Line classification with TypeSafe Jev, an optional cloud service, for the CV check.

The lines of one document form the state of a request, and one Noul question per line asks the
wording's question; obligation asks two, one for a requirement and one for a preference. Long
documents are split into several requests. The model, the wordings and the thresholds are fixed
and recorded with every reading.

The wordings are not evaluated yet. `EVALUATED` stays False until `evals/jev_classification.py`
meets the acceptance targets on the frozen reference labels; until then the application must not
offer this classifier. Changing a wording requires a new identifier and a new evaluation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from probeloop.context.application.ports import (
    Classified,
    LineReading,
    ObligationReading,
    OfferLine,
    TextClassifierUnavailable,
)
from probeloop.context.domain.model import Obligation
from probeloop.platform.jev import (
    API_URL,
    Failure,
    JevClient,
    JevError,
    JevKeyFile,
    noul_scores,
    served_model,
)

logger = logging.getLogger(__name__)

MODEL = "jev-1.14.0"
EVALUATED = False
TIMEOUT_S = 15.0  # a whole document, not a live interview turn
MAX_QUESTIONS = 40  # per request; the service-side limit is not documented

_MESSAGES: dict[Failure, str] = {
    "key_missing": "add a Jev API key in Settings",
    "key_rejected": "the Jev API key was rejected; check it in Settings",
    "unreachable": "Jev is unreachable; check the connection and try again",
    "failed": "Jev could not classify the document; try again",
}


@dataclass(frozen=True, slots=True)
class Wording:
    id: str
    instructions: str  # formatted with the line's index in its request
    criteria: dict[str, str]
    threshold: float


REQUIRED = Wording(
    "cv.obligation.v1.must",
    "Read `offer_lines[{index}].text` under its section heading "
    "`offer_lines[{index}].heading`. Does it state something the employer requires of the "
    "candidate?",
    {
        "true": "The line states a qualification, skill, experience, credential, language or "
        "condition the candidate must have, through its own wording (required, essential, at "
        "least, indispensabile) or through a heading such as Requirements or Requisiti.",
        "false": "Anything else, including preferences and pluses, responsibilities of the "
        "role, benefits, descriptions of the company and details of the selection process.",
    },
    0.5,
)
PREFERRED = Wording(
    "cv.obligation.v1.preferred",
    "Read `offer_lines[{index}].text` under its section heading "
    "`offer_lines[{index}].heading`. Does it state something the employer would like the "
    "candidate to have without requiring it?",
    {
        "true": "The line states a preference or a plus, through its own wording (preferably, "
        "ideally, a plus, preferibilmente, gradito) or through a heading such as Nice to have or "
        "Gradito.",
        "false": "Anything else, including requirements, responsibilities of the role, "
        "benefits, descriptions of the company and details of the selection process.",
    },
    0.5,
)
QUANTIFIED = Wording(
    "cv.quantified.v1",
    "Does `cv_lines[{index}]` state a measured outcome or scope of the candidate's work?",
    {
        "true": "The line gives a number or a quantity, in digits or in words, for a result, a "
        "change, a volume, a team size, users, money or time of the candidate's work.",
        "false": "Anything else, including dates, periods of employment, phone numbers, "
        "identifiers, grades, language levels and version numbers.",
    },
    0.5,
)
HEADING = Wording(
    "cv.heading.v1",
    "Is `cv_lines[{index}]` a section heading of the CV?",
    {
        "true": "The line names a section of the document, such as experience, education, "
        "skills, projects or languages, in any wording, letter case or spacing.",
        "false": "Anything else, including names, job titles, employers, dates and lines of "
        "content.",
    },
    0.5,
)


def obligation_of(must: float, preferred: float) -> Obligation:
    """A line is a requirement or a preference only when one reading alone passes its threshold.

    A line that passes both, such as a requirement with a preferred option, or neither, is left
    unclear for the analysis to settle.
    """
    required = must >= REQUIRED.threshold
    optional = preferred >= PREFERRED.threshold
    if required != optional:
        return Obligation.MUST if required else Obligation.PREFERRED
    return Obligation.UNCLEAR


def request_body(state_key: str, items: list[Any], wordings: Sequence[Wording]) -> dict[str, Any]:
    return {
        "model": MODEL,
        "state": {state_key: items},
        "questions": {
            f"q{w}_{i}": {
                "type": "noul",
                "instructions": wording.instructions.format(index=i),
                "criteria": wording.criteria,
            }
            for w, wording in enumerate(wordings)
            for i in range(len(items))
        },
    }


class JevTextClassifier:
    def __init__(
        self,
        key: JevKeyFile,
        *,
        base_url: str = API_URL,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        max_questions: int = MAX_QUESTIONS,
    ) -> None:
        self.key = key
        self._max_questions = max_questions
        self._client = JevClient(
            key, base_url=base_url, timeout_s=TIMEOUT_S, transport=transport, sleep=sleep
        )

    async def obligations(self, lines: Sequence[OfferLine]) -> Classified[ObligationReading]:
        items = [{"heading": line.heading, "text": line.text} for line in lines]
        scores, model = await self._ask("obligation", "offer_lines", items, (REQUIRED, PREFERRED))
        readings = tuple(
            ObligationReading(obligation_of(must, preferred), must, preferred)
            for must, preferred in scores
        )
        thresholds = f"must={REQUIRED.threshold}:preferred={PREFERRED.threshold}"
        return Classified(readings, f"typesafe:{model}:cv.obligation.v1:{thresholds}")

    async def quantified(self, lines: Sequence[str]) -> Classified[LineReading]:
        return await self._lines("quantified", lines, QUANTIFIED)

    async def headings(self, lines: Sequence[str]) -> Classified[LineReading]:
        return await self._lines("headings", lines, HEADING)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _lines(
        self, task: str, lines: Sequence[str], wording: Wording
    ) -> Classified[LineReading]:
        scores, model = await self._ask(task, "cv_lines", list(lines), (wording,))
        readings = tuple(LineReading(score >= wording.threshold, score) for (score,) in scores)
        return Classified(readings, f"typesafe:{model}:{wording.id}:threshold={wording.threshold}")

    async def _ask(
        self, task: str, state_key: str, items: list[Any], wordings: Sequence[Wording]
    ) -> tuple[list[tuple[float, ...]], str]:
        """The scores of every item for every wording, in order, and the model that answered."""
        per_request = max(1, self._max_questions // len(wordings))
        scores: list[tuple[float, ...]] = []
        model = MODEL
        started = time.perf_counter()
        for start in range(0, len(items), per_request):
            batch = items[start : start + per_request]
            ids = [[f"q{w}_{i}" for w in range(len(wordings))] for i in range(len(batch))]
            try:
                payload = await self._client.systemone(request_body(state_key, batch, wordings))
                answered = noul_scores(payload, [q for item in ids for q in item])
            except JevError as exc:
                raise TextClassifierUnavailable(_MESSAGES[exc.failure]) from None
            scores += [tuple(answered[q] for q in item) for item in ids]
            model = served_model(payload, MODEL)
        if items:
            logger.info(
                "document classification completed",
                extra={
                    "engine": "jev",
                    "task": task,
                    "model": model,
                    "lines": len(items),
                    "duration_ms": round(1000 * (time.perf_counter() - started), 1),
                },
            )
        return scores, model
