from __future__ import annotations

import io
import wave

import pytest

from probeloop.speech.audio import PcmAudio, from_wav, to_wav
from tests.speech_audio import tone


def test_duration_and_sample_count() -> None:
    audio = PcmAudio(tone(1.5))
    assert audio.samples == 24_000
    assert audio.duration_s == pytest.approx(1.5)


def test_odd_byte_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="even number"):
        PcmAudio(b"\x00\x01\x02")


def test_wav_round_trip_keeps_samples_and_rate() -> None:
    audio = PcmAudio(tone(0.3), sample_rate=22_050)
    assert from_wav(to_wav(audio)) == audio


def test_stereo_wav_is_rejected() -> None:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(16_000)
        out.writeframes(bytes(400))
    with pytest.raises(ValueError, match="mono 16-bit"):
        from_wav(buffer.getvalue())


def test_garbage_is_rejected() -> None:
    with pytest.raises(ValueError, match="valid WAV"):
        from_wav(b"not a wav file at all")
