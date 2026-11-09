"""Route new-policy units from recorded question intent, retaining classifier diagnostics."""

from dataclasses import replace

from probeloop.assessment.domain.model import AnswerUnit, Check, Score
from probeloop.interview.domain.model import (
    InterviewerTurn,
    InterviewSession,
    MoveAction,
    MovePurpose,
)


def recorded_units(
    session: InterviewSession,
    diagnostics: tuple[AnswerUnit, ...],
) -> tuple[tuple[AnswerUnit, ...], dict[str, bool], tuple[Check, ...]]:
    turns = {t.seq: t for t in session.turns if isinstance(t, InterviewerTurn)}
    units = []
    past: dict[str, bool] = {}
    checks = []
    topics = {t.id: t for t in session.context.topics}
    for unit in diagnostics:
        intents = [
            intent
            for n in unit.question_seqs
            if (intent := turns[n].move.intent) is not None
            and not turns[n].move.fallback
            and intent.purpose is not MovePurpose.CLARIFICATION
        ]
        known = [intent for intent in intents if intent is not None]
        kinds = {intent.rubric_kind or topics[unit.topic_id].rubric_kind for intent in known}
        kinds.discard(None)
        kind = next(iter(kinds)) if len(kinds) == 1 else "unclassified"
        if all(
            turns[n].move.action in (MoveAction.WRAP_UP, MoveAction.END) for n in unit.question_seqs
        ):
            kind = "logistics"
        units.append(replace(unit, kind=kind or "unclassified"))
        past[unit.id] = any(intent.past_example for intent in known)
        checks.append(
            Check(
                f"classification:{unit.id}",
                "consistent" if kind == unit.kind else "diagnostic_disagreement",
                f"Recorded intent: {kind}; diagnostic classifier: {unit.kind}.",
            )
        )
    return tuple(units), past, tuple(checks)


def elicited_scores(
    scores: tuple[Score, ...],
    session: InterviewSession,
    unit: AnswerUnit,
    language: str,
) -> tuple[Score, ...]:
    elicited = elicited_criteria(session, unit)
    reason = (
        "Criterio non richiesto dalle domande."
        if language == "it"
        else "Criterion not elicited by the questions."
    )
    return tuple(
        score
        if score.criterion_id in elicited
        else replace(score, value=None, evidence=(), reason=reason)
        for score in scores
    )


def elicited_criteria(session: InterviewSession, unit: AnswerUnit) -> set[str]:
    return {
        criterion
        for turn in session.interviewer_turns()
        if turn.seq in unit.question_seqs and turn.move.intent and not turn.move.fallback
        for criterion in turn.move.intent.elicited_criteria
    }
