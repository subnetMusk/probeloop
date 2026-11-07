"""Defences against text that a recogniser produces from silence or noise.

Voice activity detection is the first gate: silence never reaches the recogniser. These checks
catch what slips through:

- phrases that recognisers trained on subtitles are known to invent (M1 found "Grazie." on
  silence without VAD; the subtitle credits are a classic Whisper hallucination);
- looping output, measured as Whisper does with the zlib compression ratio;
- far more words than the segment could hold.
"""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass

BLOCKLIST = (
    "sottotitoli creati dalla comunità amara.org",
    "sottotitoli a cura di",
    "sottotitoli e revisione a cura di",
    "amara.org",
    "grazie per la visione",
    "iscriviti al canale",
    "thanks for watching",
    "thank you for watching",
    "subtitles by",
)

_NON_WORD = re.compile(r"[^\w]+")


def normalise(text: str) -> str:
    """Lower case, words only, single spaces."""
    return " ".join(_NON_WORD.sub(" ", text.lower()).split())


@dataclass(frozen=True, slots=True)
class FilterConfig:
    blocklist: tuple[str, ...] = BLOCKLIST
    max_compression_ratio: float = 2.4
    max_words_per_s: float = 7.0
    word_allowance: int = 4  # added to the per-second limit, for very short segments


def compression_ratio(text: str) -> float:
    data = text.encode("utf-8")
    return len(data) / len(zlib.compress(data)) if data else 0.0


def rejection_reason(
    text: str, duration_s: float, config: FilterConfig | None = None
) -> str | None:
    """Why the text of a segment of `duration_s` seconds should be discarded, or None to keep it."""
    config = config or FilterConfig()
    words = normalise(text)
    if not words:
        return "no_words"
    padded = f" {words} "
    if any(f" {normalise(phrase)} " in padded for phrase in config.blocklist):
        return "blocklist"
    if compression_ratio(text) > config.max_compression_ratio:
        return "repetition"
    if len(words.split()) > config.word_allowance + config.max_words_per_s * duration_s:
        return "too_many_words"
    return None
