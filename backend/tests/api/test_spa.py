"""The backend serves the built frontend at runtime."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from probeloop.ai.fake import FakeChatModel
from probeloop.api.app import create_app
from probeloop.bootstrap import build
from probeloop.settings import Settings

INDEX = "<!doctype html><title>ProbeLoop</title><div id=root></div>"


def client(tmp_path: Path, static_dir: Path | None) -> TestClient:
    settings = Settings(
        data_dir=tmp_path / "data",
        static_dir=static_dir,
        stt_url=None,
        tts_url=None,
        allowed_hosts=["testserver"],
    )
    return TestClient(create_app(build(settings, model=FakeChatModel(["{}"]))))


def built_frontend(tmp_path: Path) -> Path:
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text(INDEX, encoding="utf-8")
    (static / "assets" / "index-abc.js").write_text("console.log(1)", encoding="utf-8")
    return static


def test_client_routes_get_the_index_and_assets_are_served(tmp_path: Path) -> None:
    with client(tmp_path, built_frontend(tmp_path)) as c:
        for path in ("/", "/interview/0123"):
            response = c.get(path)
            assert response.status_code == 200
            assert response.text == INDEX
            assert response.headers["cache-control"] == "no-cache"
        assert c.get("/assets/index-abc.js").text == "console.log(1)"


def test_api_paths_never_fall_back_to_the_index(tmp_path: Path) -> None:
    with client(tmp_path, built_frontend(tmp_path)) as c:
        for path in ("/api/unknown", "/ws/whatever", "/assets/missing.js", "/health/x"):
            response = c.get(path)
            assert response.status_code == 404, path
            assert "ProbeLoop" not in response.text
        assert c.get("/health").json() == {"status": "ok"}
        assert c.get("/api/speech").status_code == 200


def test_without_a_build_only_the_api_is_served(tmp_path: Path) -> None:
    with client(tmp_path, None) as c:
        assert c.get("/").status_code == 404
    with client(tmp_path, tmp_path / "missing") as c:
        assert c.get("/").status_code == 404
