from __future__ import annotations

import time
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
    settings = Settings(
        data_dir=tmp_path,
        allowed_hosts=["testserver", "127.0.0.1"],
        stt_url=None,  # no speech services, whatever the environment says
        tts_url=None,
    )
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


def test_the_history_lists_interviews_with_their_profile(client: TestClient) -> None:
    profile = client.post("/api/profiles", json={"name": "Ruoli backend", "resources": []})
    assert profile.status_code == 201, profile.text
    profile_id = profile.json()["id"]
    with_profile = create(client, profile_id=profile_id, difficulty="hard")
    without = create(client, interview_type="hr")

    summaries = client.get("/api/sessions").json()
    assert [s["id"] for s in summaries] == [without, with_profile]
    assert (summaries[1]["difficulty"], summaries[1]["target_duration_s"]) == ("hard", 600)
    assert (summaries[1]["answers"], summaries[1]["effective_s"]) == (0, None)

    history = client.get("/api/history/interviews").json()
    assert [(e["id"], e["interview_type"]) for e in history] == [
        (without, "hr"),
        (with_profile, "technical"),
    ]
    assert history[0]["profile"] is None
    assert history[1]["profile"] == {"id": profile_id, "name": "Ruoli backend"}
    assert history[1]["latest_report"] is None
    assert history[1]["execution_profile"] == "local"

    # A deleted profile stays referenced, without a name.
    assert client.delete(f"/api/profiles/{profile_id}").status_code == 204
    deleted = client.get("/api/history/interviews").json()[1]["profile"]
    assert deleted == {"id": profile_id, "name": None}


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


def finish_text_interview(client: TestClient) -> str:
    session_id = create(client)
    with client.websocket_connect(f"/ws/sessions/{session_id}") as ws:
        send(ws, "session.join")
        send(ws, "session.start")
        receive_until(ws, "state.changed", phase="interviewer_speaking")
        send(ws, "playback.finished")
        receive_until(ws, "state.changed", phase="awaiting_candidate")
        send(ws, "turn.start")
        send(ws, "turn.end", text="Uso fast api.")
        receive_until(ws, "state.changed", phase="interviewer_speaking")
        send(ws, "playback.finished")
        receive_until(ws, "session.ended")
    return session_id


def test_answers_are_corrected_as_new_revisions(client: TestClient, tmp_path: Path) -> None:
    session_id = finish_text_interview(client)
    response = client.put(f"/api/sessions/{session_id}/answers/1", json={"text": "Uso FastAPI."})
    assert response.status_code == 200, response.text
    answer = response.json()["turns"][1]
    assert answer["text"] == "Uso FastAPI."
    assert [(r["number"], r["source"]) for r in answer["revisions"]] == [
        (1, "stt"),
        (2, "user_edit"),
    ]
    exported = (tmp_path / "sessions" / session_id / "transcript.md").read_text("utf-8")
    assert "> Uso FastAPI." in exported

    assert (
        client.put(f"/api/sessions/{session_id}/answers/0", json={"text": "x"}).status_code == 422
    )
    assert client.put(f"/api/sessions/{'0' * 32}/answers/1", json={"text": "x"}).status_code == 404
    long_text = {"text": "x" * 8001}
    assert client.put(f"/api/sessions/{session_id}/answers/1", json=long_text).status_code == 422


def test_refinement_needs_a_recogniser(client: TestClient) -> None:
    session_id = finish_text_interview(client)
    assert client.post(f"/api/sessions/{session_id}/refine").status_code == 503
    assert client.get(f"/api/sessions/{session_id}/jobs").json() == []
    assert client.get(f"/api/jobs/{'0' * 32}").status_code == 404
    running = create(client)
    assert client.post(f"/api/sessions/{running}/refine").status_code == 409


def test_refinement_runs_as_a_polled_job(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, allowed_hosts=["testserver"], speech_fake=True)
    model = FakeChatModel(
        ["{", move_json("new_topic", "t1", "Mi parli di lei?"), move_json("end", "t6", "Grazie.")]
    )
    with TestClient(create_app(build(settings, model=model))) as client:
        session_id = finish_text_interview(client)
        job = client.post(f"/api/sessions/{session_id}/refine")
        assert job.status_code == 202
        for _ in range(100):
            polled = client.get(f"/api/jobs/{job.json()['id']}").json()
            if polled["status"] in ("succeeded", "failed"):
                break
            time.sleep(0.02)
        assert polled["status"] == "succeeded", polled
        assert polled["result"] == {"revised": 0, "skipped": 1, "vocabulary": False}
        jobs = client.get(f"/api/sessions/{session_id}/jobs").json()
        assert [j["kind"] for j in jobs] == ["refine_transcript"]


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
    # The server pauses the session when it notices the disconnection, in the background.
    for _ in range(100):
        if client.get(f"/api/sessions/{session_id}").json()["status"] == "paused":
            break
        time.sleep(0.02)
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
