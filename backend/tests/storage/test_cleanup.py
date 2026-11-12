"""What deleting a CV check or a profile removes, and what it must keep. All data is synthetic."""

from __future__ import annotations

import copy
import hashlib
from dataclasses import replace
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from probeloop.assessment.domain.model import Report, ReportKind
from probeloop.context.application.snapshots import snapshot_of
from probeloop.context.domain.model import (
    Document,
    DocumentKind,
    DocumentOrigin,
    JobMode,
    Preparation,
    Profile,
    RoleProfile,
)
from probeloop.storage.database import ReportRow, downgrade, migrate, sessionmaker
from probeloop.storage.session_files import SessionFiles
from probeloop.storage.sql_context import SqlContextStore
from probeloop.storage.sql_reports import SqlReportStore
from probeloop.storage.sql_sessions import SqlSessionStore
from tests.conftest import make_session
from tests.context.conftest import cv, offer
from tests.context.test_preparation import in_review

ORIGINAL = b"%PDF synthetic CV bytes"
SHA = hashlib.sha256(ORIGINAL).hexdigest()


def uploaded(doc_id: str, created_at: float) -> Document:
    return replace(
        cv(),
        id=doc_id,
        origin=DocumentOrigin.UPLOAD,
        filename="cv.pdf",
        media_type="application/pdf",
        sha256=SHA,
        created_at=created_at,
    )


def report(
    report_id: str,
    subject_id: str,
    *,
    kind: ReportKind = ReportKind.CV,
    profile_id: str | None = None,
    version: int = 1,
) -> Report:
    interview = kind is ReportKind.INTERVIEW
    return Report(
        id=report_id,
        kind=kind,
        subject_id=subject_id,
        version=version,
        created_at=float(version),
        language="it",
        rubric_id="cv.v1",
        rubric_hash="h",
        model_ref="fake",
        prompt_ref="review_cv@v1",
        input_fingerprint="input",
        snapshot_id=None if interview else subject_id,
        session_id=subject_id if interview else None,
        scores=(),
        observations=(),
        checks=(),
        overall=None,
        assessed=0,
        criteria=0,
        dropped=0,
        duration_s=1,
        disclaimer="Formative review.",
        profile_id=profile_id,
    )


async def approved(
    store: SqlContextStore,
    documents: list[Document],
    *,
    preparation_id: str,
    snapshot_id: str,
    profile_id: str | None = None,
) -> Preparation:
    preparation = replace(in_review(), id=preparation_id, profile_id=profile_id)
    preparation.documents = documents
    preparation.set_role_profile(
        RoleProfile("Software", "Backend developer", "mid", confirmed=True)
    )
    snapshot = snapshot_of(preparation, snapshot_id, 1)
    await store.save_snapshot(snapshot)
    preparation.approve(snapshot.id)
    await store.save_preparation(preparation)
    return preparation


def blob(tmp_path: Path) -> Path:
    return tmp_path / "blobs" / SHA[:2] / SHA


