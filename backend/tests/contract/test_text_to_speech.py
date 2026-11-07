"""The same contract for every TextToSpeech adapter.

`piper` needs `-m live` and a running tts-piper service, for example:

    docker compose -f compose.yaml -f compose.dev.yaml run --rm \\
        -e PROBELOOP_TEST_TTS_URL=http://tts-piper:5000 backend \\
        pytest -m live tests/contract/test_text_to_speech.py
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest

from probeloop.speech.fake import FakeTextToSpeech
from probeloop.speech.piper import PiperTextToSpeech
from probeloop.speech.ports import SpeechError, TextToSpeech

VOICE = os.environ.get("PROBELOOP_TEST_TTS_VOICE", "it_IT-serena-medium")
QUESTION = "Mi racconta quale problema concreto risolveva il servizio che ha progettato?"


@pytest.fixture(params=["fake", pytest.param("piper", marks=pytest.mark.live)])
async def tts(request: pytest.FixtureRequest) -> AsyncIterator[TextToSpeech]:
    if request.param == "fake":
        yield FakeTextToSpeech()
        return
    url = os.environ.get("PROBELOOP_TEST_TTS_URL")
    if not url:
        pytest.skip("PROBELOOP_TEST_TTS_URL is not set")
    adapter = PiperTextToSpeech(url)
    yield adapter
    await adapter.aclose()


async def test_a_sentence_becomes_mono_pcm(tts: TextToSpeech) -> None:
    audio = await tts.synthesize(QUESTION, VOICE)
    assert audio.sample_rate >= 16_000
    assert 2.0 <= audio.duration_s <= 15.0  # about 12 words


async def test_longer_text_gives_longer_audio(tts: TextToSpeech) -> None:
    short = await tts.synthesize("Bene.", VOICE)
    long = await tts.synthesize(QUESTION, VOICE)
    assert long.duration_s > short.duration_s


async def test_blank_text_is_an_error(tts: TextToSpeech) -> None:
    with pytest.raises(SpeechError):
        await tts.synthesize("   ", VOICE)
