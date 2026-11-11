"""The execution profile and ChatGPT sign-in endpoints."""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from probeloop.ai.fake import FakeChatGptAccount, FakeChatModel
from probeloop.api.app import create_app
from probeloop.bootstrap import build
from probeloop.interview.infrastructure.jev_limits import JevKeyFile, JevStatedLimitReader
from probeloop.logging_setup import RedactSignInCallback
from probeloop.settings import Settings
from probeloop.storage.data import OWNED_DIRS
from probeloop.workspace.execution import ToolOption, execution_tools
from tests.assessment.support import synthetic_session

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
        # An open interview locks tool choices and sign-out until it is closed.
        monkeypatch.setattr(container.data, "_connected", lambda: True)
        assert client.get("/api/settings/execution").json()["locked"] is True
        selected = client.put("/api/settings/execution", json={"profile": "cloud"})
        assert selected.status_code == 409
        assert client.post("/api/settings/chatgpt/sign-out", json={}).status_code == 409
        monkeypatch.undo()

        assert client.put("/api/settings/execution", json={"profile": "cloud"}).status_code == 200

        signed_out = client.post("/api/settings/chatgpt/sign-out", json={}).json()
        assert signed_out["profile"] == "local"
        assert signed_out["chatgpt"]["signed_in"] is False
    assert build(settings).profiles.current == "local"


def test_answer_reconstruction_is_a_setting_that_needs_the_cloud_interviewer(
    tmp_path: Path,
) -> None:
    settings = Settings(data_dir=tmp_path, llm_fake=True, allowed_hosts=["testserver"])
    with TestClient(create_app(build(settings))) as client:
        view = client.get("/api/settings/execution").json()
        assert view["answer_reconstruction"] == {"enabled": False, "applies": False}
        refused = client.put("/api/settings/execution", json={})
        assert refused.status_code == 422
        enabled = client.put("/api/settings/execution", json={"answer_reconstruction": True})
        assert enabled.status_code == 200
        # Saved, but a local interviewer does not write readings.
        assert enabled.json()["answer_reconstruction"] == {"enabled": True, "applies": False}
        tools = {"interviewer": "cloud"}
        cloud = client.put("/api/settings/execution", json={"tools": tools}).json()
        assert cloud["answer_reconstruction"] == {"enabled": True, "applies": True}
    assert build(settings).profiles.answer_reconstruction is True


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


def test_new_work_records_its_execution_profile(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, llm_fake=True, allowed_hosts=["testserver"])
    container = build(settings)
    with TestClient(create_app(container)) as client:
        body = {"interview_type": "technical", "execution_profile": "cloud", "profile_id": "p1"}
        session = client.post("/api/sessions", json=body).json()
        assert (session["execution_profile"], session["profile_id"]) == ("cloud", "p1")
        default = client.post("/api/sessions", json={"interview_type": "hr"}).json()
        assert default["execution_profile"] == "local"  # the default at creation time
        summaries = {s["id"]: s for s in client.get("/api/sessions").json()}
        assert summaries[session["id"]]["execution_profile"] == "cloud"

        cv = client.post(
            "/api/documents/text", json={"kind": "cv", "title": "CV", "text": "Synthetic CV."}
        ).json()["id"]
        prepared = client.post(
            "/api/preparations",
            json={"job_mode": "none", "cv_id": cv, "execution_profile": "cloud"},
        ).json()
        assert prepared["execution_profile"] == "cloud"
        (analysis,) = client.portal.call(container.jobs.for_subject, prepared["id"])
        assert analysis.payload == {"execution": "cloud"}

        # The reports of an interview use the interview's profile, whatever the default.
        ended = synthetic_session()
        ended.execution_profile = "cloud"
        client.portal.call(container.store.save, ended)
        report = client.post(f"/api/sessions/{ended.id}/reports", json={"language": "it"})
        assert report.status_code == 202
        (review,) = client.portal.call(container.jobs.for_subject, ended.id)
        assert review.payload["execution"] == "cloud"


def test_cloud_work_needs_a_chatgpt_sign_in(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, allowed_hosts=["testserver"])
    model = FakeChatModel(["x"])
    container = build(settings, model=model, analysis_model=model, assessment_model=model)
    with TestClient(create_app(container)) as client:
        body = {"interview_type": "technical", "execution_profile": "cloud"}
        refused = client.post("/api/sessions", json=body)
        assert (refused.status_code, refused.json()["detail"]) == (
            409,
            "sign in with ChatGPT first",
        )


