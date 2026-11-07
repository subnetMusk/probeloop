"""Silero VAD through `pysilero-vad` (MIT), which bundles the model and needs no PyTorch."""

from __future__ import annotations

from pysilero_vad import SileroVoiceActivityDetector


class SileroVad:
    """One detector per audio stream: the model keeps state between windows."""

    def __init__(self) -> None:
        self._detector = SileroVoiceActivityDetector()

    def speech_probability(self, window: bytes) -> float:
        return float(self._detector(window))
