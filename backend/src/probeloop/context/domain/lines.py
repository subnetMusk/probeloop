"""Logical lines of extracted document text: a wrapped bullet or sentence becomes one line.

Extracted CVs wrap a bullet or a paragraph over several physical lines, so a measure or a claim
can start on one line and end on the next. Judging a physical line alone misreads both. A new
logical line starts after a blank line, at a list item, at a date that opens an entry, after a
line that ends a sentence, and at a short heading; otherwise an indented line, a line that starts
in lower case or with punctuation, or a line after a full-width one continues the previous line.
"""

from __future__ import annotations

import re

_BULLET = re.compile(r"^(?:[-*\u2022\u2013]|\d+[.)])\s")
_MONTH = (
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|"
    r"gen|mag|giu|lug|ago|set|ott|dic)[a-z]*\.?"
)
_DATE = re.compile(rf"^(?:\d{{1,2}}/|{_MONTH}\s+)?(?:19|20)\d{{2}}\b", re.IGNORECASE)
_TERMINAL = (".", "!", "?", ":", ";")
_FULL_WIDTH = 60  # characters: a line this long that does not end a sentence was wrapped
_HEADING_WORDS = 4


def logical_lines(text: str) -> list[str]:
    out: list[str] = []
    last = ""  # the previous physical line; empty after a blank line
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            last = ""
            continue
        if out and last and _continues(last, raw, line):
            out[-1] = f"{out[-1]} {line}"
        else:
            out.append(line)
        last = line
    return out


def _continues(last: str, raw: str, line: str) -> bool:
    if _BULLET.match(line) or _DATE.match(line) or last.endswith(_TERMINAL):
        return False
    if raw[:1].isspace():
        return True
    if line[0].isupper() and len(line.split()) <= _HEADING_WORDS and not line.endswith(_TERMINAL):
        return False
    return not line[0].isupper() or last.endswith(",") or len(last) >= _FULL_WIDTH
