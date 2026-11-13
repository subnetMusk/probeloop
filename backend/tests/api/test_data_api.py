from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from probeloop.api.app import create_app
from probeloop.bootstrap import build
from probeloop.settings import Settings
from tests.assessment.support import synthetic_session


def test_data_downloads_and_explicit_complete_deletion(tmp_path: Path) -> None:
    container = build(Settings(data_dir=tmp_path, llm_fake=True, allowed_hosts=["testserver"]))
    with TestClient(create_app(container)) as client:
        assert client.portal is not None
        session = synthetic_session()
        client.portal.call(container.store.save, session)
        assert client.get("/api/data/summary").json()["interview_sessions"] == 1
        export = client.get("/api/data/export")
        assert export.json()["tables"]["interview_sessions"][0]["id"] == session.id
        assert re.match(
            r'attachment; filename="probeloop-data-\d{8}-\d{6}\.json"',
            export.headers["content-disposition"],
        )
        token = client.post("/api/data/backup").json()["id"]
        backup = client.get(f"/api/data/backup/{token}")
        assert backup.content.startswith(b"PK")
        assert re.match(
            r'attachment; filename="probeloop-backup-\d{8}-\d{6}\.zip"',
            backup.headers["content-disposition"],
        )
        assert client.get(f"/api/data/backup/{token}").status_code == 404
        assert (
            client.post("/api/data/delete-all", json={"confirmation": "wrong"}).status_code == 422
        )
        assert client.get("/api/data/summary").json()["interview_sessions"] == 1
        assert (
            client.post(
                "/api/data/delete-all", json={"confirmation": "DELETE ALL DATA"}
            ).status_code
            == 204
        )
        assert not any(client.get("/api/data/summary").json().values())
