from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from probeloop.ai.chatgpt import USAGE_LIMIT
from probeloop.ai.fake import FakeChatModel
from probeloop.ai.ports import UserActionRequiredError
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

        [check] = client.get("/api/history/cv-checks").json()
        assert (check["snapshot_id"], check["job_mode"], check["job_offer"]) == (
            snapshot["id"],
            "none",
            None,
        )
        assert check["cv"]["id"] == document["id"]
        latest = check["latest_report"]
        assert (latest["id"], latest["version"], latest["versions"]) == (report["id"], 2, 2)
        [group] = client.get("/api/progress").json()
        assert group["kind"] == "cv"
        assert group["scorer_key"]
        assert [(p["report_id"], p["interview_type"]) for p in group["points"]] == [
            (report["id"], None)
        ]


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
            assert "technical.v2" in report["rubric_id"]
            assert report["units"][-1]["kind"] == "logistics"
            assert report["unit_scores"]
            assert report["delivery"]
            md = client.get(f"/api/reports/{report['id']}/export/md")
            assert md.status_code == 200
            assert "Technical details" in md.text
            exported = client.get(f"/api/reports/{report['id']}/export/json").json()
            assert exported == report
            if original is None:
                original = report
            else:
                assert report["input_fingerprint"] != original["input_fingerprint"]
        assert client.get(f"/api/reports/{original['id']}").json() == original
        old_export = client.get(f"/api/reports/{original['id']}/export/md").text
        assert session.turns[1].revisions[0].text in old_export
        assert "I personally designed the recovery procedure." not in old_export
        assert len(client.get(f"/api/sessions/{session.id}/reports").json()) == 2

        [entry] = client.get("/api/history/interviews").json()
        assert entry["id"] == session.id
        assert entry["answers"] == len(session.candidate_turns())
        latest = entry["latest_report"]
        assert (latest["id"], latest["version"], latest["versions"]) == (report["id"], 2, 2)
        [group] = client.get("/api/progress").json()
        assert group["kind"] == "interview"
        assert [p["interview_type"] for p in group["points"]] == [
            session.config.interview_type.value
        ]
        assert client.delete(f"/api/sessions/{session.id}").status_code == 204
        assert client.get(f"/api/reports/{original['id']}").status_code == 404


def test_a_refusal_the_user_can_resolve_is_reported_as_is(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, allowed_hosts=["testserver"])
    model = FakeChatModel(["x"])
    analysis = FakeChatModel([UserActionRequiredError(USAGE_LIMIT)])
    container = build(settings, model=model, analysis_model=analysis, assessment_model=model)
    with TestClient(create_app(container)) as client:
        document = client.post(
            "/api/documents/text", json={"kind": "cv", "title": "CV", "text": CV.read_text()}
        ).json()
        preparation = client.post(
            "/api/preparations", json={"job_mode": "none", "cv_id": document["id"]}
        ).json()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            view = client.get(f"/api/preparations/{preparation['id']}").json()
            if view["status"] == "failed":
                break
            time.sleep(0.02)
        assert view["error"] == USAGE_LIMIT
