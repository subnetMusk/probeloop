"""Requests refused with 409 while background work uses the models. Documents are synthetic."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from probeloop.api.app import create_app
from probeloop.bootstrap import Container, build
from probeloop.platform.jobs import Job, Progress
from probeloop.settings import Settings
from tests.api.test_cv_checks_api import approved_check


@pytest.fixture
def container(tmp_path: Path) -> Container:
    return build(Settings(data_dir=tmp_path, allowed_hosts=["testserver"], llm_fake=True))


@pytest.fixture
def client(container: Container) -> Iterator[TestClient]:
    with TestClient(create_app(container)) as client:
        yield client


def test_data_and_interviews_wait_for_a_running_job(
    container: Container, client: TestClient
) -> None:
    assert client.portal is not None
    _, snapshot_id = approved_check(client)
    release = client.portal.call(asyncio.Event)

    async def blocking(job: Job, progress: Progress) -> None:
        await release.wait()

    container.jobs.register("test_blocking", blocking)
    client.portal.call(container.jobs.submit, "test_blocking", "subject")
    deadline = time.monotonic() + 5
    while not container.jobs.running and time.monotonic() < deadline:
        time.sleep(0.01)
    assert container.jobs.running

    export = client.get("/api/data/export")
    assert export.status_code == 409
    assert export.json()["detail"] == "wait for background jobs to finish first"
    assert client.post("/api/data/backup").status_code == 409
    deleted = client.post("/api/data/delete-all", json={"confirmation": "DELETE ALL DATA"})
    assert deleted.status_code == 409
    created = client.post(
        "/api/sessions",
        json={
            "interview_type": "technical",
            "language": "it",
            "duration_minutes": 5,
            "snapshot_id": snapshot_id,
        },
    )
    assert created.status_code == 409

    client.portal.call(release.set)
    client.portal.call(container.jobs.wait_idle)
    assert client.get("/api/data/export").status_code == 200
    assert client.get("/api/data/summary").json()["documents"] >= 1
