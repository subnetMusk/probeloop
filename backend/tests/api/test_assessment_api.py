from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from probeloop.api.app import create_app
from probeloop.bootstrap import build
from probeloop.interview.domain.model import RevisionSource
from probeloop.settings import Settings
from tests.assessment.support import synthetic_session

CV = Path(__file__).parents[1] / "fixtures/synthetic/cv_review/cv.txt"


def test_cv_review_is_a_job_and_regeneration_preserves_versions(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, allowed_hosts=["testserver"], llm_fake=True)
    with TestClient(create_app(build(settings))) as client:
        document = client.post(
            "/api/documents/text", json={"kind": "cv", "title": "CV", "text": CV.read_text()}
        ).json()
        preparation = client.post(
            "/api/preparations", json={"job_mode": "none", "cv_id": document["id"]}
        ).json()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            view = client.get(f"/api/preparations/{preparation['id']}").json()
            if view["status"] == "review":
                break
            time.sleep(0.02)
        assert view["status"] == "review"
        client.put(
            f"/api/preparations/{preparation['id']}/area",
            json={"area": "Backend", "seniority": "mid"},
        )
        snapshot = client.post(f"/api/preparations/{preparation['id']}/approve").json()
        for version in (1, 2):
            result = client.post(
                f"/api/snapshots/{snapshot['id']}/cv-reviews", json={"language": "en"}
            )
            assert result.status_code == 202
            job = result.json()
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                job = client.get(f"/api/jobs/{job['id']}").json()
                if job["status"] in ("succeeded", "failed"):
                    break
                time.sleep(0.02)
            assert job["status"] == "succeeded", job
            report = client.get(f"/api/reports/{job['result']['report_id']}").json()
            assert report["version"] == version
            assert report["language"] == "en"
            assert report["overall"] == 3
            assert report["assessed"] == 7
            assert report["checks"]
        assert len(client.get(f"/api/snapshots/{snapshot['id']}/cv-reviews").json()) == 2
        assert client.get("/api/reports/missing").status_code == 404


def test_interview_reports_keep_revisions_and_export_complete_versions(tmp_path: Path) -> None:
    container = build(Settings(data_dir=tmp_path, allowed_hosts=["testserver"], llm_fake=True))
    with TestClient(create_app(container)) as client:
        assert client.portal is not None
        session = synthetic_session()
        client.portal.call(container.store.save, session)
        original = None
        for version in (1, 2):
            if version == 2:
                session.revise_answer(
                    1,
                    "I personally designed the recovery procedure.",
                    RevisionSource.USER_EDIT,
                    301,
                )
                client.portal.call(container.store.save, session)
            response = client.post(f"/api/sessions/{session.id}/reports", json={"language": "en"})
            assert response.status_code == 202, response.text
            job = response.json()
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                job = client.get(f"/api/jobs/{job['id']}").json()
                if job["status"] in ("succeeded", "failed"):
                    break
                time.sleep(0.02)
            assert job["status"] == "succeeded", job
            report = client.get(f"/api/reports/{job['result']['report_id']}").json()
            assert report["version"] == version
            assert report["revisions"][0] == {"seq": 1, "revision": version}
            assert report["units"][-1]["kind"] == "logistics"
            assert report["unit_scores"]
            assert report["delivery"]
            md = client.get(f"/api/reports/{report['id']}/export/md")
            assert md.status_code == 200
            assert "Provenance" in md.text
            exported = client.get(f"/api/reports/{report['id']}/export/json").json()
            assert exported == report
            if original is None:
                original = report
            else:
                assert report["input_fingerprint"] != original["input_fingerprint"]
        assert client.get(f"/api/reports/{original['id']}").json() == original
        assert len(client.get(f"/api/sessions/{session.id}/reports").json()) == 2
        assert client.delete(f"/api/sessions/{session.id}").status_code == 204
        assert client.get(f"/api/reports/{original['id']}").status_code == 404
