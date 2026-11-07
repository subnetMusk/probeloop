from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from probeloop.ai.fake import FakeChatModel
from probeloop.api.app import WS_SESSION_BUSY, create_app
from probeloop.bootstrap import build
from probeloop.settings import Settings
from tests.conftest import move_json

ORIGIN = "http://127.0.0.1:8000"


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(data_dir=tmp_path, allowed_hosts=["testserver", "127.0.0.1"])
    model = FakeChatModel(
        [
            "{",  # warm-up request
            move_json("new_topic", "t1", "Buongiorno. Mi parli di lei?"),
            move_json("end", "t6", "Grazie, abbiamo finito."),
        ]
    )
    with TestClient(create_app(build(settings, model=model))) as test_client:
        yield test_client


def create(client: TestClient, **overrides: Any) -> str:
    body = {"interview_type": "technical", "language": "it", "duration_minutes": 10, **overrides}
    response = client.post("/api/sessions", json=body)
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def send(ws: Any, message_type: str, **fields: Any) -> None:
    ws.send_json({"type": message_type, "client_msg_id": uuid.uuid4().hex, **fields})


def receive_until(ws: Any, message_type: str, **match: Any) -> dict[str, Any]:
    for _ in range(200):
        message: dict[str, Any] = ws.receive_json()
        if message["type"] == message_type and all(message.get(k) == v for k, v in match.items()):
            return message
    raise AssertionError(f"no {message_type} {match}")


def test_health_and_trusted_hosts(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/health", headers={"host": "evil.example"}).status_code == 400


def test_session_crud(client: TestClient) -> None:
    session_id = create(client)
    view = client.get(f"/api/sessions/{session_id}").json()
    assert view["status"] == "ready"
    assert view["target_duration_s"] == 600
    assert [t["id"] for t in view["topics"]][:2] == ["t1", "t2"]
    assert [s["id"] for s in client.get("/api/sessions").json()] == [session_id]
    assert client.delete(f"/api/sessions/{session_id}").status_code == 204
    assert client.get(f"/api/sessions/{session_id}").status_code == 404
    assert client.delete(f"/api/sessions/{session_id}").status_code == 404


def test_create_validates_input(client: TestClient) -> None:
    assert client.post("/api/sessions", json={"interview_type": "nope"}).status_code == 422
    assert (
        client.post(
            "/api/sessions", json={"interview_type": "hr", "duration_minutes": 1}
        ).status_code
        == 422
    )
    assert (
        client.post("/api/sessions", json={"interview_type": "hr", "extra": 1}).status_code == 422
    )
    response = client.post(
        "/api/sessions", content=b'{"interview_type": "hr"}', headers={"content-type": "text/plain"}
    )
    assert response.status_code == 415


def test_text_interview_over_websocket(client: TestClient) -> None:
    session_id = create(client)
    with client.websocket_connect(f"/ws/sessions/{session_id}", headers={"origin": ORIGIN}) as ws:
        send(ws, "session.join", last_seq=0)
        assert receive_until(ws, "state.changed")["status"] == "ready"
        send(ws, "session.start")
        completed = receive_until(ws, "interviewer.move.completed")
        assert completed["utterance"] == "Buongiorno. Mi parli di lei?"
        receive_until(ws, "state.changed", phase="interviewer_speaking")
        send(ws, "playback.finished")
        receive_until(ws, "state.changed", phase="awaiting_candidate")
        send(ws, "turn.start")
        send(ws, "turn.end", text="Sono uno sviluppatore backend.")
        recorded = receive_until(ws, "candidate.answer.recorded")
        assert recorded["text"] == "Sono uno sviluppatore backend."
        receive_until(ws, "interviewer.move.completed", utterance="Grazie, abbiamo finito.")
        receive_until(ws, "state.changed", phase="interviewer_speaking")
        send(ws, "playback.finished")
        ended = receive_until(ws, "session.ended")
        assert ended["reason"] == "completed"

    view = client.get(f"/api/sessions/{session_id}").json()
    assert view["status"] == "ended"
    assert [t["speaker"] for t in view["turns"]] == ["interviewer", "candidate", "interviewer"]


def test_invalid_commands_are_reported(client: TestClient) -> None:
    session_id = create(client)
    with client.websocket_connect(f"/ws/sessions/{session_id}") as ws:
        send(ws, "session.join")
        send(ws, "playback.finished")
        assert receive_until(ws, "error")["code"] == "invalid_command"
        ws.send_json({"type": "bogus"})
        assert receive_until(ws, "error")["code"] == "invalid_message"
        send(ws, "ping")
        receive_until(ws, "pong")


def test_duplicate_client_messages_run_once(client: TestClient) -> None:
    session_id = create(client)
    with client.websocket_connect(f"/ws/sessions/{session_id}") as ws:
        send(ws, "session.join")
        ws.send_json({"type": "session.start", "client_msg_id": "same"})
        ws.send_json({"type": "session.start", "client_msg_id": "same"})
        send(ws, "ping")
        messages = []
        while (m := ws.receive_json())["type"] != "pong":
            messages.append(m)
        assert not [m for m in messages if m["type"] == "error"]


def test_disconnect_pauses_and_reconnect_replays(client: TestClient) -> None:
    session_id = create(client)
    with client.websocket_connect(f"/ws/sessions/{session_id}") as ws:
        send(ws, "session.join")
        send(ws, "session.start")
        last = receive_until(ws, "interviewer.move.completed")["seq"]
    assert client.get(f"/api/sessions/{session_id}").json()["status"] == "paused"

    with client.websocket_connect(f"/ws/sessions/{session_id}") as ws:
        send(ws, "session.join", last_seq=last)
        # The pause is stored in a thread: when the client returns that quickly, its numbered
        # event comes from the replay or, just after the unnumbered snapshot, live.
        for _ in range(20):
            message = receive_until(ws, "state.changed", status="paused")
            if message["seq"] is not None:
                break
        assert message["seq"] > last
        send(ws, "session.resume")
        receive_until(ws, "state.changed", status="in_progress")


def test_second_client_is_rejected(client: TestClient) -> None:
    session_id = create(client)
    with client.websocket_connect(f"/ws/sessions/{session_id}") as first:
        send(first, "session.join")
        receive_until(first, "state.changed")
        with client.websocket_connect(f"/ws/sessions/{session_id}") as second:
            send(second, "session.join")
            with pytest.raises(WebSocketDisconnect) as exc:
                second.receive_json()
            assert exc.value.code == WS_SESSION_BUSY


def test_foreign_origin_is_rejected(client: TestClient) -> None:
    session_id = create(client)
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect(
            f"/ws/sessions/{session_id}", headers={"origin": "https://evil.example"}
        ) as ws,
    ):
        ws.receive_json()


def test_unknown_session_closes_the_socket(client: TestClient) -> None:
    with client.websocket_connect(f"/ws/sessions/{'f' * 32}") as ws:
        send(ws, "session.join")
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
