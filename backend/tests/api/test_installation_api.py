"""First-run defaults, legacy migration and installation mutation guards."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from probeloop.ai.fake import FakeChatModel
from probeloop.api.app import create_app
from probeloop.bootstrap import build
from probeloop.platform.jobs import Job, JobStatus, Progress
from probeloop.settings import Settings
from probeloop.workspace.installation import INSTALL_MODEL_JOB


def test_new_installation_prefers_cloud_and_disables_whisper(tmp_path: Path) -> None:
    container = build(
        Settings(
            data_dir=tmp_path,
            provisioner_url="http://127.0.0.1:1",
            ollama_base_url="http://127.0.0.1:1",
        ),
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


@pytest.mark.parametrize("reason", ["interview", "background_job", None])
def test_settings_explain_the_actual_lock_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reason: str | None
) -> None:
    container = build(Settings(data_dir=tmp_path, llm_fake=True))

    async def pending() -> bool:
        return reason == "background_job"

    monkeypatch.setattr(container.data, "_connected", lambda: reason == "interview")
    monkeypatch.setattr(container.data, "_pending", pending)
    with TestClient(create_app(container), base_url="http://localhost") as client:
        for endpoint in ("/api/installation", "/api/settings/execution"):
            view = client.get(endpoint).json()
            assert view["locked"] is (reason is not None)
            assert view["lock_reason"] == reason
        if reason is not None:
            refused = client.post("/api/installation/models/laya", json={})
            assert refused.status_code == 409
            assert refused.json()["detail"] == (
                "close the live interview first"
                if reason == "interview"
                else "wait for background jobs to finish first"
            )


def test_base_installation_leaves_laya_optional(tmp_path: Path) -> None:
    container = build(Settings(data_dir=tmp_path, llm_fake=True))
    with TestClient(create_app(container), base_url="http://localhost") as client:
        assert container.installation.config.limits_url  # Laya can still be installed alone
        jobs = client.post("/api/installation/base", json={}).json()
        assert [job["subject_id"] for job in jobs] == ["parakeet", "piper-it"]


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


@pytest.mark.parametrize("simulate_timeout", [False, True])
async def test_verified_download_survives_a_loading_speech_consumer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, simulate_timeout: bool
) -> None:
    container = build(Settings(data_dir=tmp_path, llm_fake=True, stt_url="http://speech"))
    events: list[str] = []

    async def verified(model: str, url: str, progress: Progress) -> None:
        events.append("verified")
        await progress(1.0, "Model installed and verified")

    async def reload_limits() -> None:
        events.append("limits")

    def loading(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/reload"
        events.append("speech")
        if simulate_timeout:
            raise httpx.ReadTimeout("synthetic model loading", request=request)
        return httpx.Response(503)

    real_client = httpx.AsyncClient

    def make_client(**kwargs: Any) -> httpx.AsyncClient:
        return real_client(transport=httpx.MockTransport(loading), **kwargs)

    monkeypatch.setattr(container.installation.installer, "install", verified)
    monkeypatch.setattr(container.limits, "reload", reload_limits)
    monkeypatch.setattr(httpx, "AsyncClient", make_client)

    async def progress(value: float, message: str | None) -> None:
        pass

    job = Job("synthetic-install", INSTALL_MODEL_JOB, "laya", JobStatus.RUNNING, 0)
    result = await container.installation.install(job, progress)
    assert result == {"model": "laya", "verified": True}
    assert events == ["verified", "limits", "speech"]
    await container.shutdown()
