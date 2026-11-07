"""Resampling and joining recordings (NumPy helpers)."""

from __future__ import annotations

import numpy as np
import pytest

from probeloop.speech.arrays import concatenate, float_samples, resample
from probeloop.speech.audio import PcmAudio


def sine(frequency: float, rate: int, seconds: float, amplitude: float = 0.5) -> PcmAudio:
    t = np.arange(round(rate * seconds)) / rate
    samples = np.round(amplitude * np.sin(2 * np.pi * frequency * t) * 32767).astype("<i2")
    return PcmAudio(samples.tobytes(), rate)


def amplitude_at(audio: PcmAudio, frequency: float) -> float:
    x = float_samples(audio).astype(np.float64)[200:-200]
    t = np.arange(x.size) / audio.sample_rate
    return float(2 * abs(np.mean(x * np.exp(-2j * np.pi * frequency * t))))


@pytest.mark.parametrize(("source", "target"), [(22_050, 16_000), (16_000, 22_050)])
def test_resampling_keeps_duration_and_tone(source: int, target: int) -> None:
    out = resample(sine(440, source, 1.0), target)
    assert out.sample_rate == target
    assert out.duration_s == pytest.approx(1.0, abs=0.001)
    assert amplitude_at(out, 440) == pytest.approx(0.5, abs=0.02)


def test_downsampling_removes_what_the_new_rate_cannot_hold() -> None:
    out = resample(sine(10_000, 22_050, 1.0), 16_000)  # above 8 kHz
    assert float(np.sqrt(np.mean(float_samples(out) ** 2))) < 0.01


def test_same_rate_and_empty_audio_are_unchanged() -> None:
    audio = sine(300, 16_000, 0.1)
    assert resample(audio, 16_000) == audio
    assert resample(PcmAudio(b"", 22_050), 16_000) == PcmAudio(b"", 16_000)


def test_concatenate_uses_the_highest_rate_and_adds_gaps() -> None:
    joined = concatenate([sine(300, 22_050, 1.0), sine(300, 16_000, 0.5)], gap_s=0.25)
    assert joined.sample_rate == 22_050
    assert joined.duration_s == pytest.approx(1.75, abs=0.001)
    assert concatenate([]) == PcmAudio(b"")
