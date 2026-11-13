"""Ports of the context use cases."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from probeloop.context.domain.model import (
    ContextSnapshot,
    Document,
    Obligation,
    Preparation,
    Profile,
)


class ExtractionError(ValueError):
    """A file could not be read; the message is safe to show."""


@dataclass(frozen=True, slots=True)
class ExtractedText:
    text: str
    media_type: str
    warnings: tuple[str, ...] = ()


class TextExtraction(Protocol):
    async def extract(self, data: bytes, filename: str) -> ExtractedText: ...


class ContextStore(Protocol):
    async def cached_extraction(self, key: str) -> dict[str, Any] | None: ...

    async def cache_extraction(self, key: str, data: dict[str, Any]) -> None: ...

    async def add_document(self, document: Document, original: bytes | None = None) -> None: ...

    async def documents(self, ids: list[str]) -> list[Document]: ...

    async def original(self, sha256: str) -> bytes | None:
        """The stored bytes of an uploaded file, if present."""
        ...

    async def profiles(self) -> list[Profile]: ...

    async def profile(self, profile_id: str) -> Profile | None: ...

    async def save_profile(self, profile: Profile) -> None: ...

    async def delete_profile(self, profile_id: str) -> bool:
        """Delete the profile with the preparations, contexts and documents that only it kept.
        Contexts that an interview, a report or a pending job uses stay, with their documents."""
        ...

    async def discard_snapshot(self, snapshot_id: str) -> bool:
        """Delete a context that no interview, report or pending job uses, with the preparations
        that approved it and the documents nothing else keeps. False when it is still in use."""
        ...

    async def save_preparation(self, preparation: Preparation) -> None: ...

    async def preparation(self, preparation_id: str) -> Preparation | None: ...

    async def save_snapshot(self, snapshot: ContextSnapshot) -> None: ...

    async def snapshot(self, snapshot_id: str) -> ContextSnapshot | None: ...

    async def snapshot_by_hash(self, content_hash: str) -> ContextSnapshot | None: ...


class TextClassifierUnavailable(Exception):
    """The classifier could not read the lines; the message is safe to show."""


@dataclass(frozen=True, slots=True)
class OfferLine:
    """A line of a job offer and the heading of the section it belongs to."""

    text: str
    heading: str | None = None


@dataclass(frozen=True, slots=True)
class ObligationReading:
    obligation: Obligation
    must: float  # the probability that the line states a requirement
    preferred: float  # the probability that it states a preference


@dataclass(frozen=True, slots=True)
class LineReading:
    positive: bool
    score: float


@dataclass(frozen=True, slots=True)
class Classified[T]:
    """One reading per line, in order, and the model, wording and thresholds that produced them."""

    readings: tuple[T, ...]
    model_ref: str


class TextClassifier(Protocol):
    """Line-level labels that a fast classifier can give beside the analysis model.

    Its readings are inputs that the analysis checks against its rules and its own model. It
    never decides coverage, fit, scores or feedback.
    """

    async def obligations(self, lines: Sequence[OfferLine]) -> Classified[ObligationReading]: ...

    async def quantified(self, lines: Sequence[str]) -> Classified[LineReading]:
        """Whether each CV line states a measured outcome or scope of the candidate's work."""
        ...

    async def headings(self, lines: Sequence[str]) -> Classified[LineReading]:
        """Whether each CV line is a section heading, in any wording, case or spacing."""
        ...
