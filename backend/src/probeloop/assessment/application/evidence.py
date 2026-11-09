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

_WORD = re.compile(r"\w")
_ELISION = re.compile(r"\.{3,}|…")
_MIN_QUOTE_CHARS = 8


@dataclass(frozen=True, slots=True)
class Source:
    text: str
    turn_seq: int | None = None


def source_span(quote: str, text: str) -> str | None:
    """The passage of `text` that a quotation matches after normalisation, as the source writes it.

    Matching ignores case and punctuation, as transcripts punctuate freely; what is stored and
    shown is the source's own text, never the model's rendering of it (for example with an
    added ellipsis).
    """
    needle = normalise(quote)
    chars: list[str] = []
    origin: list[int] = []
    gap = False
    for index, char in enumerate(text):
        if not _WORD.fullmatch(char):
            gap = True
            continue
        if gap and chars:
            chars.append(" ")
            origin.append(index)
        for lowered in char.lower():
            chars.append(lowered)
            origin.append(index)
        gap = False
    start = "".join(chars).find(needle) if needle else -1
    if start < 0:
        return None
    return text[origin[start] : origin[start + len(needle) - 1] + 1]


def _verified_parts(quote: str, text: str) -> list[tuple[str, str]] | None:
    """The normalised parts of a quotation and their source passages, or None if any part fails.

    An elision ("..." or "…") marks omitted words: each part around it must still be
    verbatim and long enough on its own, so one unverifiable part rejects the whole quotation.
    """
    parts: list[tuple[str, str]] = []
    for fragment in _ELISION.split(quote):
        needle = normalise(fragment)
        if not needle:
            continue
        span = source_span(fragment, text)
        if span is None or len(needle) < _MIN_QUOTE_CHARS:
            return None
        parts.append((needle, span))
    return parts or None


def checked_evidence(items: list[EvidenceData], sources: dict[str, Source]) -> tuple[Evidence, ...]:
    verified: dict[tuple[str, str], Evidence] = {}
    for item in items:
        source = sources.get(item.source_id)
        # The source registry owns turn identity. An omitted redundant turn number is resolved
        # from it; an explicitly conflicting number is rejected.
        if source is None or item.turn_seq not in (None, source.turn_seq):
            continue
        for quote, span in _verified_parts(item.quote, source.text) or ():
            verified[(item.source_id, quote)] = Evidence(item.source_id, span, source.turn_seq)
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
        observations.append(
            Observation(
                note.kind, note.text, evidence, note.replacement, unit_id, note.criterion_id
            )
        )
    return tuple(scores), tuple(observations), dropped
