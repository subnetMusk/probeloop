"""Context store on the database. Uploaded files are kept in the blob directory by sha256."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from sqlalchemy import select
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
    Subject,
    TargetArea,
)
from probeloop.storage.database import (
    ContextExtractionRow,
    DocumentRow,
    PreparationRow,
    ProfileResourceRow,
    ProfileRow,
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
            await db.delete(row)
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
            row.vocabulary = list(preparation.vocabulary)
            row.error = preparation.error
            row.profile_id = preparation.profile_id
            row.snapshot_id = preparation.snapshot_id

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
            vocabulary=tuple(row.vocabulary),
            error=row.error,
            profile_id=row.profile_id,
            snapshot_id=row.snapshot_id,
        )

    async def save_snapshot(self, snapshot: ContextSnapshot) -> None:
        data = {
            "language": snapshot.language,
            "job_mode": snapshot.job_mode.value,
            "candidate_facts": [fact_to_json(f) for f in snapshot.candidate_facts],
            "job_facts": [fact_to_json(f) for f in snapshot.job_facts],
            "matches": [match_to_json(m) for m in snapshot.matches],
            "area": area_to_json(snapshot.area),
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
            vocabulary=tuple(data["vocabulary"]),
            documents=tuple(await self.documents(list(data["document_ids"]))),
            content_hash=row.content_hash,
        )


# ---------------------------------------------------------------------- mapping


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
