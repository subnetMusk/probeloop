"""Evidence checks shared by CV and transcript assessment; document contents stay untrusted."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from probeloop.assessment.application.labels import label
from probeloop.assessment.application.rubrics import Rubric
from probeloop.assessment.application.schemas import EvidenceData, JudgementsOut
from probeloop.assessment.domain.model import Evidence, Observation, Score
from probeloop.context.application.analysis import normalise


@dataclass(frozen=True, slots=True)
class Source:
    text: str
    turn_seq: int | None = None


def checked_evidence(items: list[EvidenceData], sources: dict[str, Source]) -> tuple[Evidence, ...]:
    verified: dict[tuple[str, str], Evidence] = {}
    for item in items:
        source = sources.get(item.source_id)
        quote = normalise(item.quote)
        if (
            source is not None
            and item.turn_seq in (None, source.turn_seq)
            and len(quote) >= 8
            and quote in normalise(source.text)
        ):
            # The source registry owns turn identity. An omitted redundant turn number is
            # resolved from it; an explicitly conflicting number is rejected.
            verified[(item.source_id, quote)] = Evidence(
                item.source_id, item.quote, source.turn_seq
            )
    return tuple(verified.values())


def checked_judgements(
    output: JudgementsOut,
    rubric: Rubric,
    sources: dict[str, Source],
    *,
    language: str,
    unit_id: str | None = None,
) -> tuple[tuple[Score, ...], tuple[Observation, ...], int]:
    unavailable = {
        "it": "Evidenza insufficiente o citazione non verificata.",
        "en": "Insufficient evidence or an unverified quotation.",
    }[language]
    counts = Counter(item.criterion_id for item in output.scores)
    by_id = {item.criterion_id: item for item in output.scores if counts[item.criterion_id] == 1}
    scores = []
    dropped = sum(
        item.criterion_id not in {c.id for c in rubric.criteria} for item in output.scores
    )
    dropped += sum(count for count in counts.values() if count > 1)
    for criterion in rubric.criteria:
        item = by_id.get(criterion.id)
        evidence = checked_evidence(item.evidence, sources) if item else ()
        valid = item is not None and item.score is not None and bool(evidence)
        if item and item.score is not None and not valid:
            dropped += 1
        scores.append(
            Score(
                criterion.id,
                label(criterion.label, language),
                item.score if valid and item else None,
                item.reason if evidence and item else unavailable,
                evidence,
                unit_id=unit_id,
            )
        )
    observations = []
    for note in output.observations:
        evidence = checked_evidence(note.evidence, sources)
        if not evidence:
            dropped += 1
            continue
        if note.kind == "rewrite" and note.replacement:
            numbers = set(re.findall(r"\d+(?:[.,]\d+)?", note.replacement))
            originals = " ".join(e.quote for e in evidence)
            if not numbers.issubset(set(re.findall(r"\d+(?:[.,]\d+)?", originals))):
                dropped += 1
                continue
        observations.append(Observation(note.kind, note.text, evidence, note.replacement, unit_id))
    return tuple(scores), tuple(observations), dropped
