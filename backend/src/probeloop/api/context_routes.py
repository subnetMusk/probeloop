"""REST endpoints of the context: documents, profiles of resources, analysis and review."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from probeloop.ai.ports import LlmError
from probeloop.ai.profiles import using_profile
from probeloop.api.schemas import JobView, RoleProfileData
from probeloop.context.application.ports import ExtractionError
from probeloop.context.application.service import (
    ANALYSE_JOB,
    ContextNotFoundError,
    ContextService,
    ResourceInput,
)
from probeloop.context.application.snapshots import candidate_brief, job_brief
from probeloop.context.domain.model import (
    MAX_DOCUMENT_CHARS,
    MAX_RESOURCES,
    MAX_TITLE,
    ContextError,
    ContextSnapshot,
    Document,
    DocumentKind,
    Fact,
    FactKind,
    JobMode,
    Preparation,
    Profile,
    Review,
    Subject,
)
from probeloop.platform.jobs import JobRunner

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DocumentView(BaseModel):
    id: str
    kind: str
    title: str
    origin: str
    media_type: str
    filename: str | None
    created_at: float
    has_original: bool  # the uploaded file can be downloaded
    chars: int
    warnings: list[str]
    preview: str

    @classmethod
    def of(cls, d: Document) -> DocumentView:
        return cls(
            id=d.id,
            kind=d.kind.value,
            title=d.title,
            origin=d.origin.value,
            media_type=d.media_type,
            filename=d.filename,
            created_at=d.created_at,
            has_original=d.has_original,
            chars=len(d.text),
            warnings=list(d.warnings),
            preview=d.text[:600],
        )


class TypedDocument(Strict):
    kind: DocumentKind
    title: str = Field(min_length=1, max_length=MAX_TITLE)
    text: str = Field(min_length=1, max_length=MAX_DOCUMENT_CHARS)
    generated: bool = False  # a job offer drafted by the model and edited by the user


class DocumentTextView(BaseModel):
    id: str
    text: str


class DraftRequest(Strict):
    description: str = Field(min_length=10, max_length=3000)
    language: Literal["it", "en"] = "it"
    execution_profile: str | None = Field(default=None, max_length=1024)


class DraftView(BaseModel):
    text: str


class ResourceIn(Strict):
    title: str = Field(max_length=MAX_TITLE)
    document_id: str = Field(max_length=32)


class ProfileIn(Strict):
    name: str = Field(min_length=1, max_length=MAX_TITLE)
    cv_id: str | None = Field(default=None, max_length=32)
    job_offer_id: str | None = Field(default=None, max_length=32)
    resources: list[ResourceIn] = Field(max_length=MAX_RESOURCES)


class ProfileRename(Strict):
    name: str = Field(min_length=1, max_length=MAX_TITLE)


class DocumentRevision(Strict):
    text: str = Field(min_length=1, max_length=MAX_DOCUMENT_CHARS)
    title: str | None = Field(default=None, max_length=MAX_TITLE)


class ProfileView(BaseModel):
    id: str
    name: str
    created_at: float
    updated_at: float
    job_mode: JobMode
    cv: DocumentView | None
    job_offer: DocumentView | None
    resources: list[DocumentView]

    @classmethod
    def of(cls, p: Profile) -> ProfileView:
        return cls(
            id=p.id,
            name=p.name,
            created_at=p.created_at,
            updated_at=p.updated_at,
            job_mode=p.job_mode,
            cv=DocumentView.of(p.cv) if p.cv else None,
            job_offer=DocumentView.of(p.job_offer) if p.job_offer else None,
            resources=[DocumentView.of(d) for d in p.resources],
        )


class PrepareIn(Strict):
    language: Literal["it", "en"] = "it"
    job_mode: JobMode
    cv_id: str | None = Field(default=None, max_length=32)
    job_offer_id: str | None = Field(default=None, max_length=32)
    resources: list[ResourceIn] = Field(default=[], max_length=MAX_RESOURCES)
    profile_id: str | None = Field(default=None, max_length=32)
    execution_profile: str | None = Field(default=None, max_length=1024)


class FactView(BaseModel):
    id: str
    subject: str
    kind: str
    statement: str
    text: str
    origin: str
    document_id: str | None
    quote: str | None
    review: str
    corrected: str | None

    @classmethod
    def of(cls, f: Fact) -> FactView:
        return cls(
            id=f.id,
            subject=f.subject.value,
            kind=f.kind.value,
            statement=f.statement,
            text=f.text,
            origin=f.origin.value,
            document_id=f.document_id,
            quote=f.quote,
            review=f.review.value,
            corrected=f.corrected,
        )


class MatchView(BaseModel):
    requirement_id: str
    status: str
    fact_ids: list[str]
    rationale: str


class AreaView(BaseModel):
    area: str
    seniority: str
    rationale: str
    confirmed: bool


class PreparationView(BaseModel):
    id: str
    status: str
    language: str
    job_mode: str
    documents: list[DocumentView]
    facts: list[FactView]
    matches: list[MatchView]
    area: AreaView | None
    role_profile: RoleProfileData | None = None
    vocabulary: list[str]
    error: str | None
    snapshot_id: str | None
    created_at: float
    profile_id: str | None
    execution_profile: str | None
    analysis: JobView | None

    @classmethod
    def of(cls, p: Preparation, analysis: JobView | None) -> PreparationView:
        area = p.area
        return cls(
            id=p.id,
            status=p.status.value,
            language=p.language,
            job_mode=p.job_mode.value,
            documents=[DocumentView.of(d) for d in p.documents],
            facts=[FactView.of(f) for f in p.facts],
            matches=[
                MatchView(
                    requirement_id=m.requirement_id,
                    status=m.status.value,
                    fact_ids=list(m.fact_ids),
                    rationale=m.rationale,
                )
                for m in p.matches
            ],
            area=(
                AreaView(
                    area=area.area,
                    seniority=area.seniority,
                    rationale=area.rationale,
                    confirmed=area.confirmed,
                )
                if area
                else None
            ),
            vocabulary=list(p.vocabulary),
            error=p.error,
            snapshot_id=p.snapshot_id,
            created_at=p.created_at,
            profile_id=p.profile_id,
            execution_profile=p.execution_profile,
            role_profile=RoleProfileData.of(p.role_profile) if p.role_profile else None,
            analysis=analysis,
        )


class ReviewIn(Strict):
    review: Review
    corrected: str | None = Field(default=None, max_length=400)


class AddFactIn(Strict):
    subject: Subject
    kind: FactKind
    statement: str = Field(min_length=1, max_length=400)


class AreaIn(Strict):
    area: str = Field(min_length=1, max_length=120)
    seniority: str = Field(max_length=40)


class RequirementView(BaseModel):
    """A requirement of the position and how the approved candidate facts cover it."""

    id: str
    kind: Literal["requirement", "nice_to_have"]
    text: str
    status: Literal["met", "partial", "not_shown"]
    supporting: list[str]  # the statements of the candidate facts that support it
    rationale: str


class SnapshotView(BaseModel):
    id: str
    created_at: float
    content_hash: str
    language: str
    job_mode: str
    area: AreaView | None
    role_profile: RoleProfileData | None = None
    documents: list[DocumentView]
    requirements: list[RequirementView]
    candidate_brief: str
    job_brief: str
    vocabulary: list[str]

    @classmethod
    def of(cls, s: ContextSnapshot) -> SnapshotView:
        facts = {f.id: f for f in (*s.candidate_facts, *s.job_facts)}
        requirements = [
            RequirementView(
                id=m.requirement_id,
                kind="nice_to_have"
                if facts[m.requirement_id].kind is FactKind.NICE_TO_HAVE
                else "requirement",
                text=facts[m.requirement_id].text,
                status=m.status.value,
                supporting=[facts[i].text for i in m.fact_ids if i in facts],
                rationale=m.rationale,
            )
            for m in s.matches
            if m.requirement_id in facts
        ]
        area = s.area
        return cls(
            id=s.id,
            created_at=s.created_at,
            content_hash=s.content_hash,
            language=s.language,
            job_mode=s.job_mode.value,
            area=(
                AreaView(
                    area=area.area,
                    seniority=area.seniority,
                    rationale=area.rationale,
                    confirmed=area.confirmed,
                )
                if area
                else None
            ),
            documents=[DocumentView.of(d) for d in s.documents],
            requirements=requirements,
            candidate_brief=candidate_brief(s),
            job_brief=job_brief(s),
            vocabulary=list(s.vocabulary),
            role_profile=RoleProfileData.of(s.role_profile) if s.role_profile else None,
        )


def _resources(items: list[ResourceIn]) -> list[ResourceInput]:
    return [ResourceInput(title=r.title, document_id=r.document_id) for r in items]


def context_router(
    context: ContextService,
    jobs: JobRunner,
    execution: Callable[[str | None], str] = lambda requested: requested or "local",
) -> APIRouter:
    router = APIRouter(prefix="/api")

    async def view(preparation: Preparation) -> PreparationView:
        analyses = [j for j in await jobs.for_subject(preparation.id) if j.kind == ANALYSE_JOB]
        return PreparationView.of(preparation, JobView.of(analyses[-1]) if analyses else None)

    @router.post("/documents", status_code=201)
    async def upload_document(
        kind: Annotated[DocumentKind, Form()],
        title: Annotated[str, Form(min_length=1, max_length=MAX_TITLE)],
        file: Annotated[UploadFile, File()],
    ) -> DocumentView:
        """A CV, job offer or resource as a file: txt, md, json, xml, html, docx or pdf."""
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="the file is larger than 10 MB")
        try:
            document = await context.upload(kind, title, file.filename or "file.txt", data)
        except (ExtractionError, ContextError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return DocumentView.of(document)

    @router.post("/documents/text", status_code=201)
    async def typed_document(body: TypedDocument) -> DocumentView:
        try:
            document = await context.typed(
                body.kind, body.title, body.text, generated=body.generated
            )
        except ContextError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return DocumentView.of(document)

    @router.get("/documents/{document_id}")
    async def document_text(document_id: str) -> DocumentTextView:
        try:
            document = await context.document(document_id)
        except ContextNotFoundError as exc:
            raise HTTPException(status_code=404, detail="document not found") from exc
        return DocumentTextView(id=document.id, text=document.text)

    @router.post("/job-offers/draft")
    async def draft_job_offer(body: DraftRequest) -> DraftView:
        """A plausible job offer written from a short description, for the user to edit."""
        try:
            with using_profile(execution(body.execution_profile)):
                text = await context.draft_job_offer(body.description, body.language)
            return DraftView(text=text)
        except ContextError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except LlmError as exc:
            raise HTTPException(
                status_code=503, detail="the job offer could not be drafted; try again"
            ) from exc

    @router.get("/profiles")
    async def list_profiles() -> list[ProfileView]:
        return [ProfileView.of(p) for p in await context.profiles()]

    @router.post("/profiles", status_code=201)
    async def create_profile(body: ProfileIn) -> ProfileView:
        try:
            return ProfileView.of(
                await context.save_profile(
                    body.name,
                    _resources(body.resources),
                    cv_id=body.cv_id,
                    job_offer_id=body.job_offer_id,
                )
            )
        except ContextNotFoundError as exc:
            raise HTTPException(status_code=404, detail="document not found") from exc
        except ContextError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.put("/profiles/{profile_id}")
    async def overwrite_profile(profile_id: str, body: ProfileIn) -> ProfileView:
        try:
            profile = await context.save_profile(
                body.name,
                _resources(body.resources),
                profile_id=profile_id,
                cv_id=body.cv_id,
                job_offer_id=body.job_offer_id,
            )
        except ContextNotFoundError as exc:
            raise HTTPException(status_code=404, detail="not found") from exc
        except ContextError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return ProfileView.of(profile)

    @router.patch("/profiles/{profile_id}")
    async def rename_profile(profile_id: str, body: ProfileRename) -> ProfileView:
        try:
            return ProfileView.of(await context.rename_profile(profile_id, body.name))
        except ContextNotFoundError as exc:
            raise HTTPException(status_code=404, detail="profile not found") from exc
        except ContextError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("/documents/{document_id}/original")
    async def document_original(document_id: str) -> Response:
        """The uploaded file, or the text of a typed document. Only PDFs are shown inline: other
        types, HTML included, are always downloaded so they never run on the app's origin."""
        try:
            document, data = await context.original(document_id)
        except ContextNotFoundError as exc:
            raise HTTPException(status_code=404, detail="document not found") from exc
        if document.has_original:
            if data is None:
                raise HTTPException(status_code=404, detail="original file not available")
            inline = document.media_type == "application/pdf"
            return Response(
                data,
                media_type=document.media_type,
                headers=_file_headers(document.filename or document.title, inline=inline),
            )
        return Response(
            document.text.encode(),
            media_type="text/plain; charset=utf-8",
            headers=_file_headers(f"{document.title}.txt", inline=False),
        )

    @router.post("/documents/{document_id}/revisions", status_code=201)
    async def revise_document(document_id: str, body: DocumentRevision) -> DocumentView:
        try:
            return DocumentView.of(
                await context.revise_document(document_id, body.text, body.title)
            )
        except ContextNotFoundError as exc:
            raise HTTPException(status_code=404, detail="document not found") from exc
        except ContextError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.delete("/profiles/{profile_id}", status_code=204)
    async def delete_profile(profile_id: str) -> None:
        try:
            await context.delete_profile(profile_id)
        except ContextNotFoundError as exc:
            raise HTTPException(status_code=404, detail="profile not found") from exc

    @router.post("/preparations", status_code=202)
    async def prepare(body: PrepareIn) -> PreparationView:
        """Analyse the documents of an interview; poll the preparation until it is in review."""
        try:
            preparation = await context.prepare(
                language=body.language,
                job_mode=body.job_mode,
                cv_id=body.cv_id,
                job_offer_id=body.job_offer_id,
                resources=_resources(body.resources),
                profile_id=body.profile_id,
                execution_profile=execution(body.execution_profile),
            )
        except ContextNotFoundError as exc:
            raise HTTPException(status_code=404, detail="document not found") from exc
        except ContextError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return await view(preparation)

    @router.get("/preparations/{preparation_id}")
    async def get_preparation(preparation_id: str) -> PreparationView:
        try:
            return await view(await context.preparation(preparation_id))
        except ContextNotFoundError as exc:
            raise HTTPException(status_code=404, detail="not found") from exc

    @router.put("/preparations/{preparation_id}/facts/{fact_id}")
    async def review_fact(preparation_id: str, fact_id: str, body: ReviewIn) -> PreparationView:
        try:
            preparation = await context.review_fact(
                preparation_id, fact_id, body.review, body.corrected
            )
        except ContextNotFoundError as exc:
            raise HTTPException(status_code=404, detail="not found") from exc
        except ContextError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return await view(preparation)

    @router.post("/preparations/{preparation_id}/facts", status_code=201)
    async def add_fact(preparation_id: str, body: AddFactIn) -> PreparationView:
        try:
            preparation = await context.add_fact(
                preparation_id, body.subject, body.kind, body.statement
            )
        except ContextNotFoundError as exc:
            raise HTTPException(status_code=404, detail="not found") from exc
        except ContextError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return await view(preparation)

    @router.put("/preparations/{preparation_id}/area")
    async def set_area(preparation_id: str, body: AreaIn) -> PreparationView:
        try:
            preparation = await context.set_area(preparation_id, body.area, body.seniority)
        except ContextNotFoundError as exc:
            raise HTTPException(status_code=404, detail="not found") from exc
        except ContextError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return await view(preparation)

    @router.put("/preparations/{preparation_id}/role-profile")
    async def set_role_profile(preparation_id: str, body: RoleProfileData) -> PreparationView:
        try:
            preparation = await context.set_role_profile(preparation_id, body.domain())
            return await view(preparation)
        except ContextNotFoundError as exc:
            raise HTTPException(404, "preparation not found") from exc
        except ContextError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.post("/preparations/{preparation_id}/approve")
    async def approve(preparation_id: str) -> SnapshotView:
        try:
            return SnapshotView.of(await context.approve(preparation_id))
        except ContextNotFoundError as exc:
            raise HTTPException(status_code=404, detail="not found") from exc
        except ContextError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/preparations/{preparation_id}/reopen")
    async def reopen(preparation_id: str) -> PreparationView:
        """Return an approved context to the review; approve it again to continue."""
        try:
            return await view(await context.reopen(preparation_id))
        except ContextNotFoundError as exc:
            raise HTTPException(status_code=404, detail="not found") from exc
        except ContextError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("/snapshots/{snapshot_id}")
    async def get_snapshot(snapshot_id: str) -> SnapshotView:
        try:
            return SnapshotView.of(await context.snapshot(snapshot_id))
        except ContextNotFoundError as exc:
            raise HTTPException(status_code=404, detail="not found") from exc

    return router


def _file_headers(filename: str, *, inline: bool) -> dict[str, str]:
    """Download headers with an ASCII fallback name and the UTF-8 name (RFC 6266 and 5987)."""
    fallback = "".join(
        c if c.isascii() and c.isprintable() and c not in '"\\' else "_" for c in filename
    )
    disposition = "inline" if inline else "attachment"
    return {
        "Content-Disposition": (
            f"{disposition}; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}"
        ),
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-cache",
    }
