"""NumPy audio helpers for the adapters: recogniser input, resampling and joining recordings."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

from probeloop.speech.audio import PcmAudio


def float_samples(audio: PcmAudio) -> npt.NDArray[np.float32]:
    """PCM16 as float32 in [-1, 1), the input format of both recognisers."""
    return np.frombuffer(audio.data, dtype="<i2").astype(np.float32) / 32768.0


def _pcm(samples: npt.NDArray[np.floating], rate: int) -> PcmAudio:
    clipped = np.clip(np.round(samples * 32767.0), -32768, 32767).astype("<i2")
    return PcmAudio(clipped.tobytes(), rate)


def resample(audio: PcmAudio, rate: int) -> PcmAudio:
    """Change the sample rate: a windowed-sinc low-pass when going down, then interpolation."""
    if audio.sample_rate == rate or not audio.data:
        return PcmAudio(audio.data, rate)
    samples = float_samples(audio).astype(np.float64)
    if rate < audio.sample_rate:
        cutoff = 0.45 * rate / audio.sample_rate  # cycles per input sample
        taps = np.arange(-64, 65)
        kernel = 2 * cutoff * np.sinc(2 * cutoff * taps) * np.blackman(taps.size)
        samples = np.convolve(samples, kernel / kernel.sum(), mode="same")
    count = round(samples.size * rate / audio.sample_rate)
    positions = np.arange(count) * (audio.sample_rate / rate)
    return _pcm(np.interp(positions, np.arange(samples.size), samples), rate)


def concatenate(parts: Sequence[PcmAudio], *, gap_s: float = 0.0) -> PcmAudio:
    """Join recordings at the highest of their sample rates, with silence between them."""
    if not parts:
        return PcmAudio(b"")
    rate = max(p.sample_rate for p in parts)
    gap = bytes(2 * round(gap_s * rate))
    chunks: list[bytes] = []
    for i, part in enumerate(parts):
        if i:
            chunks.append(gap)
        chunks.append(resample(part, rate).data)
    return PcmAudio(b"".join(chunks), rate)
