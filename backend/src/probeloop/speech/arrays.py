"""NumPy conversions shared by the in-process recognisers. Only the stt-worker image has NumPy."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from probeloop.speech.audio import PcmAudio


def float_samples(audio: PcmAudio) -> npt.NDArray[np.float32]:
    """PCM16 as float32 in [-1, 1), the input format of both recognisers."""
    return np.frombuffer(audio.data, dtype="<i2").astype(np.float32) / 32768.0
