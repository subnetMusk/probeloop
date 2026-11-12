"""Context store on the database. Uploaded files are kept in the blob directory by sha256."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from probeloop.context.domain.model import (
    ContextSnapshot,
    Document,
    DocumentKind,
    DocumentOrigin,
    Fact,
    FactKind,
    FactOrigin,
    JobMode,
    MatchStatus,
    Preparation,
    PreparationStatus,
    Profile,
    RequirementMatch,
    Review,
    RoleProfile,
    Subject,
    TargetArea,
)
from probeloop.storage.database import (
    ContextExtractionRow,
    DocumentRow,
    JobRow,
    PreparationRow,
    ProfileResourceRow,
    ProfileRow,
    ReportRow,
    SessionRow,
    SnapshotRow,
)
from probeloop.storage.session_files import atomic_write


class SqlContextStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], blobs: Path) -> None:
        self._sessions = sessions
        self._blobs = blobs

    async def cached_extraction(self, key: str) -> dict[str, Any] | None:
        async with self._sessions() as db:
            row = await db.get(ContextExtractionRow, key)
            return None if row is None else dict(row.data)

    async def cache_extraction(self, key: str, data: dict[str, Any]) -> None:
        async with self._sessions.begin() as db:
            await db.merge(ContextExtractionRow(key=key, data=data))

    async def add_document(self, document: Document, original: bytes | None = None) -> None:
        if original is not None and document.sha256:
            await asyncio.to_thread(self._write_blob, document.sha256, original)
        async with self._sessions.begin() as db:
            db.add(_document_row(document))

    async def original(self, sha256: str) -> bytes | None:
        path = self._blobs / sha256[:2] / sha256
        if len(sha256) != 64 or not all(c in "0123456789abcdef" for c in sha256):
            return None  # never build a path from anything but a stored digest
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError:
            return None

    async def documents(self, ids: list[str]) -> list[Document]:
        async with self._sessions() as db:
            rows = (await db.scalars(select(DocumentRow).where(DocumentRow.id.in_(ids)))).all()
        by_id = {r.id: _document(r) for r in rows}
        return [by_id[i] for i in dict.fromkeys(ids) if i in by_id]

    async def profiles(self) -> list[Profile]:
        async with self._sessions() as db:
            rows = (
                await db.scalars(
                    select(ProfileRow)
                    .options(selectinload(ProfileRow.resources))
                    .order_by(ProfileRow.updated_at.desc())
                )
            ).all()
            return [await self._profile(db, r) for r in rows]

    async def profile(self, profile_id: str) -> Profile | None:
        async with self._sessions() as db:
            row = await db.get(ProfileRow, profile_id, options=[selectinload(ProfileRow.resources)])
            return None if row is None else await self._profile(db, row)

    async def save_profile(self, profile: Profile) -> None:
        async with self._sessions.begin() as db:
            row = await db.get(ProfileRow, profile.id, options=[selectinload(ProfileRow.resources)])
            if row is None:
                row = ProfileRow(id=profile.id, resources=[])
                db.add(row)
            row.name = profile.name
            row.created_at = profile.created_at
            row.updated_at = profile.updated_at
            row.cv_document_id = profile.cv.id if profile.cv else None
            row.job_offer_document_id = profile.job_offer.id if profile.job_offer else None
            row.resources.clear()
            await db.flush()
            row.resources.extend(
                ProfileResourceRow(profile_id=profile.id, position=n, document_id=d.id)
                for n, d in enumerate(profile.resources)
            )

    async def delete_profile(self, profile_id: str) -> bool:
        async with self._sessions.begin() as db:
            row = await db.get(ProfileRow, profile_id)
            if row is None:
                return False
            candidates = {row.cv_document_id, row.job_offer_document_id}
            candidates |= set(
                (
                    await db.scalars(
                        select(ProfileResourceRow.document_id).where(
                            ProfileResourceRow.profile_id == profile_id
                        )
                    )
                ).all()
            )
            await db.delete(row)
            await db.flush()
            # Preparations still analysing stay: their job would otherwise fail.
            preparations = (
                await db.scalars(
                    select(PreparationRow).where(
                        PreparationRow.profile_id == profile_id,
                        PreparationRow.status != PreparationStatus.ANALYSING.value,
                    )
                )
            ).all()
            approved = {p.snapshot_id for p in preparations if p.snapshot_id}
            used = await _snapshots_in_use(db, approved)
            doomed = [p for p in preparations if p.snapshot_id is None or p.snapshot_id not in used]
            candidates |= await _drop_preparations(db, doomed)
            candidates |= await _drop_snapshots(db, {p.snapshot_id for p in doomed} - {None})
            hashes = await _drop_documents(db, candidates)
        await asyncio.to_thread(self._drop_blobs, hashes)
        return True

    async def discard_snapshot(self, snapshot_id: str) -> bool:
        async with self._sessions.begin() as db:
            if await db.get(SnapshotRow, snapshot_id) is None:
                return False
            if await _snapshots_in_use(db, {snapshot_id}):
                return False
            preparations = (
                await db.scalars(
                    select(PreparationRow).where(PreparationRow.snapshot_id == snapshot_id)
                )
            ).all()
            candidates = await _drop_preparations(db, list(preparations))
            candidates |= await _drop_snapshots(db, {snapshot_id})
            hashes = await _drop_documents(db, candidates)
        await asyncio.to_thread(self._drop_blobs, hashes)
        return True

    async def save_preparation(self, preparation: Preparation) -> None:
        async with self._sessions.begin() as db:
            row = await db.get(PreparationRow, preparation.id)
            if row is None:
                row = PreparationRow(id=preparation.id)
                db.add(row)
            row.created_at = preparation.created_at
            row.language = preparation.language
            row.job_mode = preparation.job_mode.value
            row.status = preparation.status.value
            row.document_ids = [d.id for d in preparation.documents]
            row.facts = [fact_to_json(f) for f in preparation.facts]
            row.matches = [match_to_json(m) for m in preparation.matches]
            row.area = area_to_json(preparation.area)
            row.role_profile = (
                asdict(preparation.role_profile) if preparation.role_profile else None
            )
            row.vocabulary = list(preparation.vocabulary)
            row.error = preparation.error
            row.profile_id = preparation.profile_id
            row.snapshot_id = preparation.snapshot_id
            row.execution_profile = preparation.execution_profile

    async def preparation(self, preparation_id: str) -> Preparation | None:
        async with self._sessions() as db:
            row = await db.get(PreparationRow, preparation_id)
        if row is None:
            return None
        documents = await self.documents(list(row.document_ids))
        return Preparation(
            id=row.id,
            created_at=row.created_at,
            language=row.language,
            job_mode=JobMode(row.job_mode),
            documents=documents,
            status=PreparationStatus(row.status),
            facts=[fact_from_json(f) for f in row.facts],
            matches=[match_from_json(m) for m in row.matches],
            area=area_from_json(row.area),
            role_profile=role_from_json(row.role_profile),
            vocabulary=tuple(row.vocabulary),
            error=row.error,
            profile_id=row.profile_id,
            snapshot_id=row.snapshot_id,
            execution_profile=row.execution_profile,
        )

    async def save_snapshot(self, snapshot: ContextSnapshot) -> None:
        data = {
            "language": snapshot.language,
            "job_mode": snapshot.job_mode.value,
            "candidate_facts": [fact_to_json(f) for f in snapshot.candidate_facts],
            "job_facts": [fact_to_json(f) for f in snapshot.job_facts],
            "matches": [match_to_json(m) for m in snapshot.matches],
            "area": area_to_json(snapshot.area),
            "role_profile": asdict(snapshot.role_profile) if snapshot.role_profile else None,
            "vocabulary": list(snapshot.vocabulary),
            "document_ids": [d.id for d in snapshot.documents],
        }
        async with self._sessions.begin() as db:
            db.add(
                SnapshotRow(
                    id=snapshot.id,
                    preparation_id=snapshot.preparation_id,
                    created_at=snapshot.created_at,
                    content_hash=snapshot.content_hash,
                    data=data,
                )
            )

    async def snapshot(self, snapshot_id: str) -> ContextSnapshot | None:
        async with self._sessions() as db:
            row = await db.get(SnapshotRow, snapshot_id)
        return None if row is None else await self._snapshot(row)

    async def snapshot_by_hash(self, content_hash: str) -> ContextSnapshot | None:
        async with self._sessions() as db:
            row = await db.scalar(
                select(SnapshotRow).where(SnapshotRow.content_hash == content_hash)
            )
        return None if row is None else await self._snapshot(row)

    # ------------------------------------------------------------------ internals

    def _write_blob(self, sha256: str, data: bytes) -> None:
        path = self._blobs / sha256[:2] / sha256
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(path, data)

    def _drop_blobs(self, hashes: set[str]) -> None:
        for sha256 in hashes:
            if len(sha256) == 64 and all(c in "0123456789abcdef" for c in sha256):
                (self._blobs / sha256[:2] / sha256).unlink(missing_ok=True)

    async def _profile(self, db: AsyncSession, row: ProfileRow) -> Profile:
        ids = [r.document_id for r in row.resources]
        wanted = [*ids, row.cv_document_id, row.job_offer_document_id]
        documents = (
            await db.scalars(
                select(DocumentRow).where(DocumentRow.id.in_([i for i in wanted if i]))
            )
        ).all()
        by_id = {d.id: _document(d) for d in documents}
        return Profile(
            id=row.id,
            name=row.name,
            resources=tuple(by_id[i] for i in ids if i in by_id),
            created_at=row.created_at,
            updated_at=row.updated_at,
            cv=by_id.get(row.cv_document_id) if row.cv_document_id else None,
            job_offer=(by_id.get(row.job_offer_document_id) if row.job_offer_document_id else None),
        )

    async def _snapshot(self, row: SnapshotRow) -> ContextSnapshot:
        data = row.data
        return ContextSnapshot(
            id=row.id,
            preparation_id=row.preparation_id,
            created_at=row.created_at,
            language=data["language"],
            job_mode=JobMode(data["job_mode"]),
            candidate_facts=tuple(fact_from_json(f) for f in data["candidate_facts"]),
            job_facts=tuple(fact_from_json(f) for f in data["job_facts"]),
            matches=tuple(match_from_json(m) for m in data["matches"]),
            area=area_from_json(data["area"]),
            role_profile=role_from_json(data.get("role_profile")),
            vocabulary=tuple(data["vocabulary"]),
            documents=tuple(await self.documents(list(data["document_ids"]))),
            content_hash=row.content_hash,
        )


# ---------------------------------------------------------------------- cleanup

PENDING_JOBS = ("queued", "running")


async def _snapshots_in_use(db: AsyncSession, snapshot_ids: set[str]) -> set[str]:
    """The contexts an interview, a report or a pending job refers to."""
    if not snapshot_ids:
        return set()
    wanted = list(snapshot_ids)
    used = set(
        (
            await db.scalars(
                select(SessionRow.snapshot_id).where(SessionRow.snapshot_id.in_(wanted))
            )
        ).all()
    )
    used |= set(
        (
            await db.scalars(select(ReportRow.snapshot_id).where(ReportRow.snapshot_id.in_(wanted)))
        ).all()
    )
    used |= set(
        (
            await db.scalars(
                select(JobRow.subject_id).where(
                    JobRow.subject_id.in_(wanted), JobRow.status.in_(PENDING_JOBS)
                )
            )
        ).all()
    )
    return {s for s in used if s}


async def _drop_preparations(db: AsyncSession, rows: list[PreparationRow]) -> set[str | None]:
    """Delete preparations with their jobs; returns the documents they used."""
    if not rows:
        return set()
    ids = [p.id for p in rows]
    documents: set[str | None] = {d for p in rows for d in p.document_ids}
    await db.execute(delete(JobRow).where(JobRow.subject_id.in_(ids)))
    await db.execute(delete(PreparationRow).where(PreparationRow.id.in_(ids)))
    return documents


async def _drop_snapshots(db: AsyncSession, snapshot_ids: set[str | None]) -> set[str | None]:
    """Delete the contexts that no interview, report, pending job or remaining preparation
    refers to; returns the documents they used."""
    wanted = {s for s in snapshot_ids if s}
    unused = wanted - await _snapshots_in_use(db, wanted)
    if unused:
        unused -= set(
            (
                await db.scalars(
                    select(PreparationRow.snapshot_id).where(
                        PreparationRow.snapshot_id.in_(list(unused))
                    )
                )
            ).all()
        )
    if not unused:
        return set()
    rows = (await db.scalars(select(SnapshotRow).where(SnapshotRow.id.in_(list(unused))))).all()
    documents: set[str | None] = {d for r in rows for d in r.data.get("document_ids", [])}
    await db.execute(delete(SnapshotRow).where(SnapshotRow.id.in_(list(unused))))
    return documents


async def _drop_documents(db: AsyncSession, candidates: set[str | None]) -> set[str]:
    """Delete the candidate documents nothing refers to, with the earlier documents of the same
    uploaded file (an edited text keeps its original). Newer uploads of that file may belong to
    work in progress and stay. Returns the hashes of files no document uses any more."""
    wanted = [c for c in candidates if c]
    if not wanted:
        return set()
    rows = list((await db.scalars(select(DocumentRow).where(DocumentRow.id.in_(wanted)))).all())
    newest: dict[str, float] = {}
    for row in rows:
        if row.sha256:
            newest[row.sha256] = max(newest.get(row.sha256, row.created_at), row.created_at)
    if newest:
        rows += (
            await db.scalars(
                select(DocumentRow).where(
                    DocumentRow.sha256.in_(list(newest)), DocumentRow.id.not_in(wanted)
                )
            )
        ).all()
    rows = [r for r in rows if not r.sha256 or r.created_at <= newest[r.sha256]]
    referenced = await _referenced_documents(db)
    doomed = {r.id: r.sha256 for r in rows if r.id not in referenced}
    if not doomed:
        return set()
    await db.execute(delete(DocumentRow).where(DocumentRow.id.in_(list(doomed))))
    hashes = {h for h in doomed.values() if h}
    if hashes:
        hashes -= set(
            (
                await db.scalars(
                    select(DocumentRow.sha256).where(DocumentRow.sha256.in_(list(hashes)))
                )
            ).all()
        )
    return {h for h in hashes if h}


async def _referenced_documents(db: AsyncSession) -> set[str]:
    referenced: set[str] = set()
    for cv, offer in (
        await db.execute(select(ProfileRow.cv_document_id, ProfileRow.job_offer_document_id))
    ).all():
        referenced |= {d for d in (cv, offer) if d}
    referenced |= set((await db.scalars(select(ProfileResourceRow.document_id))).all())
    for ids in (await db.scalars(select(PreparationRow.document_ids))).all():
        referenced |= set(ids)
    for data in (await db.scalars(select(SnapshotRow.data))).all():
        referenced |= set(data.get("document_ids", []))
    return referenced


# ---------------------------------------------------------------------- mapping


def role_from_json(data: dict[str, Any] | None) -> RoleProfile | None:
    if data is None:
        return None
    return RoleProfile(
        profession=data["profession"],
        target_role=data["target_role"],
        seniority=data["seniority"],
        responsibilities=tuple(data.get("responsibilities", ())),
        competencies=tuple(data.get("competencies", ())),
        basis_fact_ids=tuple(data.get("basis_fact_ids", ())),
        rationale=data.get("rationale", ""),
        confirmed=data.get("confirmed", False),
    )


def _document_row(d: Document) -> DocumentRow:
    return DocumentRow(
        id=d.id,
        kind=d.kind.value,
        title=d.title,
        origin=d.origin.value,
        text=d.text,
        media_type=d.media_type,
        filename=d.filename,
        sha256=d.sha256,
        warnings=list(d.warnings),
        created_at=d.created_at,
    )


def _document(r: DocumentRow) -> Document:
    return Document(
        id=r.id,
        kind=DocumentKind(r.kind),
        title=r.title,
        origin=DocumentOrigin(r.origin),
        text=r.text,
        created_at=r.created_at,
        media_type=r.media_type,
        filename=r.filename,
        sha256=r.sha256,
        warnings=tuple(r.warnings),
    )


def fact_to_json(f: Fact) -> dict[str, Any]:
    return {
        "id": f.id,
        "subject": f.subject.value,
        "kind": f.kind.value,
        "statement": f.statement,
        "origin": f.origin.value,
        "document_id": f.document_id,
        "quote": f.quote,
        "review": f.review.value,
        "corrected": f.corrected,
    }


def fact_from_json(d: dict[str, Any]) -> Fact:
    return Fact(
        id=d["id"],
        subject=Subject(d["subject"]),
        kind=FactKind(d["kind"]),
        statement=d["statement"],
        origin=FactOrigin(d["origin"]),
        document_id=d["document_id"],
        quote=d["quote"],
        review=Review(d["review"]),
        corrected=d["corrected"],
    )


def match_to_json(m: RequirementMatch) -> dict[str, Any]:
    return {
        "requirement_id": m.requirement_id,
        "status": m.status.value,
        "fact_ids": list(m.fact_ids),
        "rationale": m.rationale,
    }


def match_from_json(d: dict[str, Any]) -> RequirementMatch:
    return RequirementMatch(
        requirement_id=d["requirement_id"],
        status=MatchStatus(d["status"]),
        fact_ids=tuple(d["fact_ids"]),
        rationale=d["rationale"],
    )


def area_to_json(a: TargetArea | None) -> dict[str, Any] | None:
    if a is None:
        return None
    return {
        "area": a.area,
        "seniority": a.seniority,
        "rationale": a.rationale,
        "confirmed": a.confirmed,
    }


def area_from_json(d: dict[str, Any] | None) -> TargetArea | None:
    if d is None:
        return None
    return TargetArea(d["area"], d["seniority"], d["rationale"], d["confirmed"])
