"""The analysis of the documents: facts with verified quotes, requirement matching, the target
area without a job offer, the technical vocabulary, and the drafting of a job offer from a
description.

Every model output is checked in code before it is used (AGENTS.md: AI outputs are untrusted):

- a fact's quote must be found in its document, otherwise the fact is *inferred* and the quote
  is dropped;
- a match may cite only existing candidate facts, and "met" needs at least one;
- a vocabulary term must appear in the documents.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from rapidfuzz import fuzz

from probeloop.ai.ports import ChatMessage, ChatModel, ChatRequest
from probeloop.ai.prompts import PromptRenderer
from probeloop.ai.structured import complete_structured
from probeloop.context.application.ports import ContextStore
from probeloop.context.domain.model import (
    Document,
    DocumentKind,
    Fact,
    FactKind,
    FactOrigin,
    JobMode,
    MatchStatus,
    RequirementMatch,
    RoleProfile,
    Subject,
    TargetArea,
)

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {"it": "Italian", "en": "English"}
KIND_LABELS = {
    DocumentKind.CV: "a CV",
    DocumentKind.JOB_OFFER: "a job offer",
    DocumentKind.RESOURCE: "a supporting document chosen by the candidate",
}
CHUNK_CHARS = 3500
MAX_FACTS_PER_CHUNK = 25
MAX_VOCABULARY = 60
QUOTE_MATCH = 90  # rapidfuzz partial_ratio on normalised text
MIN_QUOTE_CHARS = 8

_CANDIDATE_KINDS = Literal[
    "role", "project", "skill", "achievement", "education", "certification", "language", "other"
]
_JOB_KINDS = Literal["requirement", "nice_to_have", "responsibility", "company"]


class FactOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: Literal["candidate", "job"]
    kind: _CANDIDATE_KINDS | _JOB_KINDS
    statement: str = Field(min_length=3, max_length=400)
    quote: str = Field(max_length=600)


class ExtractionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facts: list[FactOut] = Field(max_length=40)
    terms: list[str] = Field(max_length=40)


class MatchOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_id: str = Field(max_length=16)
    status: Literal["met", "partial", "not_shown"]
    fact_ids: list[str] = Field(max_length=10)
    rationale: str = Field(max_length=400)


class MatchingOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    matches: list[MatchOut] = Field(max_length=60)


class AreaOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    area: str = Field(min_length=2, max_length=120)
    seniority: Literal["junior", "mid", "senior", "lead"]
    rationale: str = Field(max_length=600)


class RoleOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profession: str = Field(max_length=160)
    target_role: str = Field(max_length=160)
    seniority: str = Field(max_length=160)
    responsibilities: list[str] = Field(max_length=12)
    competencies: list[str] = Field(max_length=12)
    basis_fact_ids: list[str] = Field(max_length=24)
    rationale: str = Field(max_length=800)


class DraftOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(max_length=120)
    company: str = Field(max_length=300)
    seniority: str = Field(max_length=60)
    summary: str = Field(max_length=800)
    responsibilities: list[str] = Field(min_length=1, max_length=8)
    requirements: list[str] = Field(min_length=1, max_length=8)
    nice_to_have: list[str] = Field(max_length=8)


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    facts: list[Fact]
    matches: list[RequirementMatch]
    area: TargetArea | None
    vocabulary: tuple[str, ...]


_NON_WORD = re.compile(r"[^\w]+")


def normalise(text: str) -> str:
    return " ".join(_NON_WORD.sub(" ", text.lower()).split())


def quote_found(quote: str, text: str) -> bool:
    needle = normalise(quote)
    if len(needle) < MIN_QUOTE_CHARS:
        return False
    return bool(fuzz.partial_ratio(needle, normalise(text)) >= QUOTE_MATCH)


def chunks(text: str, size: int = CHUNK_CHARS) -> list[str]:
    """Split at paragraph (or line) boundaries into pieces of at most about `size` characters."""
    pieces: list[str] = []
    current = ""
    for paragraph in re.split(r"\n\s*\n", text):
        for part in _split_long(paragraph, size):
            if current and len(current) + len(part) + 2 > size:
                pieces.append(current)
                current = part
            else:
                current = f"{current}\n\n{part}" if current else part
    if current:
        pieces.append(current)
    return pieces


def _split_long(paragraph: str, size: int) -> list[str]:
    if len(paragraph) <= size:
        return [paragraph]
    out, current = [], ""
    for line in paragraph.split("\n"):
        while len(line) > size:
            out.append(line[:size])
            line = line[size:]
        if current and len(current) + len(line) + 1 > size:
            out.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        out.append(current)
    return out


class ContextAnalyser:
    def __init__(self, model: ChatModel, *, cache: ContextStore | None = None) -> None:
        self._model = model
        self._prompts = PromptRenderer("probeloop.context")
        self._cache = cache

    async def _complete[T: BaseModel](self, request: ChatRequest, output: type[T]) -> T:
        """Reuse analyses only when the model, schema and complete input agree."""
        key = hashlib.sha256(
            json.dumps(
                {
                    "version": 1,
                    "model": self._model.model_ref,
                    "schema": output.model_json_schema(),
                    "instructions": request.instructions,
                    "messages": [[m.role, m.content] for m in request.messages],
                    "temperature": request.temperature,
                    "tokens": request.max_output_tokens,
                    "reasoning": request.reasoning,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        if self._cache is not None:
            cached = await self._cache.cached_extraction(key)
            if cached is not None:
                return output.model_validate(cached)
        value = (await complete_structured(self._model, request, output)).value
        if self._cache is not None:
            await self._cache.cache_extraction(key, value.model_dump(mode="json"))
        return value

    async def analyse(
        self,
        documents: Sequence[Document],
        job_mode: JobMode,
        language: str,
        progress: Callable[[float, str], Awaitable[None]] | None = None,
    ) -> AnalysisResult:
        work = [(d, piece) for d in documents for piece in chunks(d.text)]
        steps = len(work) + 2
        facts: list[Fact] = []
        terms: list[str] = []
        seen: set[tuple[str, str]] = set()
        for index, (document, piece) in enumerate(work, start=1):
            if progress is not None:
                await progress(index / steps, f"reading {document.title}")
            extracted = await self._extract(document, piece, language)
            for item in extracted.facts:
                fact = self._fact(document, item)
                key = (fact.subject.value, normalise(fact.statement))
                if key not in seen:
                    seen.add(key)
                    facts.append(fact)
            terms += extracted.terms
        if progress is not None:
            await progress((steps - 1) / steps, "comparing with the position")
        matches = await self._match(facts, language)
        area = None
        if job_mode is JobMode.NONE:
            area = await self._infer_area(facts, language)
        vocabulary = vocabulary_from(terms, [d.text for d in documents])
        logger.info(
            "context analysed",
            extra={
                "facts": len(facts),
                "declared": sum(f.origin is FactOrigin.DECLARED for f in facts),
                "matches": len(matches),
                "terms": len(vocabulary),
            },
        )
        return AnalysisResult(facts=facts, matches=matches, area=area, vocabulary=vocabulary)

    async def draft_job_offer(self, description: str, language: str) -> str:
        prompt = self._prompts.render(
            "draft_job_offer", 1, language_name=LANGUAGE_NAMES.get(language, "English")
        )
        request = ChatRequest(
            instructions=prompt.text,
            messages=(
                ChatMessage("user", f"Description of the position:\n<<<\n{description}\n>>>"),
            ),
            temperature=0.4,
            max_output_tokens=1200,
        )
        draft = (await complete_structured(self._model, request, DraftOut)).value
        return render_offer(draft, language)

    async def propose_role(self, facts: list[Fact], language: str) -> RoleProfile:
        if not facts:
            return RoleProfile()
        # Inferences without a verified quote cannot substantiate a proposed profile.
        available = [f for f in facts if f.included and f.origin is not FactOrigin.INFERRED]
        if not available:
            return RoleProfile()
        prompt = self._prompts.render(
            "propose_role", 1, language_name=LANGUAGE_NAMES.get(language, "English")
        )
        out = await self._complete(
            ChatRequest(
                instructions=prompt.text,
                messages=(
                    ChatMessage(
                        "user",
                        json.dumps(
                            [
                                {
                                    "id": f.id,
                                    "subject": f.subject.value,
                                    "kind": f.kind.value,
                                    "text": f.text,
                                }
                                for f in available
                            ],
                            ensure_ascii=False,
                        ),
                    ),
                ),
                temperature=0.1,
                max_output_tokens=1400,
            ),
            RoleOut,
        )
        known = {f.id for f in available}
        return RoleProfile(
            profession=out.profession.strip(),
            target_role=out.target_role.strip(),
            seniority=out.seniority.strip(),
            responsibilities=tuple(s.strip()[:400] for s in out.responsibilities if s.strip()),
            competencies=tuple(s.strip()[:400] for s in out.competencies if s.strip()),
            basis_fact_ids=tuple(dict.fromkeys(i for i in out.basis_fact_ids if i in known)),
            rationale=out.rationale,
        )

    # ------------------------------------------------------------------ steps

    async def _extract(self, document: Document, piece: str, language: str) -> ExtractionOut:
        prompt = self._prompts.render(
            "extract_facts",
            1,
            kind=document.kind.value,
            kind_label=KIND_LABELS[document.kind],
            language_name=LANGUAGE_NAMES.get(language, "English"),
            max_facts=MAX_FACTS_PER_CHUNK,
        )
        request = ChatRequest(
            instructions=prompt.text,
            messages=(ChatMessage("user", f'Document "{document.title}":\n<<<\n{piece}\n>>>'),),
            temperature=0.1,
            max_output_tokens=3000,
        )
        return await self._complete(request, ExtractionOut)

    def _fact(self, document: Document, item: FactOut) -> Fact:
        subject = Subject(item.subject)
        if document.kind is DocumentKind.CV:
            subject = Subject.CANDIDATE
        elif document.kind is DocumentKind.JOB_OFFER:
            subject = Subject.JOB
        kind = FactKind(item.kind)
        if (subject is Subject.JOB) != (kind in _JOB_FACT_KINDS):
            kind = FactKind.REQUIREMENT if subject is Subject.JOB else FactKind.OTHER
        verified = quote_found(item.quote, document.text)
        return Fact(
            id=hashlib.sha256(
                json.dumps(
                    [
                        document.kind.value,
                        document.title,
                        document.text,
                        subject.value,
                        kind.value,
                        item.statement,
                        item.quote,
                    ]
                ).encode()
            ).hexdigest()[:12],
            subject=subject,
            kind=kind,
            statement=" ".join(item.statement.split()),
            origin=FactOrigin.DECLARED if verified else FactOrigin.INFERRED,
            document_id=document.id,
            quote=" ".join(item.quote.split()) if verified else None,
        )

    async def _match(self, facts: list[Fact], language: str) -> list[RequirementMatch]:
        requirements = [f for f in facts if f.kind in (FactKind.REQUIREMENT, FactKind.NICE_TO_HAVE)]
        candidate = [f for f in facts if f.subject is Subject.CANDIDATE]
        if not requirements:
            return []
        if not candidate:
            return [RequirementMatch(r.id, MatchStatus.NOT_SHOWN) for r in requirements]
        prompt = self._prompts.render(
            "match_requirements", 1, language_name=LANGUAGE_NAMES.get(language, "English")
        )
        listing = "Requirements:\n" + "\n".join(f"- {r.id}: {r.statement}" for r in requirements)
        listing += "\n\nCandidate facts:\n" + "\n".join(
            f"- {f.id}: {f.statement}" for f in candidate
        )
        request = ChatRequest(
            instructions=prompt.text,
            messages=(ChatMessage("user", listing),),
            temperature=0.1,
            max_output_tokens=3000,
        )
        out = await self._complete(request, MatchingOut)
        return checked_matches(out, requirements, candidate)

    async def _infer_area(self, facts: list[Fact], language: str) -> TargetArea | None:
        candidate = [f for f in facts if f.subject is Subject.CANDIDATE]
        if not candidate:
            return None
        prompt = self._prompts.render(
            "infer_area", 1, language_name=LANGUAGE_NAMES.get(language, "English")
        )
        listing = "Candidate facts:\n" + "\n".join(f"- {f.statement}" for f in candidate)
        request = ChatRequest(
            instructions=prompt.text,
            messages=(ChatMessage("user", listing),),
            temperature=0.2,
            max_output_tokens=500,
        )
        out = await self._complete(request, AreaOut)
        return TargetArea(area=out.area.strip(), seniority=out.seniority, rationale=out.rationale)


_JOB_FACT_KINDS = frozenset(
    {FactKind.REQUIREMENT, FactKind.NICE_TO_HAVE, FactKind.RESPONSIBILITY, FactKind.COMPANY}
)


def checked_matches(
    out: MatchingOut, requirements: list[Fact], candidate: list[Fact]
) -> list[RequirementMatch]:
    """One match per requirement; unknown ids are dropped, and "met" needs evidence."""
    known = {f.id for f in candidate if f.origin is not FactOrigin.INFERRED}
    by_requirement: dict[str, MatchOut] = {}
    for item in out.matches:
        by_requirement.setdefault(item.requirement_id, item)
    result = []
    for requirement in requirements:
        match = by_requirement.get(requirement.id)
        if match is None:
            result.append(RequirementMatch(requirement.id, MatchStatus.NOT_SHOWN))
            continue
        fact_ids = tuple(dict.fromkeys(i for i in match.fact_ids if i in known))
        status = MatchStatus(match.status)
        if status is not MatchStatus.NOT_SHOWN and not fact_ids:
            status = MatchStatus.NOT_SHOWN
        if status is MatchStatus.NOT_SHOWN:
            fact_ids = ()
        result.append(RequirementMatch(requirement.id, status, fact_ids, match.rationale.strip()))
    return result


def vocabulary_from(terms: Sequence[str], texts: Sequence[str]) -> tuple[str, ...]:
    """Terms that really occur in the documents, first spelling kept, in order of appearance."""
    corpus = "\n".join(texts).lower()
    out: dict[str, str] = {}
    for term in terms:
        cleaned = " ".join(term.split()).strip(" .,;:")
        key = cleaned.lower()
        if 2 <= len(cleaned) <= 40 and key not in out and key in corpus:
            out[key] = cleaned
    return tuple(out.values())[:MAX_VOCABULARY]


_OFFER_HEADINGS = {
    "it": ("Azienda", "Livello", "Il ruolo", "Responsabilità", "Requisiti", "Preferibile"),
    "en": ("Company", "Level", "The role", "Responsibilities", "Requirements", "Nice to have"),
}


def render_offer(draft: DraftOut, language: str) -> str:
    company, level, role, duties, required, nice = _OFFER_HEADINGS.get(
        language, _OFFER_HEADINGS["en"]
    )
    lines = [draft.title.strip(), "", f"{company}: {draft.company.strip()}"]
    lines += [f"{level}: {draft.seniority.strip()}", "", role, draft.summary.strip(), ""]
    for heading, items in ((duties, draft.responsibilities), (required, draft.requirements)):
        lines += [heading, *(f"- {i.strip()}" for i in items), ""]
    if draft.nice_to_have:
        lines += [nice, *(f"- {i.strip()}" for i in draft.nice_to_have)]
    return "\n".join(lines).strip()
