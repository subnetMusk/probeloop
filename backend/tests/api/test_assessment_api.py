from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from probeloop.api.app import create_app
from probeloop.bootstrap import build
from probeloop.settings import Settings

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