def test_per_role_choices_are_checked_and_frozen_with_new_work(tmp_path: Path) -> None:
    # An empty model directory, independent of any classifier installed on this machine.
    settings = Settings(
        data_dir=tmp_path,
        llm_fake=True,
        allowed_hosts=["testserver"],
        limits_model_dir=tmp_path / "models",
    )
    container = build(settings)
    with TestClient(create_app(container)) as client:
        roles = {r["id"]: r for r in client.get("/api/settings/execution").json()["tools"]}
        assert set(roles) == {"interviewer", "analysis", "evaluation", "limits"}
        assert [o["id"] for o in roles["analysis"]["options"]] == ["local", "cloud"]
        assert [o["id"] for o in roles["limits"]["options"]] == ["local", "cloud", "laya", "jev"]
        laya = next(o for o in roles["limits"]["options"] if o["id"] == "laya")
        assert not laya["available"]
        assert laya["reason"] == "model_missing"
        for change, status in [({"limits": "laya"}, 409), ({"interviewer": "laya"}, 422)]:
            assert (
                client.put("/api/settings/execution", json={"tools": change}).status_code == status
            )
        selected = client.put("/api/settings/execution", json={"tools": {"analysis": "cloud"}})
        assert selected.status_code == 200
        frozen = selected.json()["profile"]
        assert execution_tools(frozen) == {
            "interviewer": "local",
            "analysis": "cloud",
            "evaluation": "local",
            "limits": "local",
        }
        session = client.post("/api/sessions", json={"interview_type": "hr"}).json()
        assert session["execution_profile"] == frozen
        client.put("/api/settings/execution", json={"tools": {"analysis": "local"}})
        assert client.get(f"/api/sessions/{session['id']}").json()["execution_profile"] == frozen
        assert client.post("/api/sessions", json={"execution_profile": "{bad"}).status_code == 422


def test_jev_is_optional_and_needs_a_verified_key(tmp_path: Path) -> None:
    accepted = "synthetic-jev-key"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.typesafe.ai" and request.url.path == "/v1/models":
            ok = request.headers.get("authorization") == f"Bearer {accepted}"
            return httpx.Response(200 if ok else 401, json={"models": []})
        raise httpx.ConnectError("offline", request=request)

    settings = Settings(data_dir=tmp_path, llm_fake=True, allowed_hosts=["testserver"])
    keys = JevKeyFile(tmp_path / "typesafe")
    jev = JevStatedLimitReader(keys, transport=httpx.MockTransport(handler))
    container = build(settings, jev=jev)
    with TestClient(create_app(container)) as client:
        view = client.get("/api/settings/execution").json()
        assert view["jev"] == {"configured": False}
        limits = next(r for r in view["tools"] if r["id"] == "limits")
        option = next(o for o in limits["options"] if o["id"] == "jev")
        assert (option["available"], option["reason"]) == (False, "key_missing")
        assert option["model_ref"] == "typesafe:jev-1.14.0:limits.v2:threshold=0.5"
        refused = client.put("/api/settings/execution", json={"tools": {"limits": "jev"}})
        assert refused.status_code == 409
        elsewhere = client.put("/api/settings/execution", json={"tools": {"analysis": "jev"}})
        assert elsewhere.status_code == 422

        rejected = client.put("/api/settings/jev/key", json={"key": "wrong-key"})
        assert (rejected.status_code, rejected.json()["detail"]) == (
            422,
            "the Jev API key was rejected; check it in Settings",
        )
        assert "wrong-key" not in rejected.text
        spaced = client.put("/api/settings/jev/key", json={"key": "two words"})
        assert spaced.status_code == 422
        assert "two words" not in spaced.text
        assert not keys.configured

        saved = client.put("/api/settings/jev/key", json={"key": f"  {accepted}\n"})
        assert saved.status_code == 200
        assert accepted not in saved.text
        assert saved.json()["jev"] == {"configured": True}
        assert keys.read() == accepted
        selected = client.put("/api/settings/execution", json={"tools": {"limits": "jev"}})
        assert selected.status_code == 200
        assert execution_tools(selected.json()["profile"])["limits"] == "jev"

        # The key is machine configuration, never part of a portable backup or data deletion.
        assert "typesafe" not in OWNED_DIRS

        # A session frozen with this plan reads its limits with Jev, whatever the later default.
        session = synthetic_session()
        session.execution_profile = selected.json()["profile"]
        interviewer = container.sessions._interviewer_for(session)
        assert interviewer._limit_reader is jev  # type: ignore[attr-defined]

        removed = client.post("/api/settings/jev/remove", json={})
        assert removed.json()["jev"] == {"configured": False}
        assert execution_tools(removed.json()["profile"])["limits"] == "local"
        assert not (tmp_path / "typesafe" / "api-key").exists()


def test_an_uninstalled_local_model_cannot_be_selected(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, llm_fake=True, allowed_hosts=["testserver"])
    container = build(settings)
    original = container.tool_options

    async def unavailable():
        options = dict(await original())
        options["analysis"] = (
            ToolOption("local", False, "ollama:missing", "model_missing"),
            options["analysis"][1],
        )
        return options

    object.__setattr__(container, "tool_options", unavailable)
    with TestClient(create_app(container)) as client:
        assert (
            client.put("/api/settings/execution", json={"tools": {"analysis": "cloud"}}).status_code
            == 200
        )
        refused = client.put("/api/settings/execution", json={"tools": {"analysis": "local"}})
        assert refused.status_code == 409
        assert "model_missing" in refused.json()["detail"]
