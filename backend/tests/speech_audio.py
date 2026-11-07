"""Synthetic audio for speech tests: tones, silence, noise and the Piper fixtures."""

from __future__ import annotations

import json
import math
import random
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from probeloop.speech.audio import SAMPLE_RATE, PcmAudio, from_wav

FIXTURES = Path(__file__).parent / "fixtures" / "synthetic" / "speech"


def _pcm(samples: list[float]) -> bytes:
    return array("h", [max(-32768, min(32767, round(s * 32767))) for s in samples]).tobytes()


def tone(seconds: float, amplitude: float = 0.3, frequency: float = 220.0) -> bytes:
    n = round(seconds * SAMPLE_RATE)
    step = 2 * math.pi * frequency / SAMPLE_RATE
    return _pcm([amplitude * math.sin(step * i) for i in range(n)])


def silence(seconds: float) -> bytes:
    return bytes(2 * round(seconds * SAMPLE_RATE))


def noise(seconds: float, rms: float = 0.001, seed: int = 0) -> bytes:
    """Gaussian noise; the default level is about -60 dBFS, a quiet room."""
    rng = random.Random(seed)
    return _pcm([rng.gauss(0.0, rms) for _ in range(round(seconds * SAMPLE_RATE))])


def frames(pcm: bytes, frame_s: float = 0.02) -> list[bytes]:
    size = 2 * round(frame_s * SAMPLE_RATE)
    return [pcm[i : i + size] for i in range(0, len(pcm), size)]


@dataclass(frozen=True, slots=True)
class Utterance:
    text: str
    start_s: float
    end_s: float


@dataclass(frozen=True, slots=True)
class SpeechFixture:
    name: str
    audio: PcmAudio
    utterances: tuple[Utterance, ...]

    @property
    def text(self) -> str:
        return " ".join(u.text for u in self.utterances)


def speech_fixture(name: str) -> SpeechFixture:
    manifest: dict[str, Any] = json.loads((FIXTURES / "manifest.json").read_text("utf-8"))
    entry = manifest["fixtures"][name]
    return SpeechFixture(
        name=name,
        audio=from_wav((FIXTURES / f"{name}.wav").read_bytes()),
        utterances=tuple(Utterance(**u) for u in entry["utterances"]),
    )
