"""Use cases of the context: documents, profiles of resources, the analysis and its review."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePath
from typing import Any

from probeloop.ai.ports import UserActionRequiredError
from probeloop.context.application.analysis import ContextAnalyser
from probeloop.context.application.ports import ContextStore, ExtractedText, TextExtraction
from probeloop.context.application.snapshots import snapshot_of
from probeloop.context.domain.model import (
    ContextError,
    ContextSnapshot,
    Document,
    DocumentKind,
    DocumentOrigin,
    Fact,
    FactKind,
    FactOrigin,
    JobMode,
    Preparation,
    PreparationStatus,
    Profile,
    Review,
    RoleProfile,
    Subject,
)
from probeloop.platform.jobs import Job, JobError, Progress

logger = logging.getLogger(__name__)

ANALYSE_JOB = "analyse_context"


class ContextNotFoundError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class ResourceInput:
    """A resource of the resource screen: a title and an uploaded or typed document."""

    title: str
    document_id: str


class ContextService:
    def __init__(
        self,
        *,
        store: ContextStore,
        analyser: ContextAnalyser,
        extractor: TextExtraction,
        submit: Callable[[str, str, Mapping[str, Any] | None], Awaitable[Job]],
        now: Callable[[], float],
        new_id: Callable[[], str],
    ) -> None:
        self._store = store
        self._analyser = analyser
        self._extractor = extractor
        self._submit = submit
        self._now = now
        self._new_id = new_id

    # ------------------------------------------------------------------ documents

    async def document(self, document_id: str) -> Document:
        (document,) = await self._documents([document_id])
        return document

    async def original(self, document_id: str) -> tuple[Document, bytes | None]:
        """A document with the bytes of its uploaded file, or None when it has no stored file."""
        document = await self.document(document_id)
        if not document.has_original or document.sha256 is None:
            return document, None
        return document, await self._store.original(document.sha256)

    async def upload(self, kind: DocumentKind, title: str, filename: str, data: bytes) -> Document:
        key = hashlib.sha256(
            b"text.v1\0" + PurePath(filename).suffix.lower().encode() + b"\0" + data
        ).hexdigest()
        cached = await self._store.cached_extraction(key)
        if cached is None:
            extracted = await self._extractor.extract(data, filename)
            await self._store.cache_extraction(
                key,
                {
                    "text": extracted.text,
                    "media_type": extracted.media_type,
                    "warnings": list(extracted.warnings),
                },
            )
        else:
            extracted = ExtractedText(
                cached["text"], cached["media_type"], tuple(cached["warnings"])
            )
        document = Document(
            id=self._new_id(),
            kind=kind,
            title=title.strip(),
            origin=DocumentOrigin.UPLOAD,
            text=extracted.text,
            created_at=self._now(),
            media_type=extracted.media_type,
            filename=filename,
            sha256=hashlib.sha256(data).hexdigest(),
            warnings=extracted.warnings,
        )
        await self._store.add_document(document, data)
        return document

    async def typed(
        self, kind: DocumentKind, title: str, text: str, *, generated: bool = False
    ) -> Document:
        if generated and kind is not DocumentKind.JOB_OFFER:
            raise ContextError("only job offers can be generated")
        document = Document(
            id=self._new_id(),
            kind=kind,
            title=title.strip(),
            origin=DocumentOrigin.GENERATED if generated else DocumentOrigin.TYPED,
            text=text.strip(),
            created_at=self._now(),
        )
        await self._store.add_document(document)
        return document

    async def draft_job_offer(self, description: str, language: str) -> str:
        if len(description.strip()) < 10:
            raise ContextError("describe the position in a few words first")
        return await self._analyser.draft_job_offer(description.strip(), language)

    # ------------------------------------------------------------------ profiles

    async def profiles(self) -> list[Profile]:
        return await self._store.profiles()

    async def profile(self, profile_id: str) -> Profile:
        profile = await self._store.profile(profile_id)
        if profile is None:
            raise ContextNotFoundError(profile_id)
        return profile

    async def save_profile(
        self,
        name: str,
        resources: Sequence[ResourceInput],
        profile_id: str | None = None,
        *,
        cv_id: str | None = None,
        job_offer_id: str | None = None,
    ) -> Profile:
        """Create a profile, or overwrite an existing one, with these documents."""
        documents = await self._resources(resources)
        cv = await self._document_of_kind(cv_id, DocumentKind.CV)
        job_offer = await self._document_of_kind(job_offer_id, DocumentKind.JOB_OFFER)
        now = self._now()
        created = now
        if profile_id is not None:
            created = (await self.profile(profile_id)).created_at
        profile = Profile(
            id=profile_id or self._new_id(),
            name=name.strip(),
            resources=tuple(documents),
            created_at=created,
            updated_at=now,
            cv=cv,
            job_offer=job_offer,
        )
        await self._store.save_profile(profile)
        return profile

    async def rename_profile(self, profile_id: str, name: str) -> Profile:
        profile = (await self.profile(profile_id)).renamed(name, self._now())
        await self._store.save_profile(profile)
        return profile

    async def revise_document(self, document_id: str, text: str, title: str | None) -> Document:
        """Save edited text as a new document; the edited one stays unchanged."""
        document = (await self.document(document_id)).revised(
            self._new_id(), text, title, self._now()
        )
        await self._store.add_document(document)
        return document

    async def _document_of_kind(
        self, document_id: str | None, kind: DocumentKind
    ) -> Document | None:
        if document_id is None:
            return None
        document = await self.document(document_id)
        if document.kind is not kind:
            raise ContextError(f"document {document_id} is not a {kind.value}")
        return document

    async def delete_profile(self, profile_id: str) -> None:
        if not await self._store.delete_profile(profile_id):
            raise ContextNotFoundError(profile_id)

    # ------------------------------------------------------------------ preparation

    async def prepare(
        self,
        *,
        language: str,
        job_mode: JobMode,
        cv_id: str | None,
        job_offer_id: str | None,
        resources: Sequence[ResourceInput],
        profile_id: str | None = None,
        execution_profile: str | None = None,
    ) -> Preparation:
        documents: list[Document] = []
        for document_id, kind in ((cv_id, DocumentKind.CV), (job_offer_id, DocumentKind.JOB_OFFER)):
            if document_id is None:
                continue
            (document,) = await self._documents([document_id])
            if document.kind is not kind:
                raise ContextError(f"document {document_id} is not a {kind.value}")
            documents.append(document)
        documents += await self._resources(resources)
        preparation = Preparation(
            id=self._new_id(),
            created_at=self._now(),
            language=language,
            job_mode=job_mode,
            documents=documents,
            profile_id=profile_id,
            execution_profile=execution_profile,
            role_profile=RoleProfile(),
        )
        if not documents:
            preparation.analysed([], [], None, ())
        await self._store.save_preparation(preparation)
        payload = {"execution": execution_profile} if execution_profile else None
        if documents:
            await self._submit(ANALYSE_JOB, preparation.id, payload)
        return preparation

    async def preparation(self, preparation_id: str) -> Preparation:
        preparation = await self._store.preparation(preparation_id)
        if preparation is None:
            raise ContextNotFoundError(preparation_id)
        return preparation

    async def analyse(self, job: Job, progress: Progress) -> Mapping[str, Any]:
        """Job handler: read the documents and fill the preparation for review."""
        preparation = await self.preparation(job.subject_id)
        if preparation.status is not PreparationStatus.ANALYSING:
            return {"skipped": preparation.status.value}

        async def report(fraction: float, message: str) -> None:
            await progress(fraction, message)

        try:
            result = await self._analyser.analyse(
                preparation.documents, preparation.job_mode, preparation.language, report
            )
            role_profile = await self._analyser.propose_role(result.facts, preparation.language)
        except Exception as exc:
            logger.error(
                "context analysis failed",
                extra={"preparation_id": preparation.id, "error_type": type(exc).__name__},
            )
            # A provider refusal the user can resolve (sign-in, usage limit) is shown as is.
            reason = (
                str(exc)
                if isinstance(exc, UserActionRequiredError)
                else "the documents could not be analysed; try again"
            )
            preparation.failed(reason)
            await self._store.save_preparation(preparation)
            raise JobError(
                reason
                if isinstance(exc, UserActionRequiredError)
                else "the documents could not be analysed"
            ) from exc
        preparation.analysed(result.facts, result.matches, result.area, result.vocabulary)
        preparation.role_profile = role_profile
        await self._store.save_preparation(preparation)
        return {
            "facts": len(result.facts),
            "declared": sum(f.origin is FactOrigin.DECLARED for f in result.facts),
            "terms": len(result.vocabulary),
        }

    async def review_fact(
        self, preparation_id: str, fact_id: str, review: Review, corrected: str | None
    ) -> Preparation:
        preparation = await self.preparation(preparation_id)
        preparation.review_fact(fact_id, review, corrected)
        await self._store.save_preparation(preparation)
        return preparation

    async def add_fact(
        self, preparation_id: str, subject: Subject, kind: FactKind, statement: str
    ) -> Preparation:
        if not statement.strip():
            raise ContextError("the statement cannot be empty")
        preparation = await self.preparation(preparation_id)
        preparation.add_fact(
            Fact(
                id=self._new_id()[-12:],
                subject=subject,
                kind=kind,
                statement=" ".join(statement.split()),
                origin=FactOrigin.USER,
                review=Review.CONFIRMED,
            )
        )
        await self._store.save_preparation(preparation)
        return preparation

    async def set_area(self, preparation_id: str, area: str, seniority: str) -> Preparation:
        preparation = await self.preparation(preparation_id)
        preparation.set_area(area, seniority)
        await self._store.save_preparation(preparation)
        return preparation

    async def approve(self, preparation_id: str) -> ContextSnapshot:
        """Freeze the reviewed context. Identical content reuses the earlier snapshot."""
        preparation = await self.preparation(preparation_id)
        candidate = snapshot_of(preparation, self._new_id(), self._now())
        existing = await self._store.snapshot_by_hash(candidate.content_hash)
        snapshot = existing or candidate
        preparation.approve(snapshot.id)
        if existing is None:
            await self._store.save_snapshot(snapshot)
        await self._store.save_preparation(preparation)
        return snapshot

    async def set_role_profile(self, preparation_id: str, profile: RoleProfile) -> Preparation:
        preparation = await self.preparation(preparation_id)
        preparation.set_role_profile(profile)
        await self._store.save_preparation(preparation)
        return preparation

    async def reopen(self, preparation_id: str) -> Preparation:
        preparation = await self.preparation(preparation_id)
        preparation.reopen()
        await self._store.save_preparation(preparation)
        return preparation

    async def snapshot(self, snapshot_id: str) -> ContextSnapshot:
        snapshot = await self._store.snapshot(snapshot_id)
        if snapshot is None:
            raise ContextNotFoundError(snapshot_id)
        return snapshot

    # ------------------------------------------------------------------ internals

    async def _documents(self, ids: list[str]) -> list[Document]:
        documents = await self._store.documents(ids)
        if len(documents) != len(set(ids)):
            raise ContextNotFoundError("document")
        return documents

    async def _resources(self, resources: Sequence[ResourceInput]) -> list[Document]:
        """The resources, each with the title chosen on the resource screen."""
        if not resources:
            return []
        documents = {d.id: d for d in await self._documents([r.document_id for r in resources])}
        out = []
        for resource in resources:
            document = documents[resource.document_id]
            if document.kind is not DocumentKind.RESOURCE:
                raise ContextError(f"'{document.title}' is not a resource")
            title = resource.title.strip() or document.title
            if title != document.title:
                document = Document(
                    id=self._new_id(),
                    kind=document.kind,
                    title=title,
                    origin=document.origin,
                    text=document.text,
                    created_at=self._now(),
                    media_type=document.media_type,
                    filename=document.filename,
                    sha256=document.sha256,
                    warnings=document.warnings,
                )
                await self._store.add_document(document)
            out.append(document)
        return out
