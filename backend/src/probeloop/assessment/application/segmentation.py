"""Group recorded follow-up moves before asking a model only for question classification."""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

from pydantic import Field

from probeloop.assessment.application.schemas import Strict
from probeloop.assessment.domain.model import AnswerUnit
from probeloop.interview.domain.model import (
    CandidateTurn,
    InterviewerTurn,
    InterviewSession,
    MoveAction,
)


class KindOut(Strict):
    unit_id: str
    # Whether a question asks what the candidate actually did. Decided from the questions alone,
    # because judges were observed to score a plan as missing experience. It precedes `kind`:
    # constrained decoding follows this order, and deciding the kind first made the model answer
    # false for technical questions that also ask for a personal example
    # (docs/research/interview-calibration.md).
    past_example: bool
    kind: Literal["hr", "behavioral", "technical", "hypothetical", "logistics"]


class KindsOut(Strict):
    units: list[KindOut] = Field(max_length=100)


def answer_units(session: InterviewSession) -> tuple[AnswerUnit, ...]:
    units: list[AnswerUnit] = []
    for turn in session.turns:
        if isinstance(turn, InterviewerTurn):
            if turn.move.action in (MoveAction.WRAP_UP, MoveAction.END):
                # Candidate questions and closing are preserved but never scored as answers.
                units.append(
                    AnswerUnit(f"u{turn.seq}", turn.move.topic_id, "logistics", (turn.seq,), ())
                )
            elif units and turn.move.action in (MoveAction.FOLLOW_UP, MoveAction.CLARIFY):
                units[-1] = replace(units[-1], question_seqs=(*units[-1].question_seqs, turn.seq))
            else:
                units.append(
                    AnswerUnit(f"u{turn.seq}", turn.move.topic_id, "unclassified", (turn.seq,), ())
                )
        elif isinstance(turn, CandidateTurn) and units:
            units[-1] = replace(units[-1], answer_seqs=(*units[-1].answer_seqs, turn.seq))
    return tuple(u for u in units if u.answer_seqs)


def past_examples(units: tuple[AnswerUnit, ...], output: KindsOut) -> dict[str, bool]:
    """Units whose questions ask for a past example; ambiguous answers default to asking."""
    counts = {u.id: sum(item.unit_id == u.id for item in output.units) for u in units}
    flags = {item.unit_id: item.past_example for item in output.units}
    return {u.id: flags[u.id] if counts[u.id] == 1 else True for u in units}


def classified(units: tuple[AnswerUnit, ...], output: KindsOut) -> tuple[AnswerUnit, ...]:
    counts = {u.id: sum(item.unit_id == u.id for item in output.units) for u in units}
    by_id = {item.unit_id: item.kind for item in output.units}
    return tuple(
        replace(unit, kind=by_id[unit.id])
        if unit.kind != "logistics" and counts[unit.id] == 1
        else unit
        for unit in units
    )
