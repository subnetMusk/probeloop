"""HttpSpeechToText against a mocked transport: request shape and error mapping."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from probeloop.speech.audio import PcmAudio
from probeloop.speech.http_stt import HttpSpeechToText
from probeloop.speech.ports import SpeechError, TranscribeOptions
from probeloop.speech.wire import Engine
from tests.speech_audio import tone

BODY = {
    "engine_ref": "onnx-asr/nemo-parakeet-tdt-0.6b-v3/int8",
    "language": "it",
    "processing_s": 0.31,
    "segments": [{"start_s": 0.0, "end_s": 1.0, "text": "Buongiorno.", "words": []}],
}


def adapter(
    handler: Callable[[httpx.Request], httpx.Response], engine: Engine = "live"
) -> HttpSpeechToText:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://stt")
    return HttpSpeechToText("http://stt", engine=engine, client=client)


def refused(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused", request=request)


def timed_out(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("no answer", request=request)


async def test_sends_raw_pcm_and_the_options_as_query_parameters() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=BODY)

    stt = adapter(handler, engine="refine")
    assert stt.engine_ref == "stt-worker/refine"
    audio = PcmAudio(tone(1.0))
    options = TranscribeOptions("it", initial_prompt="Già, PostgreSQL", word_timestamps=True)
    result = await stt.transcribe(audio, options)

    (request,) = seen
    assert request.method == "POST"
    assert request.url.path == "/transcribe"
    assert dict(request.url.params) == {
        "engine": "refine",
        "language": "it",
        "word_timestamps": "true",
        "sample_rate": "16000",
        "initial_prompt": "Già, PostgreSQL",
    }
    assert request.headers["content-type"] == "application/octet-stream"
    assert request.content == audio.data
    assert result.text == "Buongiorno."
    assert result.engine_ref == stt.engine_ref == BODY["engine_ref"]


async def test_no_prompt_parameter_without_a_prompt() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=BODY)

    await adapter(handler).transcribe(PcmAudio(tone(0.2)), TranscribeOptions("it"))
    assert "initial_prompt" not in seen[0].url.params
    assert seen[0].url.params["engine"] == "live"


@pytest.mark.parametrize(
    ("handler", "message"),
    [
        (refused, "unreachable: ConnectError"),
        (timed_out, "unreachable: ReadTimeout"),
        (lambda r: httpx.Response(503, json={"detail": "speech recognition failed"}), "503"),
        (lambda r: httpx.Response(200, content=b"not json"), "invalid response"),
        (lambda r: httpx.Response(200, json={"segments": "nope"}), "invalid response"),
    ],
)
async def test_failures_become_speech_errors(
    handler: Callable[[httpx.Request], httpx.Response], message: str
) -> None:
    with pytest.raises(SpeechError, match=message):
        await adapter(handler).transcribe(PcmAudio(tone(0.2)), TranscribeOptions("it"))


async def test_other_sample_rates_are_refused_before_sending() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    with pytest.raises(SpeechError, match="16 kHz"):
        await adapter(handler).transcribe(PcmAudio(tone(0.2), 22_050), TranscribeOptions("it"))
