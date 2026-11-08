from __future__ import annotations

import json
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from probeloop.context.application.snapshots import snapshot_of
from probeloop.storage.data import SqlDataStore
from probeloop.storage.database import current_revision, revisions, sessionmaker
from probeloop.storage.session_files import SessionFiles
from probeloop.storage.sql_context import SqlContextStore
from probeloop.storage.sql_reports import SqlReportStore
from probeloop.storage.sql_sessions import SqlSessionStore
from tests.assessment.support import synthetic_session
from tests.assessment.test_exports import sample_report
from tests.context.test_preparation import in_review


async def test_portable_backup_roundtrip_and_complete_owned_data_deletion(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    root = tmp_path / "data"
    sessions = sessionmaker(engine)
    context = SqlContextStore(sessions, root / "blobs")
    preparation = in_review()
    for document in preparation.documents:
        await context.add_document(document)
    await context.save_preparation(preparation)
    snapshot = snapshot_of(preparation, "snapshot", 0)
    await context.save_snapshot(snapshot)
    store = SqlSessionStore(sessions, SessionFiles(root / "sessions"))
    session = synthetic_session()
    session.snapshot_id = snapshot.id
    await store.save(session)
    await store.export(session, audio=False)
    report = replace(
        sample_report(), subject_id=session.id, session_id=session.id, snapshot_id=snapshot.id
    )
    await SqlReportStore(sessions).save(report)
    (root / "blobs").mkdir()
    source = Path(__file__).parents[1] / "fixtures/synthetic/cv_review/cv.txt"
    (root / "blobs" / "synthetic.txt").write_bytes(source.read_bytes())
    (root / ".env").write_text("synthetic configuration marker")
    data = SqlDataStore(engine, root)
    counts = await data.summary()
    exported = json.loads(await data.export_json())
    assert exported["tables"]["reports"][0]["id"] == report.id
    archive = await data.backup()
    downloaded = tmp_path / "downloaded.zip"
    downloaded.write_bytes(archive.read_bytes())
    try:
        with zipfile.ZipFile(archive) as contents:
            assert "blobs/synthetic.txt" in contents.namelist()
            assert "sessions/" + session.id + "/transcript.json" in contents.namelist()
            assert ".env" not in contents.namelist()
        await data.delete_all()
        assert not any((await data.summary()).values())
        assert not (root / "sessions").exists()
        assert not (root / "blobs").exists()
        assert (root / ".env").exists()
        await data.restore(downloaded)
        assert await data.summary() == counts
        assert await SqlReportStore(sessions).get(report.id) == report
        assert (root / "blobs" / "synthetic.txt").read_bytes() == source.read_bytes()
        with pytest.raises(ValueError, match="empty database"):
            await data.restore(downloaded)
    finally:
        archive.unlink(missing_ok=True)


@pytest.mark.parametrize(
    "entry", ["../outside.txt", "/absolute.txt", "blobs/../../outside.txt", "blobs//file.txt"]
)
async def test_restore_rejects_paths_before_changing_data(
    engine: AsyncEngine, tmp_path: Path, entry: str
) -> None:
    archive = tmp_path / "malformed.zip"
    with zipfile.ZipFile(archive, "w") as contents:
        contents.writestr(entry, "synthetic")
    data = SqlDataStore(engine, tmp_path / "data")
    with pytest.raises(ValueError, match="unsafe backup path"):
        await data.restore(archive)
    assert not any((await data.summary()).values())


async def test_deletion_refuses_an_owned_directory_redirected_outside_the_root(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    root = tmp_path / "data"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "marker").write_text("synthetic marker")
    (root / "blobs").symlink_to(outside, target_is_directory=True)
    data = SqlDataStore(engine, root)
    with pytest.raises(ValueError, match="inside"):
        await data.delete_all()
    assert (outside / "marker").exists()


def _archive(path: Path, content: dict[str, object]) -> Path:
    with zipfile.ZipFile(path, "w") as contents:
        contents.writestr("data.json", json.dumps(content))
    return path


async def test_a_backup_from_an_earlier_schema_is_upgraded_on_restore(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    root = tmp_path / "data"
    data = SqlDataStore(engine, root)
    store = SqlSessionStore(sessionmaker(engine), SessionFiles(root / "sessions"))
    session = synthetic_session()
    await store.save(session)
    exported = json.loads(await data.export_json())
    assert exported["format"] == "probeloop-data-v2"
    head = exported["revision"]
    assert head == revisions()[-1]
    # The same data as a backup taken before the reports table existed (revision 0002).
    del exported["tables"]["reports"]
    exported["revision"] = "0002"
    archive = _archive(tmp_path / "old.zip", exported)
    await data.delete_all()
    await data.restore(archive)
    assert await current_revision(engine) == head
    restored = await store.load(session.id)
    assert restored is not None
    assert restored.turns == session.turns


async def test_a_backup_without_a_recorded_revision_is_read_as_the_first_format(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    data = SqlDataStore(engine, tmp_path / "data")
    tables = json.loads(await data.export_json())["tables"]
    archive = _archive(tmp_path / "v1.zip", {"format": "probeloop-data-v1", "tables": tables})
    await data.restore(archive)
    assert await current_revision(engine) == revisions()[-1]


async def test_a_backup_from_a_newer_version_is_refused(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    data = SqlDataStore(engine, tmp_path / "data")
    content = json.loads(await data.export_json())
    content["revision"] = "9999"
    with pytest.raises(ValueError, match="newer or unknown"):
        await data.restore(_archive(tmp_path / "new.zip", content))
    assert await current_revision(engine) == revisions()[-1]


async def test_a_failed_restore_leaves_an_empty_database_at_the_current_schema(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    data = SqlDataStore(engine, tmp_path / "data")
    content = json.loads(await data.export_json())
    del content["tables"]["reports"]
    content["revision"] = "0002"
    content["tables"]["interview_sessions"] = [{"id": "x", "unknown_column": 1}]
    with pytest.raises(ValueError, match="invalid backup rows"):
        await data.restore(_archive(tmp_path / "bad.zip", content))
    assert await current_revision(engine) == revisions()[-1]
    assert not any((await data.summary()).values())


async def test_profiles_from_a_backup_before_profile_documents_have_none(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    from probeloop.context.domain.model import DocumentKind, Profile

    root = tmp_path / "data"
    data = SqlDataStore(engine, root)
    context = SqlContextStore(sessionmaker(engine), root / "blobs")
    resource = replace(in_review().documents[0], id="r1", kind=DocumentKind.RESOURCE)
    await context.add_document(resource)
    await context.save_profile(Profile("p1", "Backend", (resource,), 1, 1))
    content = json.loads(await data.export_json())
    # As exported by revision 0003, before profiles had a CV and a job offer.
    for row in content["tables"]["profiles"]:
        del row["cv_document_id"], row["job_offer_document_id"]
    content["revision"] = "0003"
    await data.delete_all()
    await data.restore(_archive(tmp_path / "0003.zip", content))
    restored = await context.profile("p1")
    assert restored is not None
    assert (restored.resources, restored.cv, restored.job_offer) == ((resource,), None, None)
