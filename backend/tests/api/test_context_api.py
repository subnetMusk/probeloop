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


def confirm_role(client: TestClient, view: dict[str, Any], **changes: Any) -> dict[str, Any]:
    response = client.put(
        f"/api/preparations/{view['id']}/role-profile",
        json={
            **view["role_profile"],
            **changes,
            "confirmed": True,
        },
    )
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


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


def test_profiles_keep_a_cv_and_a_job_offer_and_can_be_renamed(client: TestClient) -> None:
    cv = typed(client, "cv", "CV", CV_TEXT)
    offer = typed(client, "job_offer", "Offerta", OFFER_TEXT)
    created = client.post(
        "/api/profiles",
        json={"name": "Backend", "cv_id": cv, "job_offer_id": offer, "resources": []},
    ).json()
    assert (created["job_mode"], created["cv"]["id"], created["job_offer"]["id"]) == (
        "offer",
        cv,
        offer,
    )
    renamed = client.patch(f"/api/profiles/{created['id']}", json={"name": "Ruoli backend"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Ruoli backend"
    assert renamed.json()["cv"]["id"] == cv
    assert client.patch("/api/profiles/missing", json={"name": "x"}).status_code == 404
    swapped = client.post("/api/profiles", json={"name": "x", "cv_id": offer, "resources": []})
    assert swapped.status_code == 422


def test_editing_a_document_creates_a_revision(client: TestClient) -> None:
    upload = client.post(
        "/api/documents",
        data={"kind": "cv", "title": "CV"},
        files={"file": ("cv.txt", CV_TEXT.encode(), "text/plain")},
    ).json()
    assert upload["has_original"] is True
    revised = client.post(
        f"/api/documents/{upload['id']}/revisions", json={"text": "Giulia Neri, backend."}
    )
    assert revised.status_code == 201
    view = revised.json()
    assert view["id"] != upload["id"]
    assert (view["origin"], view["filename"], view["has_original"]) == ("edited", "cv.txt", True)
    assert client.get(f"/api/documents/{upload['id']}").json()["text"].startswith("Giulia Neri")
    missing = client.post("/api/documents/missing/revisions", json={"text": "x"})
    assert missing.status_code == 404


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

    # The offer's heading and the model disagree on Kafka: the cue wins until the user decides.
    kafka = next(
        f
        for f in view["facts"]
        if f["statement"] == "Esperienza con Kafka e architetture a eventi."
    )
    assert (kafka["kind"], kafka["requirement"]["obligation"]) == ("requirement", "must")
    assert kafka["requirement"]["disputed"] is True
    assert {r["source"] for r in kafka["requirement"]["readings"]} == {"cue", "model"}
    settled = client.put(f"{base}/facts/{kafka['id']}/obligation", json={"obligation": "preferred"})
    assert settled.status_code == 200, settled.text
    updated = next(f for f in settled.json()["facts"] if f["id"] == kafka["id"])
    assert (updated["kind"], updated["requirement"]["disputed"]) == ("nice_to_have", False)
    not_a_requirement = client.put(
        f"{base}/facts/{inferred['id']}/obligation", json={"obligation": "must"}
    )
    assert not_a_requirement.status_code == 422

    confirm_role(client, view)
    snapshot = client.post(f"{base}/approve").json()
    assert "Go di base." in snapshot["candidate_brief"]
    assert "Esperta di Kafka." not in snapshot["candidate_brief"]
    assert "Confirmed target expectations" in snapshot["job_brief"]
    assert client.post(f"{base}/approve").status_code == 422  # already approved
    assert (snapshot["language"], snapshot["job_mode"], snapshot["area"]) == ("it", "offer", None)
    assert [d["kind"] for d in snapshot["documents"]] == ["cv", "job_offer"]
    assert snapshot["created_at"] > 0
    requirements = snapshot["requirements"]
    assert requirements
    assert {r["kind"] for r in requirements} <= {"requirement", "nice_to_have"}
    assert {r["status"] for r in requirements} <= {"met", "partial", "not_shown"}
    statements = {f["id"]: f["statement"] for f in view["facts"]}
    for requirement in requirements:
        assert requirement["text"] == statements[requirement["id"]]
        assert "Esperta di Kafka." not in requirement["supporting"]  # excluded during review
    assert client.get(f"/api/snapshots/{snapshot['id']}").json() == snapshot

    # Back to the review after approval: the same content gives the same snapshot.
    reopened = client.post(f"{base}/reopen")
    assert reopened.status_code == 200, reopened.text
    assert (reopened.json()["status"], reopened.json()["snapshot_id"]) == ("review", None)
    assert client.post(f"{base}/approve").json()["id"] == snapshot["id"]
    assert client.post("/api/preparations/missing/reopen").status_code == 404

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
    confirm_role(client, view, profession="data engineering", seniority="senior")
    snapshot = client.post(f"/api/preparations/{view['id']}/approve").json()
    assert snapshot["role_profile"]["profession"] == "data engineering"
    assert snapshot["role_profile"]["seniority"] == "senior"

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
        confirm_role(client, view)
        snapshot = client.post(f"/api/preparations/{view['id']}/approve")
        assert snapshot.status_code == 200, snapshot.text
        snapshots.append(snapshot.json()["id"])
    assert snapshots[0] == snapshots[1]


def test_original_files_are_served_safely(client: TestClient, tmp_path: Path) -> None:
    pdf_bytes = text_pdf(["Giulia Neri", "Backend developer"])
    pdf = client.post(
        "/api/documents",
        data={"kind": "cv", "title": "CV"},
        files={"file": ("Curriculum è.pdf", pdf_bytes, "application/pdf")},
    ).json()
    shown = client.get(f"/api/documents/{pdf['id']}/original")
    assert shown.status_code == 200
    assert shown.content == pdf_bytes
    assert shown.headers["content-type"] == "application/pdf"
    assert shown.headers["content-disposition"].startswith('inline; filename="Curriculum _.pdf"')
    assert "filename*=UTF-8''Curriculum%20%C3%A8.pdf" in shown.headers["content-disposition"]
    assert shown.headers["x-content-type-options"] == "nosniff"

    page = client.post(
        "/api/documents",
        data={"kind": "resource", "title": "Pagina"},
        files={"file": ("page.html", b"<p>Progetto di routing in Python.</p>", "text/html")},
    ).json()
    downloaded = client.get(f"/api/documents/{page['id']}/original")
    assert downloaded.headers["content-disposition"].startswith("attachment;")

    edited = client.post(
        f"/api/documents/{pdf['id']}/revisions", json={"text": "Giulia Neri, backend."}
    ).json()
    assert client.get(f"/api/documents/{edited['id']}/original").content == pdf_bytes

    notes = typed(client, "resource", "Note", "Progetto di routing in Python.")
    text = client.get(f"/api/documents/{notes}/original")
    assert text.headers["content-type"] == "text/plain; charset=utf-8"
    assert text.headers["content-disposition"].startswith('attachment; filename="Note.txt"')
    assert text.text == "Progetto di routing in Python."

    for blob in (tmp_path / "blobs").rglob("*"):
        if blob.is_file():
            blob.unlink()
    lost = client.get(f"/api/documents/{pdf['id']}/original")
    assert (lost.status_code, lost.json()["detail"]) == (404, "original file not available")
    assert client.get("/api/documents/missing/original").status_code == 404


def test_without_documents_the_target_profile_is_required_and_persisted(client: TestClient) -> None:
    created = client.post("/api/preparations", json={"job_mode": "none"})
    assert created.status_code == 202
    view = created.json()
    assert view["status"] == "review"
    assert view["analysis"] is None
    assert client.post(f"/api/preparations/{view['id']}/approve").status_code == 422
    updated = confirm_role(
        client,
        view,
        profession="Economics",
        target_role="Research economist",
        seniority="Junior under supervision",
        competencies=["Interpreting economic evidence"],
    )
    assert updated["role_profile"]["confirmed"]
    snapshot = client.post(f"/api/preparations/{view['id']}/approve").json()
    assert snapshot["documents"] == []
    assert "Marco" not in snapshot["candidate_brief"]
    assert snapshot["role_profile"]["target_role"] == "Research economist"
    assert client.get(f"/api/snapshots/{snapshot['id']}").json() == snapshot
