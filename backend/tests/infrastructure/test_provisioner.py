"""The installer preserves valid files and never activates incomplete or unverified weights."""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from probeloop.workspace.infrastructure.provisioner import (
    Provisioner,
    checksum,
    create_provisioner_app,
    validate_download_url,
)
from probeloop.workspace.infrastructure.provisioning import HttpModelInstaller, OllamaModelManager
from probeloop.workspace.installation import ProvisioningError

DATA = (Path(__file__).parents[1] / "fixtures/synthetic/installation/model.txt").read_bytes()


def manifest() -> dict[str, Any]:
    return {
        "version": 1,
        "models": [
            {
                "id": "synthetic",
                "title": "Synthetic",
                "license": "Apache-2.0",
                "source": "https://models.example.test",
                "reference": None,
                "files": [
                    {
                        "path": "synthetic/model.txt",
                        "url": "https://models.example.test/model.txt",
                        "size": len(DATA),
                        "sha256": hashlib.sha256(DATA).hexdigest(),
                    }
                ],
            }
        ],
    }


async def consume(worker: Provisioner) -> list[dict[str, Any]]:
    return [item async for item in worker.install("synthetic", "")]


def test_checksum_reports_bytes_without_changing_the_digest(tmp_path: Path) -> None:
    content = DATA * (2 * 1024 * 1024 // len(DATA) + 1)
    path = tmp_path / "model.txt"
    path.write_bytes(content)
    checked: list[int] = []
    assert checksum(path, checked.append) == hashlib.sha256(content).hexdigest()
    assert len(checked) > 1
    assert checked == sorted(checked)
    assert checked[-1] == len(content)


async def test_existing_weights_report_progress_before_verification_finishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "synthetic/model.txt"
    path.parent.mkdir()
    path.write_bytes(DATA)
    original_mtime = path.stat().st_mtime_ns
    halfway = threading.Event()
    release = threading.Event()

    def slow_checksum(path: Path, progress: Callable[[int], None] | None = None) -> str:
        assert progress is not None
        progress(len(DATA) // 2)
        halfway.set()
        assert release.wait(timeout=10)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def unexpected_download(request: httpx.Request) -> httpx.Response:
        pytest.fail("valid installed weights must not be downloaded again")

    monkeypatch.setattr("probeloop.workspace.infrastructure.provisioner.checksum", slow_checksum)
    worker = Provisioner(
        tmp_path,
        manifest=manifest(),
        transport=httpx.MockTransport(unexpected_download),
        validate_urls=False,
    )
    events = worker.install("synthetic", "")
    assert (await anext(events))["progress"] == 0
    update = asyncio.create_task(anext(events))
    try:
        assert await asyncio.to_thread(halfway.wait, 5)
        checking = await asyncio.wait_for(update, timeout=3)
        assert 0 < checking["progress"] < 1
        assert checking["message"] == "Checking installed model files"
    finally:
        release.set()
    remaining = [event async for event in events]
    assert remaining[-1]["done"]
    assert worker.status()["models"][0]["state"] == "ready"
    assert path.stat().st_mtime_ns == original_mtime


async def test_install_verified_idempotent_and_detect_modified_file(tmp_path: Path) -> None:
    requests = []

    def download(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=DATA)

    worker = Provisioner(
        tmp_path, manifest=manifest(), transport=httpx.MockTransport(download), validate_urls=False
    )
    assert worker.status()["models"][0]["state"] == "missing"
    assert (await consume(worker))[-1]["done"]
    assert worker.status()["models"][0]["state"] == "ready"
    await consume(worker)
    assert len(requests) == 1
    (tmp_path / "synthetic/model.txt").write_bytes(b"x" * len(DATA))
    assert worker.status()["models"][0]["state"] == "unverified"
    await consume(worker)
    assert len(requests) == 2
    assert (tmp_path / "synthetic/model.txt").read_bytes() == DATA


async def test_partial_download_resumes_without_repeating_bytes(tmp_path: Path) -> None:
    partial = tmp_path / ".installation/partial/synthetic/0"
    partial.parent.mkdir(parents=True)
    partial.write_bytes(DATA[:10])

    def download(request: httpx.Request) -> httpx.Response:
        assert request.headers["range"] == "bytes=10-"
        return httpx.Response(
            206,
            content=DATA[10:],
            headers={"content-range": f"bytes 10-{len(DATA) - 1}/{len(DATA)}"},
        )

    worker = Provisioner(
        tmp_path, manifest=manifest(), transport=httpx.MockTransport(download), validate_urls=False
    )
    await consume(worker)
    assert (tmp_path / "synthetic/model.txt").read_bytes() == DATA


@pytest.mark.parametrize("content", [b"incomplete", b"x" * len(DATA), DATA + b"unexpected"])
async def test_bad_download_never_publishes_model(tmp_path: Path, content: bytes) -> None:
    worker = Provisioner(
        tmp_path,
        manifest=manifest(),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=content)),
        validate_urls=False,
    )
    with pytest.raises(ValueError, match="model"):
        await consume(worker)
    assert not (tmp_path / "synthetic/model.txt").exists()
    assert worker.status()["models"][0]["state"] == "missing"


async def test_insufficient_space_makes_no_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "probeloop.workspace.infrastructure.provisioner.shutil.disk_usage",
        lambda _: SimpleNamespace(free=1),
    )
    worker = Provisioner(tmp_path, manifest=manifest())
    with pytest.raises(ValueError, match="not enough space"):
        await consume(worker)


def test_private_download_url_and_catalog_escape_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="private or loopback"):
        validate_download_url("https://127.0.0.1/private")
    with pytest.raises(ValueError, match="HTTPS"):
        validate_download_url("http://example.test/model")
    worker = Provisioner(tmp_path, manifest=manifest())
    with pytest.raises(ValueError, match="catalog path"):
        worker.path("../outside")


def test_provisioner_exposes_only_catalogued_models(tmp_path: Path) -> None:
    with TestClient(create_provisioner_app(Provisioner(tmp_path, manifest=manifest()))) as client:
        assert client.get("/status").json()["models"][0]["id"] == "synthetic"
        assert client.post("/install/arbitrary", json={}).status_code == 404
        assert client.post("/install/synthetic", json={"command": "ignored"}).status_code == 422


async def test_http_adapter_requires_final_success_and_preserves_error() -> None:
    async def progress(value: float, message: str | None) -> None:
        pass

    for content, expected in [
        (b'{"progress":0.5}\n', "interrupted"),
        (b'{"error":"not enough space"}\n', "not enough space"),
    ]:
        adapter = HttpModelInstaller(
            "http://provisioner",
            transport=httpx.MockTransport(
                lambda _, payload=content: httpx.Response(200, content=payload)
            ),
        )
        with pytest.raises(ProvisioningError, match=expected):
            await adapter.install("synthetic", "", progress)


async def test_ollama_pull_uses_requested_model_and_reports_complete() -> None:
    updates = []

    def reply(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == {"model": "synthetic-model", "stream": True}
        return httpx.Response(
            200, content=b'{"status":"pulling","total":10,"completed":5}\n{"status":"success"}\n'
        )

    async def progress(value: float, message: str | None) -> None:
        updates.append(value)

    await OllamaModelManager(transport=httpx.MockTransport(reply)).pull(
        "http://ollama", "synthetic-model", progress
    )
    assert updates == [0.5, 1.0]
