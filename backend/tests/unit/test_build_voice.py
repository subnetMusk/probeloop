"""The composition root picks the speech adapters from the settings."""

from __future__ import annotations

import json
from pathlib import Path

from probeloop.ai.ports import ChatMessage, ChatRequest
from probeloop.bootstrap import build, build_voice, scripted_moves
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
    assert voice.stt_status == voice.stt.status
    assert voice.tts_status == voice.tts.status


def test_fake_speech_for_end_to_end_tests() -> None:
    voice = build_voice(settings(speech_fake=True))
    assert voice is not None
    assert isinstance(voice.stt, FakeSpeechToText)
    assert isinstance(voice.tts, FakeTextToSpeech)
    assert voice.voice_for(Language.ENGLISH) is None


def test_scripted_moves_ask_numbered_questions_then_say_goodbye() -> None:
    move = scripted_moves(questions=2)

    def after(moves: int) -> dict[str, str]:
        history = [ChatMessage(role, "x") for _ in range(moves) for role in ("user", "assistant")]
        request = ChatRequest(instructions="", messages=(*history, ChatMessage("user", "x")))
        return json.loads(move(request))  # type: ignore[no-any-return]

    assert after(0) == after(0)  # every session starts the same way
    assert after(0)["utterance"] == "Questa è la domanda di prova numero 1?"
    assert after(1)["utterance"] == "Questa è la domanda di prova numero 2?"
    assert after(2)["action"] == "end"


def test_the_fake_language_model_is_selected_by_the_settings(tmp_path: Path) -> None:
    container = build(settings(data_dir=tmp_path, llm_fake=True, speech_fake=True))
    assert container.model.model_ref == "fake:scripted"
    assert container.sessions.voice is not None
