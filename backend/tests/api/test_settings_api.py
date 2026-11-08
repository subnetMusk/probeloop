"""The execution profile and ChatGPT sign-in endpoints."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from probeloop.ai.fake import FakeChatGptAccount, FakeChatModel
from probeloop.api.app import create_app
from probeloop.bootstrap import build
from probeloop.logging_setup import RedactSignInCallback
from probeloop.settings import Settings

ORIGIN = {"Origin": "http://localhost:8000"}


def test_the_cloud_profile_needs_a_chatgpt_sign_in(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, allowed_hosts=["testserver"])
    model = FakeChatModel(["x"])
    container = build(settings, model=model, analysis_model=model, assessment_model=model)
    with TestClient(create_app(container)) as client:
        view = client.get("/api/settings/execution").json()
        assert view["profile"] == "local"
        assert view["chatgpt"] == {"signed_in": False, "email": None, "plan_usage": False}
        cloud = view["profiles"][1]
        assert cloud["models"]["interviewer"] == "chatgpt:gpt-6.1-terra"
        response = client.put("/api/settings/execution", json={"profile": "cloud"})
        assert response.status_code == 409
        assert response.json()["detail"] == "sign in with ChatGPT first"
        # Starting a sign-in returns OpenAI's authorization URL with a loopback redirect.
        start = client.post("/api/settings/chatgpt/sign-in", json={}, headers=ORIGIN)
        url = start.json()["url"]
        assert url.startswith("https://auth.openai.com/api/accounts/authorize?")
        assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A8000%2Fauth%2Fcallback" in url
        foreign = {"Origin": "http://evil.example"}
        assert (
            client.post("/api/settings/chatgpt/sign-in", json={}, headers=foreign).status_code
            == 403
        )


def test_signing_in_selecting_and_signing_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(data_dir=tmp_path, llm_fake=True, allowed_hosts=["testserver"])
    container = build(settings)
    assert isinstance(container.account, FakeChatGptAccount)
    container.account.signed_in = False
    with TestClient(create_app(container)) as client:
        url = client.post("/api/settings/chatgpt/sign-in", json={}, headers=ORIGIN).json()["url"]
        callback = client.get(url.replace("http://127.0.0.1:8000", ""), follow_redirects=False)
        assert callback.status_code == 303
        assert callback.headers["location"] == "http://localhost:8000/settings?chatgpt=connected"
        assert client.get("/api/settings/execution").json()["chatgpt"]["plan_usage"] is True

        assert client.put("/api/settings/execution", content="cloud").status_code == 415
        monkeypatch.setattr(container.data, "_connected", lambda: True)
        assert client.put("/api/settings/execution", json={"profile": "cloud"}).status_code == 409
        monkeypatch.undo()
        selected = client.put("/api/settings/execution", json={"profile": "cloud"})
        assert selected.json()["profile"] == "cloud"

        signed_out = client.post("/api/settings/chatgpt/sign-out", json={}).json()
        assert signed_out["profile"] == "local"
        assert signed_out["chatgpt"]["signed_in"] is False
    assert build(settings).profiles.current == "local"


def test_a_failed_callback_returns_to_settings_with_the_reason(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, allowed_hosts=["testserver"])
    model = FakeChatModel(["x"])
    container = build(settings, model=model, analysis_model=model, assessment_model=model)
    with TestClient(create_app(container)) as client:
        denied = client.get(
            "/auth/callback?error=access_denied&state=unknown", follow_redirects=False
        )
        assert denied.headers["location"] == "/settings?chatgpt=denied"
        expired = client.get("/auth/callback?code=c&state=unknown", follow_redirects=False)
        assert expired.headers["location"] == "/settings?chatgpt=expired"


def test_the_access_log_never_shows_the_authorization_code() -> None:
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        0,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:5000", "GET", "/auth/callback?code=secret&state=s", "1.1", 303),
        None,
    )
    RedactSignInCallback().filter(record)
    assert "secret" not in record.getMessage()
    assert "/auth/callback?[redacted]" in record.getMessage()
