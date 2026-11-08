"""Immutable report content. Scores describe practice evidence, never hiring probability."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ReportKind(StrEnum):
    CV = "cv"
    INTERVIEW = "interview"


@dataclass(frozen=True, slots=True)
class Evidence:
    source_id: str
    quote: str
    turn_seq: int | None = None


@dataclass(frozen=True, slots=True)
class Score:
    criterion_id: str
    label: str
    value: float | None
    reason: str
    evidence: tuple[Evidence, ...] = ()
    unstable: bool = False
    unit_id: str | None = None

    def __post_init__(self) -> None:
        if self.value is not None and not 1 <= self.value <= 5:
            raise ValueError("a score is between 1 and 5")
        if self.value is not None and not self.evidence:
            raise ValueError("a score needs verified evidence")


@dataclass(frozen=True, slots=True)
class Observation:
    kind: str
    text: str
    evidence: tuple[Evidence, ...]
    replacement: str | None = None
    unit_id: str | None = None


@dataclass(frozen=True, slots=True)
class Check:
    id: str
    status: str
    detail: str
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True, slots=True)
class Report:
    id: str
    kind: ReportKind
    subject_id: str
    version: int
    created_at: float
    language: str
    rubric_id: str
    rubric_hash: str
    model_ref: str
    prompt_ref: str
    input_fingerprint: str
    snapshot_id: str | None
    session_id: str | None
    scores: tuple[Score, ...]
    observations: tuple[Observation, ...]
    checks: tuple[Check, ...]
    overall: float | None
    assessed: int
    criteria: int
    dropped: int
    duration_s: float
    disclaimer: str


def overall_score(scores: tuple[Score, ...], *, minimum_share: float = 0.6) -> float | None:
    """Equal weights; unavailable criteria do not become zero or a midpoint."""
    available = [score.value for score in scores if score.value is not None]
    if not scores or len(available) / len(scores) < minimum_share:
        return None
    return round(sum(available) / len(available), 2)