async def test_deleting_a_cv_check_removes_its_context_and_one_off_documents(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    context = SqlContextStore(sessionmaker(engine), tmp_path / "blobs")
    reports = SqlReportStore(sessionmaker(engine))
    original = uploaded("up1", 1)
    await context.add_document(original, ORIGINAL)
    edited = original.revised("ed1", "Testo corretto del CV", None, 2)
    for document in (edited, offer()):
        await context.add_document(document)
    await approved(context, [edited, offer()], preparation_id="p1", snapshot_id="s1")
    await reports.save(report("r1", "s1"))
    await reports.save(report("r2", "s1", version=2))
    assert blob(tmp_path).exists()

    assert await reports.delete_cv_check("s1")
    assert await context.discard_snapshot("s1")

    assert await reports.reports(ReportKind.CV, "s1") == []
    assert await context.snapshot("s1") is None
    assert await context.preparation("p1") is None
    # The edited text, the upload it came from and the uploaded file are all gone.
    assert await context.documents(["up1", "ed1", offer().id]) == []
    assert not blob(tmp_path).exists()
    assert not await reports.delete_cv_check("s1")
    assert not await context.discard_snapshot("s1")


async def test_a_saved_profile_keeps_the_documents_of_its_deleted_cv_check(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    context = SqlContextStore(sessionmaker(engine), tmp_path / "blobs")
    reports = SqlReportStore(sessionmaker(engine))
    for document in (cv(), offer()):
        await context.add_document(document)
    await context.save_profile(Profile("pr1", "Backend", (), 1, 1, cv=cv(), job_offer=offer()))
    await approved(
        context, [cv(), offer()], preparation_id="p1", snapshot_id="s1", profile_id="pr1"
    )
    await reports.save(report("r1", "s1", profile_id="pr1"))

    assert await reports.delete_cv_check("s1")
    assert await context.discard_snapshot("s1")

    assert await context.snapshot("s1") is None
    assert await context.preparation("p1") is None
    assert {d.id for d in await context.documents([cv().id, offer().id])} == {cv().id, offer().id}


async def test_a_context_that_an_interview_uses_is_kept(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    context = SqlContextStore(sessionmaker(engine), tmp_path / "blobs")
    reports = SqlReportStore(sessionmaker(engine))
    sessions = SqlSessionStore(sessionmaker(engine), SessionFiles(tmp_path / "sessions"))
    for document in (cv(), offer()):
        await context.add_document(document)
    await approved(context, [cv(), offer()], preparation_id="p1", snapshot_id="s1")
    session = make_session(session_id="i" * 32)
    session.snapshot_id = "s1"
    await sessions.save(session)
    await reports.save(report("r1", "s1"))

    assert await reports.delete_cv_check("s1")
    assert not await context.discard_snapshot("s1")

    assert await context.snapshot("s1") is not None
    assert await context.preparation("p1") is not None
    assert len(await context.documents([cv().id, offer().id])) == 2


async def test_deleting_a_profile_keeps_what_reports_use_and_drops_the_rest(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    context = SqlContextStore(sessionmaker(engine), tmp_path / "blobs")
    reports = SqlReportStore(sessionmaker(engine))
    note = replace(cv(), id="note", kind=DocumentKind.RESOURCE, title="Note")
    draft_cv = replace(cv(), id="draft-cv")
    in_flight = replace(cv(), id="in-flight", created_at=9)
    for document in (cv(), offer(), note, draft_cv, in_flight):
        await context.add_document(document)
    await context.save_profile(Profile("pr1", "Backend", (note,), 1, 1, cv=cv(), job_offer=offer()))
    # Approved and checked: the CV check stays, so its context and documents stay.
    await approved(
        context, [cv(), offer()], preparation_id="p1", snapshot_id="s1", profile_id="pr1"
    )
    await reports.save(report("r1", "s1", profile_id="pr1"))
    # Approved but never used: an intermediate state of the profile.
    await approved(context, [draft_cv], preparation_id="p2", snapshot_id="s2", profile_id="pr1")
    # Still in review.
    reviewing = replace(in_review(JobMode.NONE), id="p3", profile_id="pr1")
    reviewing.documents = [draft_cv]
    await context.save_preparation(reviewing)

    assert await context.delete_profile("pr1")

    assert await context.profile("pr1") is None
    assert await context.snapshot("s1") is not None
    assert await context.preparation("p1") is not None
    assert await reports.reports(ReportKind.CV, "s1") != []
    assert await context.snapshot("s2") is None
    assert await context.preparation("p2") is None
    assert await context.preparation("p3") is None
    remaining = {d.id for d in await context.documents([cv().id, offer().id, "note", "draft-cv"])}
    assert remaining == {cv().id, offer().id}
    # A document that nothing refers to yet may belong to work in progress.
    assert [d.id for d in await context.documents(["in-flight"])] == ["in-flight"]
    assert not await context.delete_profile("pr1")


async def test_a_newer_upload_of_the_same_file_keeps_it(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    context = SqlContextStore(sessionmaker(engine), tmp_path / "blobs")
    reports = SqlReportStore(sessionmaker(engine))
    await context.add_document(uploaded("up1", 1), ORIGINAL)
    await context.add_document(uploaded("up2", 5), ORIGINAL)
    await approved(context, [uploaded("up1", 1)], preparation_id="p1", snapshot_id="s1")
    await reports.save(report("r1", "s1"))

    assert await reports.delete_cv_check("s1")
    assert await context.discard_snapshot("s1")

    assert [d.id for d in await context.documents(["up1", "up2"])] == ["up2"]
    assert blob(tmp_path).exists()


async def test_reports_keep_their_owner_outside_the_assessed_content(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    context = SqlContextStore(sessionmaker(engine), tmp_path / "blobs")
    reports = SqlReportStore(sessionmaker(engine))
    for document in (cv(), offer()):
        await context.add_document(document)
    await approved(context, [cv(), offer()], preparation_id="p1", snapshot_id="s1")
    await reports.save(report("r1", "s1", profile_id="pr1"))
    await reports.save(report("r2", "s1", version=2))

    assert (await reports.get("r1")) == report("r1", "s1", profile_id="pr1")
    async with sessionmaker(engine)() as db:
        data = await db.scalar(select(ReportRow.data).where(ReportRow.id == "r1"))
    assert data is not None
    assert "profile_id" not in data

    assert await reports.adopt_cv_reports("s1", "pr2") == 1
    owners = [r.profile_id for r in await reports.reports(ReportKind.CV, "s1")]
    assert owners == ["pr1", "pr2"]


async def test_upgrading_gives_existing_reports_their_profile(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    context = SqlContextStore(sessionmaker(engine), tmp_path / "blobs")
    reports = SqlReportStore(sessionmaker(engine))
    sessions = SqlSessionStore(sessionmaker(engine), SessionFiles(tmp_path / "sessions"))
    for document in (cv(), offer()):
        await context.add_document(document)
    session = make_session(session_id="i" * 32)
    session.profile_id = "pr1"
    await sessions.save(session)
    await reports.save(report("ri", session.id, kind=ReportKind.INTERVIEW))
    await approved(
        context, [cv(), offer()], preparation_id="p1", snapshot_id="s1", profile_id="pr2"
    )
    await reports.save(report("r1", "s1"))
    # Two profiles approved the same content: the owner of its CV check is unknown.
    shared = await approved(
        context, [cv()], preparation_id="p2", snapshot_id="s2", profile_id="pr2"
    )
    other = copy.copy(shared)
    other.id, other.profile_id = "p3", "pr3"
    await context.save_preparation(other)
    await reports.save(report("r2", "s2"))

    await downgrade(engine, "0008")
    await migrate(engine)

    owners = {r.id: r.profile_id for r in await reports.all()}
    assert owners == {"ri": "pr1", "r1": "pr2", "r2": None}
