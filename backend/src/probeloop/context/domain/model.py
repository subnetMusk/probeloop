"""What is known about the candidate and the position before the interview.

The user provides documents: a CV, a job offer (uploaded, typed, or drafted by the model from a
description) and any number of titled resources. The analysis turns them into facts, each with
a quote from its document; a fact whose quote is found in the document is *declared*, any other
fact is *inferred*. The user reviews the facts, and approval freezes them into an immutable
snapshot that feeds the interviewer, the CV review and the evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum

MAX_TITLE = 120
MAX_DOCUMENT_CHARS = 60_000
MAX_RESOURCES = 20


class ContextError(ValueError):
    """A request that breaks a rule of the context, with a message the user can read."""


class DocumentKind(StrEnum):
    CV = "cv"
    JOB_OFFER = "job_offer"
    RESOURCE = "resource"


class DocumentOrigin(StrEnum):
    UPLOAD = "upload"  # a file
    TYPED = "typed"  # text typed or pasted by the user
    GENERATED = "generated"  # a job offer drafted by the model from the user's description
    # Text extracted from an uploaded file, then edited by the user. The original file stays
    # available: filename, media type and sha256 are kept.
    EDITED = "edited"


@dataclass(frozen=True, slots=True)
class Document:
    id: str
    kind: DocumentKind
    title: str
    origin: DocumentOrigin
    text: str
    created_at: float
    media_type: str = "text/plain"
    filename: str | None = None
    sha256: str | None = None  # of the uploaded file
    warnings: tuple[str, ...] = ()  # for example hidden text found in a PDF

    def __post_init__(self) -> None:
        if not self.title.strip() or len(self.title) > MAX_TITLE:
            raise ContextError(f"a title needs 1 to {MAX_TITLE} characters")
        if not self.text.strip():
            raise ContextError(f"'{self.title}' contains no text")
        if len(self.text) > MAX_DOCUMENT_CHARS:
            raise ContextError(f"'{self.title}' is longer than {MAX_DOCUMENT_CHARS} characters")

    @property
    def has_original(self) -> bool:
        """Whether the uploaded file behind this text is stored."""
        return self.sha256 is not None and self.origin in (
            DocumentOrigin.UPLOAD,
            DocumentOrigin.EDITED,
        )

    def revised(self, document_id: str, text: str, title: str | None, now: float) -> Document:
        """A new document with edited text. Documents are immutable: preparations and
        snapshots that used this one keep it."""
        origin = DocumentOrigin.EDITED if self.has_original else self.origin
        return Document(
            id=document_id,
            kind=self.kind,
            title=(title or self.title).strip(),
            origin=origin,
            text=text.strip(),
            created_at=now,
            media_type=self.media_type if self.has_original else "text/plain",
            filename=self.filename if self.has_original else None,
            sha256=self.sha256 if self.has_original else None,
        )


class Subject(StrEnum):
    CANDIDATE = "candidate"
    JOB = "job"


class FactKind(StrEnum):
    # About the candidate
    ROLE = "role"
    PROJECT = "project"
    SKILL = "skill"
    ACHIEVEMENT = "achievement"
    EDUCATION = "education"
    CERTIFICATION = "certification"
    LANGUAGE = "language"
    OTHER = "other"
    # About the position
    REQUIREMENT = "requirement"
    NICE_TO_HAVE = "nice_to_have"
    RESPONSIBILITY = "responsibility"
    COMPANY = "company"


class FactOrigin(StrEnum):
    DECLARED = "declared"  # the quote was found in the document
    INFERRED = "inferred"  # no verified quote: the model's reading, to be checked
    USER = "user"  # added by the user during the review


class Review(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CORRECTED = "corrected"
    EXCLUDED = "excluded"


@dataclass(frozen=True, slots=True)
class Fact:
    id: str
    subject: Subject
    kind: FactKind
    statement: str
    origin: FactOrigin
    document_id: str | None = None
    quote: str | None = None
    review: Review = Review.PENDING
    corrected: str | None = None  # the user's wording, when the review corrected the statement

    @property
    def text(self) -> str:
        return (
            self.corrected if self.review is Review.CORRECTED and self.corrected else self.statement
        )

    @property
    def included(self) -> bool:
        return self.review is not Review.EXCLUDED


class MatchStatus(StrEnum):
    MET = "met"
    PARTIAL = "partial"
    NOT_SHOWN = "not_shown"


@dataclass(frozen=True, slots=True)
class RequirementMatch:
    requirement_id: str
    status: MatchStatus
    fact_ids: tuple[str, ...] = ()
    rationale: str = ""


@dataclass(frozen=True, slots=True)
class TargetArea:
    """Without a job offer: the professional area and level inferred from the CV."""

    area: str
    seniority: str
    rationale: str = ""
    confirmed: bool = False


class JobMode(StrEnum):
    OFFER = "offer"  # a real job offer, uploaded or pasted
    GENERATED = "generated"  # drafted by the model from the user's description, then edited
    NONE = "none"  # a getting-to-know interview for the area inferred from the CV


class PreparationStatus(StrEnum):
    ANALYSING = "analysing"
    REVIEW = "review"  # the facts wait for the user
    APPROVED = "approved"
    FAILED = "failed"


@dataclass
class Preparation:
    """The documents of one interview setup, their analysis and its review."""

    id: str
    created_at: float
    language: str
    job_mode: JobMode
    documents: list[Document]
    status: PreparationStatus = PreparationStatus.ANALYSING
    facts: list[Fact] = field(default_factory=list)
    matches: list[RequirementMatch] = field(default_factory=list)
    area: TargetArea | None = None
    vocabulary: tuple[str, ...] = ()
    error: str | None = None
    profile_id: str | None = None
    snapshot_id: str | None = None

    def __post_init__(self) -> None:
        kinds = [d.kind for d in self.documents]
        if kinds.count(DocumentKind.CV) > 1 or kinds.count(DocumentKind.JOB_OFFER) > 1:
            raise ContextError("at most one CV and one job offer")
        if kinds.count(DocumentKind.RESOURCE) > MAX_RESOURCES:
            raise ContextError(f"at most {MAX_RESOURCES} resources")
        if (DocumentKind.JOB_OFFER in kinds) == (self.job_mode is JobMode.NONE):
            raise ContextError("a job offer goes with the 'offer' and 'generated' modes only")
        offer = self.document(DocumentKind.JOB_OFFER)
        if offer and (offer.origin is DocumentOrigin.GENERATED) != (
            self.job_mode is JobMode.GENERATED
        ):
            raise ContextError("a generated job offer must be labelled as generated")

    def document(self, kind: DocumentKind) -> Document | None:
        return next((d for d in self.documents if d.kind is kind), None)

    def fact(self, fact_id: str) -> Fact:
        for fact in self.facts:
            if fact.id == fact_id:
                return fact
        raise ContextError(f"unknown fact {fact_id}")

    def analysed(
        self,
        facts: list[Fact],
        matches: list[RequirementMatch],
        area: TargetArea | None,
        vocabulary: tuple[str, ...],
    ) -> None:
        if self.status is not PreparationStatus.ANALYSING:
            raise ContextError("the analysis is already done")
        self.facts = facts
        self.matches = matches
        self.area = area
        self.vocabulary = vocabulary
        self.status = PreparationStatus.REVIEW

    def failed(self, message: str) -> None:
        self.status = PreparationStatus.FAILED
        self.error = message

    def review_fact(self, fact_id: str, review: Review, corrected: str | None = None) -> Fact:
        self._require_review()
        if review is Review.CORRECTED and not (corrected and corrected.strip()):
            raise ContextError("a correction needs the corrected statement")
        fact = self.fact(fact_id)
        updated = replace(
            fact,
            review=review,
            corrected=corrected.strip() if review is Review.CORRECTED and corrected else None,
        )
        self.facts = [updated if f.id == fact_id else f for f in self.facts]
        if review in (Review.CORRECTED, Review.EXCLUDED):
            # A changed statement no longer supports the model's original comparison.
            self.matches = [
                replace(
                    match,
                    status=MatchStatus.PARTIAL
                    if any(i != fact_id for i in match.fact_ids)
                    else MatchStatus.NOT_SHOWN,
                    fact_ids=tuple(i for i in match.fact_ids if i != fact_id),
                    rationale="Evidence changed during review; the original match was withdrawn.",
                )
                if fact_id in match.fact_ids
                else match
                for match in self.matches
                if match.requirement_id != fact_id or review is not Review.EXCLUDED
            ]
        return updated

    def add_fact(self, fact: Fact) -> None:
        self._require_review()
        if fact.origin is not FactOrigin.USER:
            raise ContextError("only the user adds facts during the review")
        self.facts.append(fact)
        if fact.subject is Subject.JOB and fact.kind in (
            FactKind.REQUIREMENT,
            FactKind.NICE_TO_HAVE,
        ):
            self.matches.append(RequirementMatch(fact.id, MatchStatus.NOT_SHOWN))

    def set_area(self, area: str, seniority: str) -> None:
        self._require_review()
        if self.job_mode is not JobMode.NONE:
            raise ContextError("the area is inferred only without a job offer")
        if not area.strip():
            raise ContextError("the area cannot be empty")
        rationale = self.area.rationale if self.area else ""
        self.area = TargetArea(area.strip(), seniority.strip(), rationale, confirmed=True)

    def approve(self, snapshot_id: str) -> None:
        self._require_review()
        if self.job_mode is JobMode.NONE and (self.area is None or not self.area.confirmed):
            raise ContextError("confirm the professional area before approving")
        self.status = PreparationStatus.APPROVED
        self.snapshot_id = snapshot_id

    def included_facts(self, subject: Subject | None = None) -> list[Fact]:
        return [f for f in self.facts if f.included and (subject is None or f.subject is subject)]

    def _require_review(self) -> None:
        if self.status is not PreparationStatus.REVIEW:
            raise ContextError(f"the context is {self.status.value}, not in review")


@dataclass(frozen=True, slots=True)
class Profile:
    """A named set of documents reused across interviews: a CV, a job offer and resources."""

    id: str
    name: str
    resources: tuple[Document, ...]
    created_at: float
    updated_at: float
    cv: Document | None = None
    job_offer: Document | None = None

    def __post_init__(self) -> None:
        if not self.name.strip() or len(self.name) > MAX_TITLE:
            raise ContextError(f"a profile name needs 1 to {MAX_TITLE} characters")
        if len(self.resources) > MAX_RESOURCES:
            raise ContextError(f"at most {MAX_RESOURCES} resources")
        if any(r.kind is not DocumentKind.RESOURCE for r in self.resources):
            raise ContextError("the resources of a profile must be resource documents")
        if self.cv is not None and self.cv.kind is not DocumentKind.CV:
            raise ContextError("the CV of a profile must be a CV document")
        if self.job_offer is not None and self.job_offer.kind is not DocumentKind.JOB_OFFER:
            raise ContextError("the job offer of a profile must be a job offer document")

    @property
    def job_mode(self) -> JobMode:
        if self.job_offer is None:
            return JobMode.NONE
        if self.job_offer.origin is DocumentOrigin.GENERATED:
            return JobMode.GENERATED
        return JobMode.OFFER

    def renamed(self, name: str, now: float) -> Profile:
        return replace(self, name=name.strip(), updated_at=now)


@dataclass(frozen=True, slots=True)
class ContextSnapshot:
    """The approved context, frozen. Identical content gives an identical hash."""

    id: str
    preparation_id: str
    created_at: float
    language: str
    job_mode: JobMode
    candidate_facts: tuple[Fact, ...]
    job_facts: tuple[Fact, ...]
    matches: tuple[RequirementMatch, ...]
    area: TargetArea | None
    vocabulary: tuple[str, ...]
    documents: tuple[Document, ...]
    content_hash: str
