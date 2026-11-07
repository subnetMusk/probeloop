"""PiperTextToSpeech against a mocked transport: request shape and error mapping."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from probeloop.speech.audio import PcmAudio, to_wav
from probeloop.speech.piper import PiperTextToSpeech
from probeloop.speech.ports import SpeechError
from tests.speech_audio import tone

VOICE = "it_IT-serena-medium"


def adapter(handler: Callable[[httpx.Request], httpx.Response]) -> PiperTextToSpeech:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://tts")
    return PiperTextToSpeech("http://tts", client=client)


def refused(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused", request=request)


def timed_out(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("no answer", request=request)


async def test_posts_the_sentence_and_returns_the_wav_audio() -> None:
    seen: list[httpx.Request] = []
    wav = to_wav(PcmAudio(tone(0.5), sample_rate=22_050))

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=wav, headers={"Content-Type": "audio/wav"})

    audio = await adapter(handler).synthesize("Buongiorno, come sta?", VOICE)
    (request,) = seen
    assert request.method == "POST"
    assert request.url.path == "/synthesize"
    assert json.loads(request.content) == {"text": "Buongiorno, come sta?", "voice": VOICE}
    assert audio.sample_rate == 22_050
    assert audio.data == PcmAudio(tone(0.5), sample_rate=22_050).data


async def test_blank_text_is_refused_before_sending() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    with pytest.raises(SpeechError, match="nothing"):
        await adapter(handler).synthesize("  ", VOICE)


@pytest.mark.parametrize(
    ("handler", "message"),
    [
        (refused, "unreachable: ConnectError"),
        (timed_out, "unreachable: ReadTimeout"),
        (lambda r: httpx.Response(500, text="ValueError: No text provided"), "answered 500"),
        (lambda r: httpx.Response(200, content=b"not a wav"), "invalid audio"),
        (lambda r: httpx.Response(200, content=to_wav(PcmAudio(b"", 22_050))), "no audio"),
    ],
)
async def test_failures_become_speech_errors(
    handler: Callable[[httpx.Request], httpx.Response], message: str
) -> None:
    with pytest.raises(SpeechError, match=message):
        await adapter(handler).synthesize("Una frase.", VOICE)


async def test_status_finds_the_installed_voice() -> None:
    voices = {VOICE: {"audio": {"sample_rate": 22050}}, "it_IT-paola-medium": {}}
    tts = adapter(lambda r: httpx.Response(200, json=voices))
    assert (await tts.status(VOICE)).ready
    missing = await tts.status("en_US-missing-medium")
    assert missing.state == "failed"
    assert "not installed" in (missing.message or "")


async def test_an_unreachable_service_may_still_be_starting() -> None:
    status = await adapter(refused).status(VOICE)
    assert status.state == "starting"
    assert status.message == "the speech synthesis service is unreachable"
