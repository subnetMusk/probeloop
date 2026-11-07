"""Word assembly and chunking of the Parakeet adapter; no model is loaded."""

from __future__ import annotations

import math

import pytest

from probeloop.speech.parakeet import ParakeetSpeechToText, assemble_words
from tests.speech_audio import speech_fixture

# Recorded from Parakeet TDT 0.6B v3 on the late_start fixture.
TOKENS = [" Sì", ",", " cer", "to", ",", " pos", "so", " fare", " un", " es", "emp", "io", " conc"]
TIMESTAMPS = [2.24, 2.48, 2.64, 2.88, 3.12, 3.28, 3.44, 3.52, 3.68, 3.84, 4.0, 4.08, 4.24]
LOGPROBS = [-0.1, -0.01, -0.004, 0.0, -0.16, 0.0, 0.0, -0.002, 0.0, 0.0, 0.0, 0.0, -0.001]


def test_tokens_with_a_leading_space_start_new_words() -> None:
    words = assemble_words(TOKENS, TIMESTAMPS, LOGPROBS)
    assert [w.text for w in words] == ["Sì,", "certo,", "posso", "fare", "un", "esempio", "conc"]
    assert [w.start_s for w in words] == [2.24, 2.64, 3.28, 3.52, 3.68, 3.84, 4.24]
    assert [w.end_s for w in words[:-1]] == [2.64, 3.28, 3.52, 3.68, 3.84, 4.24]
    assert words[-1].end_s == pytest.approx(4.32)


def test_word_probability_is_the_geometric_mean_of_its_tokens() -> None:
    words = assemble_words(TOKENS, TIMESTAMPS, LOGPROBS)
    assert words[0].probability == pytest.approx(math.exp((-0.1 - 0.01) / 2))
    assert words[3].probability == pytest.approx(math.exp(-0.002))


def test_offset_and_missing_logprobs() -> None:
    words = assemble_words([" a", " b"], [0.0, 0.5], None, offset_s=10.0)
    assert [(w.start_s, w.end_s, w.probability) for w in words] == [
        (10.0, 10.5, None),
        (10.5, 10.58, None),
    ]


def test_no_tokens_no_words() -> None:
    assert assemble_words([], [], []) == ()


def test_short_audio_is_one_chunk_and_long_audio_is_split_at_pauses() -> None:
    audio = speech_fixture("three_sentences").audio  # 10.8 s, three sentences
    assert ParakeetSpeechToText()._chunks(audio) == [(0.0, audio)]
    chunks = ParakeetSpeechToText(max_chunk_s=5.0)._chunks(audio)
    assert len(chunks) == 3
    assert all(chunk.duration_s <= 5.0 for _, chunk in chunks)
    assert [round(start) for start, _ in chunks] == [0, 4, 8]
