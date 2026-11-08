from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from probeloop.ai.fake import FakeChatModel
from probeloop.api.app import create_app
from probeloop.bootstrap import build
from probeloop.settings import Settings
from tests.context.conftest import CV_TEXT, OFFER_TEXT, scripted_analysis
from tests.pdf_writer import text_pdf


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(data_dir=tmp_path, allowed_hosts=["testserver"], stt_url=None, tts_url=None)
    model = FakeChatModel([scripted_analysis()])
    with TestClient(create_app(build(settings, model=model, analysis_model=model))) as c:
        yield c


def typed(client: TestClient, kind: str, title: str, text: str) -> str:
    response = client.post("/api/documents/text", json={"kind": kind, "title": title, "text": text})
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def wait_for_review(client: TestClient, preparation_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        view: dict[str, Any] = client.get(f"/api/preparations/{preparation_id}").json()
        if view["status"] != "analysing" and view["analysis"]["status"] != "running":
            return view
        time.sleep(0.02)
    raise AssertionError(
        f"analysis did not finish: {view['status']}, job {view['analysis']['status']}"
    )


def test_documents_upload_as_files_or_text(client: TestClient, tmp_path: Path) -> None:
    pdf = text_pdf(CV_TEXT.splitlines())
    response = client.post(
        "/api/documents",
        data={"kind": "cv", "title": "CV"},
        files={"file": ("cv.pdf", pdf, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    view = response.json()
    assert (view["kind"], view["media_type"], view["filename"]) == (
        "cv",
        "application/pdf",
        "cv.pdf",
    )
    assert view["preview"].startswith("Giulia Neri\nBackend developer")
    assert len(list((tmp_path / "blobs").rglob("*"))) == 2  # the original, by sha256
    assert client.get(f"/api/documents/{view['id']}").json()["text"].startswith("Giulia Neri")
    assert client.get("/api/documents/missing").status_code == 404

    bad = client.post(
        "/api/documents",
        data={"kind": "resource", "title": "x"},
        files={"file": ("tool.exe", b"MZ", "application/octet-stream")},
    )
    assert bad.status_code == 422
    assert "unsupported file type" in bad.json()["detail"]
    empty = client.post("/api/documents/text", json={"kind": "cv", "title": "CV", "text": " "})
    assert empty.status_code == 422


def test_profiles_save_titled_resources(client: TestClient) -> None:
    notes = typed(client, "resource", "notes.md", "Progetto di routing in Python.")
    readme = typed(client, "resource", "README", "Libreria open source.")
    created = client.post(
        "/api/profiles",
        json={
            "name": "Backend",
            "resources": [
                {"title": "Note sul routing", "document_id": notes},
                {"title": "", "document_id": readme},
            ],
        },
    )
    assert created.status_code == 201, created.text
    profile = created.json()
    assert [r["title"] for r in profile["resources"]] == ["Note sul routing", "README"]

    overwritten = client.put(
        f"/api/profiles/{profile['id']}",
        json={"name": "Backend 2", "resources": [{"title": "Solo README", "document_id": readme}]},
    )
    assert [r["title"] for r in overwritten.json()["resources"]] == ["Solo README"]
    assert [p["name"] for p in client.get("/api/profiles").json()] == ["Backend 2"]
    cv = typed(client, "cv", "CV", CV_TEXT)
    wrong = client.post(
        "/api/profiles", json={"name": "x", "resources": [{"title": "t", "document_id": cv}]}
    )
    assert wrong.status_code == 422
    assert client.delete(f"/api/profiles/{profile['id']}").status_code == 204
    assert client.get("/api/profiles").json() == []


def test_from_documents_to_an_interview_with_its_own_plan(client: TestClient) -> None:
    cv = typed(client, "cv", "CV", CV_TEXT)
    offer = typed(client, "job_offer", "Offerta", OFFER_TEXT)
    started = client.post(
        "/api/preparations",
        json={"language": "it", "job_mode": "offer", "cv_id": cv, "job_offer_id": offer},
    )
    assert started.status_code == 202, started.text
    view = wait_for_review(client, started.json()["id"])
    assert view["status"] == "review", view
    assert view["analysis"]["status"] == "succeeded"
    assert {f["origin"] for f in view["facts"]} == {"declared", "inferred"}
    assert "Kafka" in view["vocabulary"]

    inferred = next(f for f in view["facts"] if f["origin"] == "inferred")
    base = f"/api/preparations/{view['id']}"
    assert (
        client.put(f"{base}/facts/{inferred['id']}", json={"review": "excluded"}).status_code == 200
    )
    added = client.post(
        f"{base}/facts", json={"subject": "candidate", "kind": "skill", "statement": "Go di base."}
    )
    assert added.status_code == 201

    snapshot = client.post(f"{base}/approve").json()
    assert "Go di base." in snapshot["candidate_brief"]
    assert "Esperta di Kafka." not in snapshot["candidate_brief"]
    assert "Requirements the candidate's documents do not show" in snapshot["job_brief"]
    assert client.post(f"{base}/approve").status_code == 422  # already approved

    session = client.post(
        "/api/sessions",
        json={
            "interview_type": "technical",
            "language": "it",
            "duration_minutes": 10,
            "snapshot_id": snapshot["id"],
        },
    )
    assert session.status_code == 201, session.text
    created = session.json()
    assert created["snapshot_id"] == snapshot["id"]
    assert [t["title"] for t in created["topics"]] == [
        "Il servizio di ottimizzazione dei percorsi",
        "Esperienza con Kafka, non mostrata",
        "Candidate questions and closing",
    ]
    missing = client.post("/api/sessions", json={"interview_type": "hr", "snapshot_id": "0" * 32})
    assert missing.status_code == 404


def test_without_a_job_offer_the_area_is_reviewed(client: TestClient) -> None:
    cv = typed(client, "cv", "CV", CV_TEXT)
    started = client.post("/api/preparations", json={"job_mode": "none", "cv_id": cv})
    view = wait_for_review(client, started.json()["id"])
    assert view["area"]["area"] == "sviluppo backend"
    assert client.post(f"/api/preparations/{view['id']}/approve").status_code == 422
    changed = client.put(
        f"/api/preparations/{view['id']}/area",
        json={"area": "data engineering", "seniority": "senior"},
    )
    assert changed.json()["area"]["confirmed"] is True
    snapshot = client.post(f"/api/preparations/{view['id']}/approve").json()
    assert "data engineering (senior)" in snapshot["job_brief"]

    mismatch = client.post("/api/preparations", json={"job_mode": "offer", "cv_id": cv})
    assert mismatch.status_code == 422


def test_a_job_offer_is_drafted_for_editing(client: TestClient) -> None:
    response = client.post(
        "/api/job-offers/draft",
        json={"description": "ruolo junior PHP in una web agency, 0-2 anni", "language": "it"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["text"].startswith("Sviluppatore web junior")
    assert client.post("/api/job-offers/draft", json={"description": "x"}).status_code == 422


def test_identical_documents_reuse_the_approved_snapshot(client: TestClient) -> None:
    snapshots = []
    for _ in range(2):
        cv = typed(client, "cv", "CV", CV_TEXT)
        offer = typed(client, "job_offer", "Offerta", OFFER_TEXT)
        response = client.post(
            "/api/preparations",
            json={
                "job_mode": "offer",
                "cv_id": cv,
                "job_offer_id": offer,
            },
        )
        view = wait_for_review(client, response.json()["id"])
        snapshot = client.post(f"/api/preparations/{view['id']}/approve")
        assert snapshot.status_code == 200, snapshot.text
        snapshots.append(snapshot.json()["id"])
    assert snapshots[0] == snapshots[1]
