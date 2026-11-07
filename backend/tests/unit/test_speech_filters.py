from __future__ import annotations

import pytest

from probeloop.speech.filters import FilterConfig, normalise, rejection_reason


@pytest.mark.parametrize(
    "text",
    [
        "Ho lavorato tre anni con Python e PostgreSQL.",
        "Sì.",
        "Grazie.",  # a legitimate answer; only VAD gating protects silence from it
        "No, no, aspetti: intendevo un'altra cosa.",
    ],
)
def test_ordinary_answers_are_kept(text: str) -> None:
    assert rejection_reason(text, duration_s=3.0) is None


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("", "no_words"),
        ("  ... !? ", "no_words"),
        ("Sottotitoli creati dalla comunità Amara.org", "blocklist"),
        ("Grazie per la visione!", "blocklist"),
        ("thanks for watching", "blocklist"),
        ("e poi e poi e poi e poi e poi e poi e poi e poi e poi e poi e poi e poi", "repetition"),
    ],
)
def test_known_hallucinations_are_rejected(text: str, reason: str) -> None:
    assert rejection_reason(text, duration_s=10.0) == reason


def test_blocklist_matches_whole_words_only() -> None:
    assert rejection_reason("Ho usato amara.org come esempio di progetto.", 5.0) == "blocklist"
    assert rejection_reason("Una scelta amaramente sbagliata.", 5.0) is None


def test_too_many_words_for_the_segment_length() -> None:
    text = "uno due tre quattro cinque sei sette otto nove dieci"
    assert rejection_reason(text, duration_s=0.5) == "too_many_words"
    assert rejection_reason(text, duration_s=1.0) is None


def test_the_blocklist_is_configurable() -> None:
    config = FilterConfig(blocklist=("buona serata",))
    assert rejection_reason("Buona serata a tutti", 3.0, config) == "blocklist"
    assert rejection_reason("Grazie per la visione", 3.0, config) is None


def test_normalise() -> None:
    assert normalise("  Così, è FINITA!  Già.") == "così è finita già"
