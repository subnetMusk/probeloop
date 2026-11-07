"""The composition root picks the speech adapters from the settings."""

from __future__ import annotations

from pathlib import Path

from probeloop.bootstrap import build_voice
from probeloop.interview.domain.model import Language
from probeloop.settings import Settings
from probeloop.speech.fake import FakeSpeechToText, FakeTextToSpeech
from probeloop.speech.http_stt import HttpSpeechToText
from probeloop.speech.piper import PiperTextToSpeech


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {"data_dir": Path("/tmp"), "stt_url": None, "tts_url": None}
    return Settings(**(values | overrides))  # type: ignore[arg-type]


def test_without_service_urls_there_is_no_voice() -> None:
    assert build_voice(settings()) is None
    assert build_voice(settings(stt_url="http://stt-worker:8000")) is None


def test_service_urls_select_the_http_adapters_and_their_checks() -> None:
    voice = build_voice(
        settings(
            stt_url="http://stt-worker:8000",
            tts_url="http://tts-piper:5000",
            tts_voice_en="en_GB-test-medium",
        )
    )
    assert voice is not None
    assert isinstance(voice.stt, HttpSpeechToText)
    assert isinstance(voice.tts, PiperTextToSpeech)
    assert voice.voices == {
        Language.ITALIAN: "it_IT-serena-medium",
        Language.ENGLISH: "en_GB-test-medium",
    }
    assert len(voice.checks) == 3  # the worker, then one per voice


def test_fake_speech_for_end_to_end_tests() -> None:
    voice = build_voice(settings(speech_fake=True))
    assert voice is not None
    assert isinstance(voice.stt, FakeSpeechToText)
    assert isinstance(voice.tts, FakeTextToSpeech)
    assert voice.checks == []
    assert voice.voice_for(Language.ENGLISH) is None
