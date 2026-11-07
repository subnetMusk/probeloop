"""PCM audio and WAV conversion.

The whole capture path uses one format: signed 16-bit little-endian mono PCM at 16 kHz. The
browser produces it, the voice activity detector and the recognisers consume it, and it is what
gets stored. Synthesised speech keeps the sample rate of its voice.
"""

from __future__ import annotations

import io
import wave
from dataclasses import dataclass
from typing import Final

SAMPLE_RATE: Final = 16_000
SAMPLE_WIDTH: Final = 2  # bytes per sample


@dataclass(frozen=True, slots=True)
class PcmAudio:
    """Signed 16-bit little-endian mono PCM."""

    data: bytes
    sample_rate: int = SAMPLE_RATE

    def __post_init__(self) -> None:
        if len(self.data) % SAMPLE_WIDTH:
            raise ValueError("16-bit PCM needs an even number of bytes")
        if self.sample_rate <= 0:
            raise ValueError("the sample rate must be positive")

    @property
    def samples(self) -> int:
        return len(self.data) // SAMPLE_WIDTH

    @property
    def duration_s(self) -> float:
        return self.samples / self.sample_rate


def to_wav(audio: PcmAudio) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(SAMPLE_WIDTH)
        out.setframerate(audio.sample_rate)
        out.writeframes(audio.data)
    return buffer.getvalue()


def from_wav(data: bytes) -> PcmAudio:
    """Read a mono 16-bit WAV file. Other layouts are rejected rather than converted."""
    try:
        with wave.open(io.BytesIO(data), "rb") as source:
            if source.getnchannels() != 1 or source.getsampwidth() != SAMPLE_WIDTH:
                raise ValueError("expected mono 16-bit PCM")
            return PcmAudio(source.readframes(source.getnframes()), source.getframerate())
    except (wave.Error, EOFError) as exc:
        raise ValueError("not a valid WAV file") from exc
