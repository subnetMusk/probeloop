"""Voice sessions over the WebSocket, with fake speech engines and the energy detector."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from probeloop.ai.fake import FakeChatModel
from probeloop.api.app import create_app
from probeloop.bootstrap import build
from probeloop.interview.application.voice import VoiceServices
from probeloop.interview.domain.model import Language
from probeloop.settings import Settings
from probeloop.speech.audio import from_wav
from probeloop.speech.fake import EnergyVad, FakeSpeechToText, FakeTextToSpeech
from tests.conftest import move_json
from tests.speech_audio import frames, silence, tone

ORIGIN = "http://127.0.0.1:8000"
ANSWER = tone(1.0) + silence(0.8)


def make_client(tmp_path: Path, voice: VoiceServices | None) -> TestClient:
    settings = Settings(  # explicit URLs: `compose run` sets them in the environment
        data_dir=tmp_path, allowed_hosts=["testserver", "127.0.0.1"], stt_url=None, tts_url=None
    )
    model = FakeChatModel(
        [
            "{",  # warm-up request
            move_json("new_topic", "t1", "Buongiorno. Mi parli di lei?"),
            move_json("end", "t6", "Grazie, abbiamo finito."),
        ]
    )
    return TestClient(create_app(build(settings, model=model, voice=voice)))


def fake_voice() -> VoiceServices:
    return VoiceServices(
        stt=FakeSpeechToText(["Sono uno sviluppatore backend."]),
        tts=FakeTextToSpeech(),
        vad=EnergyVad,
        voices={Language.ITALIAN: "it_IT-test"},
    )


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with make_client(tmp_path, fake_voice()) as c:
        yield c


def create(client: TestClient, **overrides: Any) -> str:
    body = {"interview_type": "technical", "language": "it", "modality": "voice", **overrides}
    response = client.post("/api/sessions", json=body)
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def send(ws: Any, message_type: str, **fields: Any) -> None:
    ws.send_json({"type": message_type, "client_msg_id": uuid.uuid4().hex, **fields})


class Inbox:
    """Reads JSON messages and pairs each `tts.chunk` with the binary frame that follows it."""

    def __init__(self, ws: Any) -> None:
        self.ws = ws
        self.audio: list[tuple[dict[str, Any], bytes]] = []

    def until(self, message_type: str, **match: Any) -> dict[str, Any]:
        for _ in range(300):
            frame = self.ws.receive()
            assert "text" in frame, "binary frames only follow tts.chunk"
            message: dict[str, Any] = json.loads(frame["text"])
            if message["type"] == "tts.chunk":
                audio = self.ws.receive()
                assert "bytes" in audio
                self.audio.append((message, audio["bytes"]))
            if message["type"] == message_type and all(
                message.get(k) == v for k, v in match.items()
            ):
                return message
        raise AssertionError(f"no {message_type} {match}")


def test_a_voice_interview_over_the_websocket(client: TestClient, tmp_path: Path) -> None:
    session_id = create(client)
    with client.websocket_connect(f"/ws/sessions/{session_id}", headers={"origin": ORIGIN}) as ws:
        inbox = Inbox(ws)
        send(ws, "session.join", last_seq=0)
        send(ws, "session.start")
        done = inbox.until("tts.done")
        assert (done["turn_seq"], done["sentences"], done["failed"]) == (0, 2, 0)
        chunks = [meta for meta, _ in inbox.audio]
        assert [c["text"] for c in chunks] == ["Buongiorno.", "Mi parli di lei?"]
        for meta, pcm in inbox.audio:
            assert meta["sample_rate"] == 22_050
            assert len(pcm) == 2 * meta["samples"]
            assert meta["seq"] is None  # live only, never replayed

        send(ws, "playback.finished")
        inbox.until("state.changed", phase="awaiting_candidate")
        send(ws, "turn.start")
        inbox.until("state.changed", phase="candidate_speaking")
        for frame in frames(ANSWER, 0.1):
            ws.send_bytes(frame)
        partial = inbox.until("transcript.partial")
        assert partial == {
            "seq": partial["seq"],
            "type": "transcript.partial",
            "turn_seq": 1,
            "text": "Sono uno sviluppatore backend.",
        }
        send(ws, "turn.end")
        recorded = inbox.until("candidate.answer.recorded")
        assert recorded["text"] == "Sono uno sviluppatore backend."
        assert recorded["complete"] is True
        inbox.until("tts.done", turn_seq=2)
        send(ws, "playback.finished")
        assert inbox.until("session.ended")["reason"] == "completed"

    view = client.get(f"/api/sessions/{session_id}").json()
    assert view["modality"] == "voice"
    assert [t["text"] for t in view["turns"]][1] == "Sono uno sviluppatore backend."
    directory = tmp_path / "sessions" / session_id
    stored = from_wav((directory / "audio" / "answer-0001.wav").read_bytes())
    assert stored.data == ANSWER
    (metrics,) = (directory / "metrics.jsonl").read_text("utf-8").splitlines()
    assert json.loads(metrics)["answer_turn_seq"] == 1

    assert client.delete(f"/api/sessions/{session_id}").status_code == 204
    assert not directory.exists()


def test_bad_audio_frames_and_typed_answers_are_refused(client: TestClient) -> None:
    session_id = create(client)
    with client.websocket_connect(f"/ws/sessions/{session_id}") as ws:
        inbox = Inbox(ws)
        send(ws, "session.join")
        ws.send_bytes(b"\x00\x01\x02")
        assert inbox.until("error")["code"] == "invalid_audio_frame"
        ws.send_bytes(bytes(64 * 1024 + 2))
        assert inbox.until("error")["code"] == "invalid_audio_frame"
        ws.send_bytes(bytes(3200))  # well formed, but no answer is open: dropped silently
        send(ws, "session.start")
        inbox.until("tts.done")
        send(ws, "playback.finished")
        send(ws, "turn.start")
        send(ws, "turn.end", text="typed instead")
        error = inbox.until("error")
        assert error["code"] == "invalid_command"
        assert "spoken" in error["message"]


def test_voice_interviews_need_speech_services(tmp_path: Path) -> None:
    with make_client(tmp_path, None) as client:
        response = client.post(
            "/api/sessions",
            json={"interview_type": "technical", "modality": "voice"},
        )
        assert response.status_code == 422
        assert "speech services" in response.json()["detail"]
        status = client.get("/api/speech").json()
        assert status == {
            "ready": False,
            "problems": ["speech services not configured"],
            "voices": {},
        }
        assert create(client, modality="text")


def test_a_language_without_a_voice_is_refused(client: TestClient) -> None:
    response = client.post(
        "/api/sessions",
        json={"interview_type": "technical", "language": "en", "modality": "voice"},
    )
    assert response.status_code == 422
    assert "no voice" in response.json()["detail"]


def test_speech_status_reports_the_voices(client: TestClient) -> None:
    assert client.get("/api/speech").json() == {
        "ready": True,
        "problems": [],
        "voices": {"it": "it_IT-test", "en": None},
    }
