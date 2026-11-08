"""The execution profile endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from probeloop.ai.fake import FakeChatModel
from probeloop.api.app import create_app
from probeloop.bootstrap import build
from probeloop.settings import Settings


def test_the_profile_is_local_by_default_and_cloud_is_offered_only_when_configured(
    tmp_path: Path,
) -> None:
    settings = Settings(data_dir=tmp_path, allowed_hosts=["testserver"])
    with TestClient(create_app(build(settings, model=FakeChatModel(["x"])))) as client:
        view = client.get("/api/settings/execution").json()
        assert view["profile"] == "local"
        assert [(p["id"], p["available"]) for p in view["profiles"]] == [
            ("local", True),
            ("cloud", False),
        ]
        assert view["profiles"][1]["models"] is None
        response = client.put("/api/settings/execution", json={"profile": "cloud"})
        assert response.status_code == 409
        assert response.json()["detail"] == "the cloud profile is not configured"


def test_a_configured_cloud_profile_lists_its_models_without_contacting_them(
    tmp_path: Path,
) -> None:
    settings = Settings(
        data_dir=tmp_path,
        allowed_hosts=["testserver"],
        cloud_api_key="sk-test-not-a-real-key",
        cloud_evaluation_model="gpt-eval",
    )
    model = FakeChatModel(["x"])
    container = build(settings, model=model, analysis_model=model, assessment_model=model)
    with TestClient(create_app(container)) as client:
        cloud = client.get("/api/settings/execution").json()["profiles"][1]
        assert cloud["available"] is True
        assert cloud["models"]["evaluation"] == "openai:gpt-eval"
        assert cloud["models"]["interviewer"] == "openai:gpt-6.1-terra"
        assert "sk-test" not in client.get("/api/settings/execution").text


def test_selecting_a_profile_persists_and_waits_for_idle_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(data_dir=tmp_path, llm_fake=True, allowed_hosts=["testserver"])
    container = build(settings)
    with TestClient(create_app(container)) as client:
        assert client.put("/api/settings/execution", content="cloud").status_code == 415
        assert client.put("/api/settings/execution", json={"profile": "x"}).status_code == 422
        monkeypatch.setattr(container.data, "_connected", lambda: True)
        busy = client.put("/api/settings/execution", json={"profile": "cloud"})
        assert busy.status_code == 409
        assert client.get("/api/settings/execution").json()["profile"] == "local"
        monkeypatch.undo()
        selected = client.put("/api/settings/execution", json={"profile": "cloud"})
        assert selected.status_code == 200
        assert selected.json()["profile"] == "cloud"
    assert build(settings).profiles.current == "cloud"
