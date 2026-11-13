"""Obligation cues of a job offer: the phrase or section heading that makes a requirement
mandatory or preferred.

The lexicons follow the reference labelling guide of the CV check
(`backend/evals/fixtures/synthetic/cv_check/GUIDE.md`): a phrase in the requirement's own words
decides first, then the heading of its section. Without either, no cue decides.
"""

from __future__ import annotations

import re

from probeloop.context.domain.model import Obligation

_PREFERRED_PHRASES = (
    "preferibilmente",
    "è preferibile",
    "preferably",
    "gradito",
    "gradita",
    "graditi",
    "è un plus",
    "e' un plus",
    "a plus",
    "ideally",
    "idealmente",
    "titolo preferenziale",
    "nice to have",
)
_MUST_PHRASES = (
    "indispensabile",
    "indispensabili",
    "obbligatorio",
    "obbligatoria",
    "necessario",
    "necessaria",
    "required",
    "must",
    "essential",
    "you will need",
)
_MUST_HEADINGS = ("requisiti", "requirements", "cosa cerchiamo", "what we look for", "must have")
_PREFERRED_HEADINGS = (
    "preferibile",
    "preferibili",
    "gradito",
    "graditi",
    "nice to have",
    "plus",
    "bonus",
    "bonus points",
    "preferred",
    "costituisce titolo preferenziale",
    "titolo preferenziale",
)
_BULLET = re.compile(r"^(?:[-*\u2022\u2013]|\d+[.)])\s")
_HEADING_WORDS = 6


def _norm(text: str) -> str:
    return " ".join(text.casefold().split())


def _has(phrase: str, text: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


def is_offer_heading(line: str) -> bool:
    """A short line that is not a list item and does not end a sentence."""
    line = line.strip()
    return (
        bool(line)
        and not _BULLET.match(line)
        and len(line.split()) <= _HEADING_WORDS
        and not line.endswith((".", ";"))
    )


def locate(text: str, quote: str) -> tuple[str, str | None] | None:
    """The lines of `text` that `quote` covers, joined, and the heading of their section."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    starts, parts, position = [], [], 0
    for line in lines:
        part = _norm(line)
        starts.append(position)
        parts.append(part)
        position += len(part) + 1
    needle = _norm(quote)
    at = " ".join(parts).find(needle) if needle else -1
    if at < 0:
        return None
    first = max(i for i, start in enumerate(starts) if start <= at)
    last = max(i for i, start in enumerate(starts) if start <= at + len(needle) - 1)
    heading = next(
        (
            lines[i].rstrip(":").strip()
            for i in range(first - 1, -1, -1)
            if is_offer_heading(lines[i])
        ),
        None,
    )
    return " ".join(lines[first : last + 1]), heading


def cue_obligation(words: str, heading: str | None) -> tuple[Obligation, str] | None:
    """The obligation that a phrase in `words`, or else the section `heading`, states."""
    text = _norm(words)
    preferred = next((p for p in _PREFERRED_PHRASES if _has(p, text)), None)
    must = next((p for p in _MUST_PHRASES if _has(p, text)), None)
    if preferred and not must:
        return Obligation.PREFERRED, preferred
    if must and not preferred:
        return Obligation.MUST, must
    if preferred and must:
        return None
    if heading is None:
        return None
    title = _norm(heading).rstrip(":").strip()

    def names(candidates: tuple[str, ...]) -> bool:
        return any(title == c or title.startswith(f"{c} ") for c in candidates)

    if names(_PREFERRED_HEADINGS):
        return Obligation.PREFERRED, heading
    if names(_MUST_HEADINGS):
        return Obligation.MUST, heading
    return None
