"""Splits streamed text into sentences, so speech synthesis can start before the text is complete.

A sentence ends at `.`, `!`, `?` or `…` (closing quotes and brackets included), followed by white
space and a character that can start a new sentence. That character must already have arrived,
so a boundary costs one more streamed token, about 20 ms. Not a boundary:

- a following lower-case letter ("tre... forse quattro");
- a known abbreviation or a single initial before the full stop ("Dott. Rossi", "A. Rossi");
- a full stop inside a number ("3.5").

A sentence that grows past `max_chars` without ending is cut at its last comma, semicolon or
colon (or at its last space), which bounds the wait for the first audio.
"""

from __future__ import annotations

import re

ABBREVIATIONS = frozenset(
    {
        # Italian titles and references
        "sig",
        "sigg",
        "sig.ra",
        "sig.na",
        "dott",
        "dott.ssa",
        "prof",
        "prof.ssa",
        "ing",
        "avv",
        "arch",
        "geom",
        "rag",
        "es",
        "p.es",
        "cfr",
        "pag",
        "art",
        "n",
        "nr",
        # English
        "mr",
        "mrs",
        "ms",
        "dr",
        "st",
        "e.g",
        "i.e",
        "vs",
    }
)

# Brackets, straight quotes, guillemets and typographic double and single quotes.
_OPENERS = "(\"'\u00ab\u201c\u2018"
_CLOSERS = "\"'\u00bb\u201d\u2019)]"
_BOUNDARY = re.compile(rf"([.!?\u2026]+)([{re.escape(_CLOSERS)}]*)\s+(?=\S)")
_LAST_WORD = re.compile(r"(\S+)$")
_SOFT_BREAK = re.compile(r"[,;:]\s")


def _is_abbreviation(word: str) -> bool:
    word = word.lstrip(_OPENERS).lower()
    if len(word) == 1 and word.isalpha():
        return True  # an initial
    return word in ABBREVIATIONS


def _speakable(text: str) -> bool:
    return any(ch.isalnum() for ch in text)


class SentenceSplitter:
    def __init__(self, *, max_chars: int = 250) -> None:
        if max_chars < 20:
            raise ValueError("max_chars is too small for a sentence")
        self._max_chars = max_chars
        self._buffer = ""

    def feed(self, text: str) -> list[str]:
        """Add streamed text; return the sentences it completed."""
        self._buffer += text
        out: list[str] = []
        start = 0
        position = 0
        while (match := _BOUNDARY.search(self._buffer, position)) is not None:
            position = match.end(1)
            following = self._buffer[match.end()]
            if following.islower():
                continue
            if match.group(1) == ".":
                word = _LAST_WORD.search(self._buffer, start, match.start(1))
                if word is not None and _is_abbreviation(word.group(1)):
                    continue
            out.append(self._buffer[start : match.end(2)].strip())
            start = position = match.end()
        self._buffer = self._buffer[start:]
        while len(self._buffer) > self._max_chars:
            cut = self._soft_cut(self._buffer[: self._max_chars])
            out.append(self._buffer[:cut].strip())
            self._buffer = self._buffer[cut:].lstrip()
        return [s for s in out if _speakable(s)]

    def flush(self) -> list[str]:
        """Return the text left over at the end of the stream."""
        rest, self._buffer = self._buffer.strip(), ""
        return [rest] if _speakable(rest) else []

    @staticmethod
    def _soft_cut(text: str) -> int:
        breaks = list(_SOFT_BREAK.finditer(text))
        if breaks:
            return breaks[-1].start() + 1
        space = text.rfind(" ")
        return space if space > 0 else len(text)
