"""The stt-worker's HTTP API, with fake engines."""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field

import httpx
import pytest
from fastapi.testclient import TestClient

from probeloop.speech import worker
from probeloop.speech.audio import PcmAudio
from probeloop.speech.fake import FakeSpeechToText
from probeloop.speech.ports import (
    RecognizedSegment,
    RecognizedWord,
    SpeechError,
    TranscribeOptions,
    Transcription,
)
from probeloop.speech.wire import TranscriptionBody
from probeloop.speech.worker import create_worker_app
from tests.speech_audio import tone

PCM = {"Content-Type": "application/octet-stream"}


@dataclass
class GatedEngine:
    """Blocks every call until the gate opens, then fails or answers."""

    gate: threading.Event = field(default_factory=threading.Event)
    fail: bool = False

    @property
    def engine_ref(self) -> str:
        return "test:gated"

    async def transcribe(self, audio: PcmAudio, options: TranscribeOptions) -> Transcription:
        while not self.gate.is_set():  # noqa: ASYNC110 - the test thread opens the gate
            await asyncio.sleep(0.005)
        if self.fail:
            raise SpeechError("model files missing")
        return Transcription((), options.language, self.engine_ref)


@dataclass
class ConcurrencyProbe:
    active: int = 0
    peak: int = 0

    @property
    def engine_ref(self) -> str:
        return "test:probe"

    async def transcribe(self, audio: PcmAudio, options: TranscribeOptions) -> Transcription:
        self.active += 1
        self.peak = max(self.peak, self.active)
        await asyncio.sleep(0.02)
        self.active -= 1
        return Transcription((), options.language, self.engine_ref)


@pytest.fixture
def fake() -> FakeSpeechToText:
    return FakeSpeechToText(["Ho usato PostgreSQL."])


@pytest.fixture
def client(fake: FakeSpeechToText) -> Iterator[TestClient]:
    with TestClient(create_worker_app({"live": fake, "refine": FakeSpeechToText()})) as c:
        yield c


def wait_for_status(client: TestClient, status: str) -> httpx.Response:
    for _ in range(200):
        response = client.get("/health")
        if response.json()["status"] == status:
            return response
        time.sleep(0.01)
    raise AssertionError(f"health never became {status}")


def test_health_lists_the_engines(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "engines": {"live": "fake:stt", "refine": "fake:stt"},
    }


def test_transcribe_returns_segments_and_passes_the_options(
    client: TestClient, fake: FakeSpeechToText
) -> None:
    audio = tone(1.0)
    response = client.post(
        "/transcribe",
        params={"language": "it", "initial_prompt": "PostgreSQL, Redis", "word_timestamps": True},
        content=audio,
        headers=PCM,
    )
    assert response.status_code == 200, response.text
    body = TranscriptionBody.model_validate_json(response.content)
    assert body.engine_ref == "fake:stt"
    assert [s.text for s in body.segments] == ["Ho usato PostgreSQL."]
    assert [w.text for w in body.segments[0].words] == ["Ho", "usato", "PostgreSQL."]
    assert body.processing_s >= 0
    sent_audio, options = fake.calls[0]
    assert sent_audio.data == audio
    assert options == TranscribeOptions("it", "PostgreSQL, Redis", word_timestamps=True)


@pytest.mark.parametrize(
    ("params", "body", "headers", "status"),
    [
        ({"language": "it"}, b"\x00\x00", {"Content-Type": "audio/wav"}, 415),
        ({"language": "it"}, b"\x00\x00\x00", PCM, 400),
        ({"language": "italiano"}, b"\x00\x00", PCM, 422),
        ({}, b"\x00\x00", PCM, 422),
        ({"language": "it", "engine": "turbo"}, b"\x00\x00", PCM, 422),
        ({"language": "it", "sample_rate": 8000}, b"\x00\x00", PCM, 422),
        ({"language": "it", "initial_prompt": "x" * 1001}, b"\x00\x00", PCM, 422),
    ],
)
def test_invalid_requests_are_rejected(
    client: TestClient,
    params: dict[str, object],
    body: bytes,
    headers: dict[str, str],
    status: int,
) -> None:
    response = client.post("/transcribe", params=params, content=body, headers=headers)
    assert response.status_code == status


def test_audio_longer_than_the_limit_is_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker, "MAX_BODY_BYTES", 1000)
    response = client.post(
        "/transcribe", params={"language": "it"}, content=bytes(1002), headers=PCM
    )
    assert response.status_code == 413


def test_an_engine_that_is_not_configured_is_not_found() -> None:
    with TestClient(create_worker_app({"live": FakeSpeechToText()})) as client:
        response = client.post(
            "/transcribe", params={"language": "it", "engine": "refine"}, content=b"", headers=PCM
        )
    assert response.status_code == 404


def test_engine_errors_become_503_without_details() -> None:
    engine = FakeSpeechToText([SpeechError("onnxruntime: out of memory at /models/x")])
    with TestClient(create_worker_app({"live": engine})) as client:
        response = client.post(
            "/transcribe", params={"language": "it"}, content=tone(0.5), headers=PCM
        )
    assert response.status_code == 503
    assert response.json() == {"detail": "speech recognition failed"}


def test_the_worker_is_not_healthy_until_preloaded_engines_are_ready() -> None:
    engine = GatedEngine()
    with TestClient(create_worker_app({"live": engine}, preload=["live"])) as client:
        assert client.get("/health").status_code == 503
        assert client.get("/health").json()["status"] == "loading"
        response = client.post("/transcribe", params={"language": "it"}, content=b"", headers=PCM)
        assert response.status_code == 503
        engine.gate.set()
        assert wait_for_status(client, "ready").status_code == 200


def test_a_preload_failure_is_reported_on_health() -> None:
    engine = GatedEngine(fail=True)
    engine.gate.set()
    with TestClient(create_worker_app({"live": engine}, preload=["live"])) as client:
        assert wait_for_status(client, "failed").status_code == 503


async def test_requests_are_processed_one_at_a_time() -> None:
    probe = ConcurrencyProbe()
    app = create_worker_app({"live": probe})
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://stt-worker") as client:
        responses = await asyncio.gather(
            *(
                client.post(
                    "/transcribe", params={"language": "it"}, content=tone(0.2), headers=PCM
                )
                for _ in range(4)
            )
        )
    assert [r.status_code for r in responses] == [200] * 4
    assert probe.peak == 1


def test_wire_format_round_trip() -> None:
    transcription = Transcription(
        segments=(
            RecognizedSegment(
                0.5,
                2.0,
                "Sì, certo.",
                avg_logprob=-0.12,
                words=(RecognizedWord(0.5, 1.0, "Sì,", 0.9), RecognizedWord(1.0, 2.0, "certo.")),
            ),
        ),
        language="it",
        engine_ref="onnx-asr/nemo-parakeet-tdt-0.6b-v3/int8",
    )
    body = TranscriptionBody.of(transcription, processing_s=0.4)
    restored = TranscriptionBody.model_validate_json(body.model_dump_json()).to_transcription()
    assert restored == transcription
