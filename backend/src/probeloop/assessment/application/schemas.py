"""Untrusted model outputs and typed report serialization, validated at the application boundary."""

from __future__ import annotations

from dataclasses import asdict
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from probeloop.assessment.domain.model import (
    Check,
    Evidence,
    Observation,
    Report,
    ReportKind,
    Score,
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceData(Strict):
    source_id: str = Field(max_length=80)
    quote: str = Field(min_length=1, max_length=600)
    turn_seq: int | None = None

    def domain(self) -> Evidence:
        return Evidence(self.source_id, self.quote, self.turn_seq)


class JudgementOut(Strict):
    criterion_id: str = Field(max_length=60)
    score: int | None = Field(ge=1, le=5)
    reason: str = Field(min_length=1, max_length=600)
    evidence: list[EvidenceData] = Field(max_length=3)


class ObservationOut(Strict):
    kind: Literal["strength", "improvement", "technical_error", "rewrite", "question"]
    text: str = Field(min_length=1, max_length=600)
    evidence: list[EvidenceData] = Field(min_length=1, max_length=3)
    replacement: str | None = Field(default=None, max_length=600)


class JudgementsOut(Strict):
    scores: list[JudgementOut] = Field(max_length=7)
    observations: list[ObservationOut] = Field(max_length=12)


class ScoreData(Strict):
    criterion_id: str
    label: str
    value: float | None
    reason: str
    evidence: list[EvidenceData]
    unstable: bool
    unit_id: str | None

    def domain(self) -> Score:
        return Score(
            self.criterion_id,
            self.label,
            self.value,
            self.reason,
            tuple(e.domain() for e in self.evidence),
            self.unstable,
            self.unit_id,
        )


class ObservationData(Strict):
    kind: str
    text: str
    evidence: list[EvidenceData]
    replacement: str | None
    unit_id: str | None

    def domain(self) -> Observation:
        return Observation(
            self.kind,
            self.text,
            tuple(e.domain() for e in self.evidence),
            self.replacement,
            self.unit_id,
        )


class CheckData(Strict):
    id: str
    status: str
    detail: str
    evidence: list[EvidenceData]

    def domain(self) -> Check:
        return Check(self.id, self.status, self.detail, tuple(e.domain() for e in self.evidence))


class ReportData(Strict):
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
    scores: list[ScoreData]
    observations: list[ObservationData]
    checks: list[CheckData]
    overall: float | None
    assessed: int
    criteria: int
    dropped: int
    duration_s: float
    disclaimer: str

    @classmethod
    def of(cls, report: Report) -> ReportData:
        return cls.model_validate(asdict(report))

    def domain(self) -> Report:
        return Report(
            id=self.id,
            kind=self.kind,
            subject_id=self.subject_id,
            version=self.version,
            created_at=self.created_at,
            language=self.language,
            rubric_id=self.rubric_id,
            rubric_hash=self.rubric_hash,
            model_ref=self.model_ref,
            prompt_ref=self.prompt_ref,
            input_fingerprint=self.input_fingerprint,
            snapshot_id=self.snapshot_id,
            session_id=self.session_id,
            scores=tuple(s.domain() for s in self.scores),
            observations=tuple(o.domain() for o in self.observations),
            checks=tuple(c.domain() for c in self.checks),
            overall=self.overall,
            assessed=self.assessed,
            criteria=self.criteria,
            dropped=self.dropped,
            duration_s=self.duration_s,
            disclaimer=self.disclaimer,
        )
