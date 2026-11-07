"""The same contract for every SpeechToText adapter.

- `fake` and `http-fake` (the HTTP client against the worker app hosting fakes) run in CI.
- `parakeet` and `whisper` are the in-process engines; `http-worker` is a running stt-worker
  (set `PROBELOOP_TEST_STT_URL`). They need `-m live` and the models volume, for example:

      docker compose -f compose.yaml -f compose.dev.yaml run --rm \\
          -e PROBELOOP_TEST_STT_URL=http://stt-worker:8000 backend \\
          pytest -m live tests/contract/test_speech_to_text.py
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from rapidfuzz import fuzz

from probeloop.speech.audio import PcmAudio
from probeloop.speech.fake import FakeSpeechToText
from probeloop.speech.filters import normalise
from probeloop.speech.http_stt import HttpSpeechToText
from probeloop.speech.ports import SpeechToText, TranscribeOptions
from probeloop.speech.worker import create_worker_app
from tests.speech_audio import speech_fixture

ITALIAN = TranscribeOptions(language="it")
_loaded: dict[str, Any] = {}  # in-process engines take 20-30 s to load: once per test run


def local_engine(name: str) -> SpeechToText:
    if name not in _loaded:
        if name == "parakeet":
            from probeloop.speech.parakeet import ParakeetSpeechToText

            _loaded[name] = ParakeetSpeechToText()
        else:
            from probeloop.speech.whisper import WhisperSpeechToText

            _loaded[name] = WhisperSpeechToText()
    engine: SpeechToText = _loaded[name]
    return engine


async def make_adapter(name: str) -> AsyncIterator[SpeechToText]:
    if name == "fake":
        yield FakeSpeechToText()
    elif name == "http-fake":
        app = create_worker_app({"live": FakeSpeechToText(), "refine": FakeSpeechToText()})
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://stt-worker"
        )
        yield HttpSpeechToText("http://stt-worker", client=client)
        await client.aclose()
    elif name == "http-worker":
        url = os.environ.get("PROBELOOP_TEST_STT_URL")
        if not url:
            pytest.skip("PROBELOOP_TEST_STT_URL is not set")
        adapter = HttpSpeechToText(url, timeout_s=120)
        yield adapter
        await adapter.aclose()
    else:
        yield local_engine(name)


LIVE = pytest.mark.live
REAL = [
    pytest.param("parakeet", marks=LIVE),
    pytest.param("whisper", marks=LIVE),
    pytest.param("http-worker", marks=LIVE),
]


@pytest.fixture(params=["fake", "http-fake", *REAL])
async def stt(request: pytest.FixtureRequest) -> AsyncIterator[SpeechToText]:
    async for adapter in make_adapter(request.param):
        yield adapter


@pytest.fixture(params=REAL)
async def real_stt(request: pytest.FixtureRequest) -> AsyncIterator[SpeechToText]:
    async for adapter in make_adapter(request.param):
        yield adapter


async def test_transcription_describes_the_audio_it_was_given(stt: SpeechToText) -> None:
    audio = speech_fixture("late_start").audio
    result = await stt.transcribe(audio, ITALIAN)
    assert result.engine_ref
    assert stt.engine_ref == result.engine_ref
    assert result.language == "it"
    assert result.text.strip()
    starts = [s.start_s for s in result.segments]
    assert starts == sorted(starts)
    for segment in result.segments:
        assert 0.0 <= segment.start_s <= segment.end_s <= audio.duration_s + 0.1
        assert segment.text == " ".join(segment.text.split())


async def test_empty_audio_gives_an_empty_text(stt: SpeechToText) -> None:
    result = await stt.transcribe(PcmAudio(b""), ITALIAN)
    assert result.text == ""


async def test_word_timestamps_when_requested(stt: SpeechToText) -> None:
    audio = speech_fixture("late_start").audio
    result = await stt.transcribe(audio, TranscribeOptions(language="it", word_timestamps=True))
    assert result.segments
    for segment in result.segments:
        assert segment.words
        assert normalise(" ".join(w.text for w in segment.words)) == normalise(segment.text)
        starts = [w.start_s for w in segment.words]
        assert starts == sorted(starts)
        for word in segment.words:
            assert segment.start_s - 0.1 <= word.start_s <= word.end_s <= segment.end_s + 0.1
            assert word.probability is None or 0.0 <= word.probability <= 1.0


async def test_real_engines_recognise_synthetic_italian(real_stt: SpeechToText) -> None:
    fixture = speech_fixture("three_sentences")
    options = TranscribeOptions(language="it", initial_prompt="Python, PostgreSQL, API")
    result = await real_stt.transcribe(fixture.audio, options)
    assert fuzz.ratio(normalise(result.text), normalise(fixture.text)) >= 85
