"""First-run defaults, legacy migration and installation mutation guards."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from probeloop.ai.fake import FakeChatModel
from probeloop.api.app import create_app
from probeloop.bootstrap import build
from probeloop.settings import Settings


def test_new_installation_prefers_cloud_and_disables_whisper(tmp_path: Path) -> None:
    container = build(
        Settings(
            data_dir=tmp_path,
            provisioner_url="http://127.0.0.1:1",
            ollama_base_url="http://127.0.0.1:1",
        ),
        model=FakeChatModel([]),
    )
    assert container.installation.config.refinement is False
    assert container.profiles.current == "cloud"
    with TestClient(create_app(container), base_url="http://localhost") as client:
        status = client.get("/api/installation").json()
        assert status["managed"] is True
        assert status["config"]["completed"] is False
        assert status["provisioning"]["available"] is False
        choices = client.get("/api/settings/execution").json()["tools"]
        assert all(not role["options"][0]["available"] for role in choices)
        assert client.post("/api/installation/complete", json={}).status_code == 409
        assert client.post("/api/installation/models/arbitrary", json={}).status_code == 404
    restarted = build(
        Settings(data_dir=tmp_path, provisioner_url="http://127.0.0.1:1"), model=FakeChatModel([])
    )
    assert restarted.profiles.current == "cloud"
    assert restarted.installation.config.refinement is False


def test_existing_installation_preserves_refinement_and_selection(tmp_path: Path) -> None:
    (tmp_path / "execution-profile.json").write_text(json.dumps({"profile": "local"}))
    container = build(
        Settings(data_dir=tmp_path, provisioner_url="http://127.0.0.1:1"), model=FakeChatModel([])
    )
    assert container.installation.config.completed
    assert container.installation.config.refinement
    assert container.profiles.current == "local"


def test_installation_changes_are_locked_while_interview_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    container = build(Settings(data_dir=tmp_path, llm_fake=True))
    with TestClient(create_app(container), base_url="http://localhost") as client:
        monkeypatch.setattr(container.data, "_connected", lambda: True)
        assert client.get("/api/installation").json()["locked"]
        for route in (
            "/api/installation/base",
            "/api/installation/models/laya",
            "/api/installation/ollama/analysis",
            "/api/installation/complete",
        ):
            assert client.post(route, json={}).status_code == 409
        assert (
            client.put(
                "/api/installation",
                json={
                    "refinement": False,
                    "ollama_url": "http://host.docker.internal:11434",
                    "limits_url": "",
                },
            ).status_code
            == 409
        )


def test_configuration_is_persisted_but_does_not_complete_setup(tmp_path: Path) -> None:
    container = build(Settings(data_dir=tmp_path, llm_fake=True))
    with TestClient(create_app(container), base_url="http://localhost") as client:
        body = {
            "refinement": False,
            "ollama_url": "http://host.docker.internal:11434",
            "limits_url": "https://huggingface.co/example/model/resolve/immutable",
        }
        assert client.put("/api/installation", json=body).status_code == 200
        assert client.post("/api/installation/models/whisper", json={}).status_code == 409
        assert client.post("/api/installation/base", content="not json").status_code == 415
    assert build(Settings(data_dir=tmp_path, llm_fake=True)).installation.config.refinement is False
