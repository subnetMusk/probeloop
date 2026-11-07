from __future__ import annotations

import random
from array import array
from dataclasses import dataclass
from typing import Any

import pytest

from probeloop.speech.ports import VAD_WINDOW_SAMPLES
from probeloop.speech.segmenter import SegmenterConfig, SpeechSegment, SpeechSegmenter

W = VAD_WINDOW_SAMPLES
PAD = 3200  # 200 ms at 16 kHz
MAX = 240_000  # 15 s


@dataclass
class ScriptedVad:
    """Returns the scripted probability for each window, then 0."""

    probabilities: list[float]
    calls: int = 0

    def speech_probability(self, window: bytes) -> float:
        assert len(window) == 2 * W
        p = self.probabilities[self.calls] if self.calls < len(self.probabilities) else 0.0
        self.calls += 1
        return p


def script(*parts: tuple[float, int]) -> list[float]:
    """(probability, number of 32 ms windows) pairs."""
    return [p for p, n in parts for _ in range(n)]


def stream(samples: int) -> bytes:
    """Distinct sample values, so that slices can be checked."""
    return array("h", [i % 30_000 for i in range(samples)]).tobytes()


def run(
    probabilities: list[float],
    *,
    extra_samples: int = 0,
    chunk_bytes: int | None = None,
    config: SegmenterConfig | None = None,
) -> tuple[list[SpeechSegment], SpeechSegmenter, bytes]:
    segmenter = SpeechSegmenter(ScriptedVad(probabilities), config)
    pcm = stream(len(probabilities) * W + extra_samples)
    size = chunk_bytes or len(pcm)
    segments: list[SpeechSegment] = []
    for i in range(0, len(pcm), size):
        segments += segmenter.feed(pcm[i : i + size])
    return segments + segmenter.flush(), segmenter, pcm


def spans(segments: list[SpeechSegment]) -> list[tuple[int, int, bool]]:
    return [(s.start, s.end, s.forced) for s in segments]


def test_a_pause_of_600_ms_closes_the_segment_with_padding() -> None:
    probabilities = script((0.0, 10), (0.9, 31), (0.0, 31), (0.9, 31), (0.0, 31))
    segments, _, _ = run(probabilities)
    assert spans(segments) == [
        (10 * W - PAD, 41 * W + PAD, False),
        (72 * W - PAD, 103 * W + PAD, False),
    ]
    assert [s.index for s in segments] == [0, 1]


def test_a_shorter_pause_keeps_the_segment_open() -> None:
    probabilities = script((0.0, 10), (0.9, 31), (0.0, 13), (0.9, 31), (0.0, 31))
    segments, _, _ = run(probabilities)
    assert spans(segments) == [(10 * W - PAD, 85 * W + PAD, False)]


def test_segments_carry_their_own_audio() -> None:
    probabilities = script((0.0, 10), (0.9, 31), (0.0, 31))
    segments, segmenter, pcm = run(probabilities)
    (segment,) = segments
    assert segment.audio.data == pcm[segment.start * 2 : segment.end * 2]
    assert segment.start_s == pytest.approx(segment.start / 16_000)
    assert segment.duration_s == pytest.approx((segment.end - segment.start) / 16_000)
    assert segmenter.audio.data == pcm


@pytest.mark.parametrize(("speech_windows", "kept"), [(7, False), (8, True)])
def test_bursts_shorter_than_250_ms_are_discarded(speech_windows: int, kept: bool) -> None:
    segments, segmenter, _ = run(script((0.0, 10), (0.9, speech_windows), (0.0, 31)))
    assert bool(segments) is kept
    assert segmenter.discarded == (0 if kept else 1)


def test_uncertain_windows_neither_start_nor_end_a_pause() -> None:
    probabilities = script((0.9, 10), (0.4, 30), (0.0, 25))
    segments, _, _ = run(probabilities)
    assert spans(segments) == [(0, 40 * W + PAD, False)]

    probabilities = script((0.9, 31), (0.0, 10), (0.4, 5), (0.0, 10))
    segments, _, _ = run(probabilities)
    assert spans(segments) == [(0, 31 * W + PAD, False)]


def test_long_speech_without_pauses_is_cut_at_15_s() -> None:
    probabilities = script((0.9, 625), (0.0, 31))
    segments, _, _ = run(probabilities)
    assert spans(segments) == [(0, MAX, True), (MAX, 625 * W + PAD, False)]


def test_a_forced_cut_prefers_the_latest_short_pause() -> None:
    probabilities = script((0.9, 313), (0.0, 8), (0.9, 250), (0.0, 31))
    segments, _, _ = run(probabilities)
    first, second = segments
    assert first.forced
    assert 313 * W < first.end < 321 * W  # inside the pause
    assert second.start == first.end
    assert not second.forced


def test_a_pause_right_after_the_segment_start_is_not_used_for_a_cut() -> None:
    probabilities = script((0.9, 16), (0.0, 8), (0.9, 500), (0.0, 31))
    segments, _, _ = run(probabilities)
    assert segments[0].end == MAX
    assert segments[0].forced


def test_flush_closes_speech_at_the_end_of_the_stream() -> None:
    segments, _, _ = run(script((0.9, 62)), extra_samples=100)
    assert spans(segments) == [(0, 62 * W + 100, False)]


def test_flush_during_a_short_pause_ends_at_the_pause() -> None:
    segments, _, _ = run(script((0.9, 62), (0.0, 9)))
    assert spans(segments) == [(0, 62 * W + PAD, False)]


def test_flush_without_speech_returns_nothing() -> None:
    segments, segmenter, _ = run(script((0.0, 100)))
    assert segments == []
    assert segmenter.flush() == []


def test_frame_sizes_do_not_change_the_result() -> None:
    probabilities = script((0.0, 10), (0.9, 40), (0.0, 25), (0.9, 500), (0.0, 30))
    reference, _, _ = run(probabilities)
    rng = random.Random(1)
    segmenter = SpeechSegmenter(ScriptedVad(probabilities))
    pcm = stream(len(probabilities) * W)
    segments: list[SpeechSegment] = []
    i = 0
    while i < len(pcm):
        size = 2 * rng.randint(1, 2000)
        segments += segmenter.feed(pcm[i : i + size])
        i += size
    segments += segmenter.flush()
    assert spans(segments) == spans(reference)


def test_misuse_is_rejected() -> None:
    segmenter = SpeechSegmenter(ScriptedVad([]))
    with pytest.raises(ValueError, match="even number"):
        segmenter.feed(b"\x00\x00\x00")
    segmenter.flush()
    with pytest.raises(RuntimeError, match="flushed"):
        segmenter.feed(b"\x00\x00")


@pytest.mark.parametrize(
    "overrides",
    [
        {"threshold": 0.3, "neg_threshold": 0.35},
        {"pad_s": 0.7},
        {"split_pause_s": 0.6},
        {"min_forced_segment_s": 15.0},
    ],
)
def test_inconsistent_configuration_is_rejected(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValueError):  # noqa: PT011 - each case has its own message
        SegmenterConfig(**overrides)
