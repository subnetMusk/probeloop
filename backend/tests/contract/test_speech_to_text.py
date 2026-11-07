"""Contract of the SpeechToText port. Every adapter must pass the same tests."""

from __future__ import annotations

import pytest

from probeloop.speech.audio import PcmAudio
from probeloop.speech.fake import FakeSpeechToText
from probeloop.speech.ports import SpeechToText, TranscribeOptions
from tests.speech_audio import speech_fixture


@pytest.fixture(params=["fake"])
def stt(request: pytest.FixtureRequest) -> SpeechToText:
    if request.param == "fake":
        return FakeSpeechToText()
    raise AssertionError(request.param)


async def test_transcription_describes_the_audio_it_was_given(stt: SpeechToText) -> None:
    audio = speech_fixture("late_start").audio
    result = await stt.transcribe(audio, TranscribeOptions(language="it"))
    assert result.engine_ref
    assert stt.engine_ref == result.engine_ref
    assert result.language == "it"
    assert result.text.strip()
    starts = [s.start_s for s in result.segments]
    assert starts == sorted(starts)
    for segment in result.segments:
        assert 0.0 <= segment.start_s <= segment.end_s <= audio.duration_s + 0.1


async def test_empty_audio_gives_an_empty_text(stt: SpeechToText) -> None:
    result = await stt.transcribe(PcmAudio(b""), TranscribeOptions(language="it"))
    assert result.text == ""
