"""CV checks outside an interview: ownership by a profile, a profile made from a check, and
deleting a check. All documents are synthetic."""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from probeloop.api.app import create_app
from probeloop.bootstrap import build
from probeloop.settings import Settings
from tests.api.test_context_api import confirm_role

CV = Path(__file__).parents[1] / "fixtures/synthetic/cv_review/cv.txt"


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(data_dir=tmp_path, allowed_hosts=["testserver"], llm_fake=True)
    with TestClient(create_app(build(settings))) as client:
        yield client


def wait(client: TestClient, url: str, done: tuple[str, ...]) -> dict[str, Any]:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        view: dict[str, Any] = client.get(url).json()
        if view["status"] in done:
            return view
        time.sleep(0.02)
    raise AssertionError(f"{url} did not reach {done}")


def approved_check(client: TestClient, profile_id: str | None = None) -> tuple[str, str]:
    """Upload a CV, analyse and approve it; returns the CV and the snapshot ids."""
    cv = client.post(
        "/api/documents/text", json={"kind": "cv", "title": "CV", "text": CV.read_text()}
    ).json()
    if profile_id == "new":
        profile = client.post(
            "/api/profiles", json={"name": "Backend", "cv_id": cv["id"], "resources": []}
        ).json()
        profile_id = profile["id"]
    preparation = client.post(
        "/api/preparations",
        json={"job_mode": "none", "cv_id": cv["id"], "profile_id": profile_id},
    ).json()
    view = wait(client, f"/api/preparations/{preparation['id']}", ("review",))
    confirm_role(client, view)
    client.put(
        f"/api/preparations/{preparation['id']}/area", json={"area": "Backend", "seniority": "mid"}
    )
    snapshot = client.post(f"/api/preparations/{preparation['id']}/approve").json()
    return cv["id"], snapshot["id"]


def review(client: TestClient, snapshot_id: str, profile_id: str | None = None) -> dict[str, Any]:
    response = client.post(
        f"/api/snapshots/{snapshot_id}/cv-reviews",
        json={"language": "en", "profile_id": profile_id},
    )
    assert response.status_code == 202, response.text
    job = wait(client, f"/api/jobs/{response.json()['id']}", ("succeeded", "failed"))
    assert job["status"] == "succeeded", job
    report: dict[str, Any] = client.get(f"/api/reports/{job['result']['report_id']}").json()
    return report


def test_a_cv_check_belongs_to_the_profile_it_was_made_for(client: TestClient) -> None:
    profile = client.post("/api/profiles", json={"name": "Backend", "resources": []}).json()
    _, snapshot_id = approved_check(client, profile["id"])

    report = review(client, snapshot_id, profile["id"])

    assert report["profile_id"] == profile["id"]
    [check] = client.get("/api/history/cv-checks", params={"profile_id": profile["id"]}).json()
    assert check["snapshot_id"] == snapshot_id
    assert check["profile"] == {"id": profile["id"], "name": "Backend"}
    assert client.get("/api/history/cv-checks", params={"profile_id": "other"}).json() == []
    [group] = client.get("/api/progress").json()
    [point] = group["points"]
    assert point["profile_id"] == profile["id"]
    assert point["role"]["target_role"]
    assert (point["rubric_id"], point["language"]) == (report["rubric_id"], "en")
    assert point["model_ref"] == report["model_ref"]


def test_unknown_profiles_are_refused(client: TestClient) -> None:
    cv_id, snapshot_id = approved_check(client)
    response = client.post(
        f"/api/snapshots/{snapshot_id}/cv-reviews",
        json={"language": "en", "profile_id": "missing"},
    )
    assert response.status_code == 404
    response = client.post(
        "/api/preparations", json={"job_mode": "none", "cv_id": cv_id, "profile_id": "missing"}
    )
    assert response.status_code == 404


def test_a_profile_made_from_a_check_owns_it(client: TestClient) -> None:
    cv_id, snapshot_id = approved_check(client)
    review(client, snapshot_id)

    response = client.post(f"/api/snapshots/{snapshot_id}/profile", json={"name": "Dal check"})

    assert response.status_code == 201, response.text
    profile = response.json()
    assert (profile["name"], profile["cv"]["id"], profile["job_mode"]) == (
        "Dal check",
        cv_id,
        "none",
    )
    [check] = client.get("/api/history/cv-checks", params={"profile_id": profile["id"]}).json()
    assert check["profile"]["name"] == "Dal check"
    [report] = client.get(f"/api/snapshots/{snapshot_id}/cv-reviews").json()
    assert report["profile_id"] == profile["id"]
    missing = client.post("/api/snapshots/missing/profile", json={"name": "X"})
    assert missing.status_code == 404


def test_deleting_a_one_off_check_removes_its_documents(client: TestClient) -> None:
    cv_id, snapshot_id = approved_check(client)
    review(client, snapshot_id)
    review(client, snapshot_id)

    assert client.delete(f"/api/snapshots/{snapshot_id}/cv-reviews").status_code == 204

    assert client.get("/api/history/cv-checks").json() == []
    assert client.get(f"/api/snapshots/{snapshot_id}").status_code == 404
    assert client.get(f"/api/documents/{cv_id}").status_code == 404
    assert client.get("/api/progress").json() == []
    assert client.delete(f"/api/snapshots/{snapshot_id}/cv-reviews").status_code == 404


def test_deleting_a_profile_check_keeps_the_profile_documents(client: TestClient) -> None:
    cv_id, snapshot_id = approved_check(client, "new")
    [profile] = client.get("/api/profiles").json()
    review(client, snapshot_id, profile["id"])

    assert client.delete(f"/api/snapshots/{snapshot_id}/cv-reviews").status_code == 204

    assert client.get(f"/api/snapshots/{snapshot_id}").status_code == 404
    assert client.get(f"/api/documents/{cv_id}").status_code == 200
    # The profile can be checked again from its documents.
    _, again = approved_check(client, profile["id"])
    assert review(client, again, profile["id"])["profile_id"] == profile["id"]


def test_deleting_a_profile_keeps_its_cv_checks(client: TestClient) -> None:
    cv_id, snapshot_id = approved_check(client, "new")
    [profile] = client.get("/api/profiles").json()
    review(client, snapshot_id, profile["id"])

    assert client.delete(f"/api/profiles/{profile['id']}").status_code == 204

    [check] = client.get("/api/history/cv-checks").json()
    assert check["profile"] == {"id": profile["id"], "name": None}
    assert client.get(f"/api/snapshots/{snapshot_id}").status_code == 200
    assert client.get(f"/api/documents/{cv_id}").status_code == 200
