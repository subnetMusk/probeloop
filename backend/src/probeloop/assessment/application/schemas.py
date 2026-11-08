"""Untrusted model outputs and typed report serialization, validated at the application boundary."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model

from probeloop.assessment.domain.model import (
    AnswerUnit,
    Check,
    DeliveryMetric,
    Evidence,
    Observation,
    Report,
    ReportKind,
    Score,
    TranscriptVersion,
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
    kind: Literal["strength", "improvement", "technical_error", "rewrite", "question", "summary"]
    text: str = Field(min_length=1, max_length=600)
    evidence: list[EvidenceData] = Field(min_length=1, max_length=3)
    replacement: str | None = Field(default=None, max_length=600)


class JudgementsOut(Strict):
    scores: list[JudgementOut] = Field(max_length=7)
    observations: list[ObservationOut] = Field(max_length=12)


class RequirementOut(Strict):
    requirement_id: str = Field(max_length=80)
    evidence: list[EvidenceData] = Field(min_length=1, max_length=3)


class CriterionOut(Strict):
    """One criterion of an answer unit. Quotation, reason and score come in that order: with
    constrained decoding the model commits to its evidence and rationale before the number."""

    evidence: list[EvidenceData] = Field(max_length=2)
    reason: str = Field(min_length=1, max_length=300)
    score: int | None = Field(ge=1, le=5)


class UnitObservationOut(Strict):
    kind: Literal["strength", "improvement", "technical_error", "question"]
    evidence: list[EvidenceData] = Field(min_length=1, max_length=2)
    text: str = Field(min_length=1, max_length=400)


class ClaimCheckOut(Strict):
    """An independent check of one statement that a judge reported as a technical error."""

    analysis: str = Field(min_length=1, max_length=500)
    verdict: Literal["correct", "incorrect", "uncertain"]


class SynthesisOut(Strict):
    """Editorial selection over verified observations, referenced by id; no new evidence."""

    priorities: list[str] = Field(max_length=3)
    strengths: list[str] = Field(max_length=2)
    summary: str = Field(min_length=1, max_length=800)


def unit_output(criteria: tuple[str, ...], *, observations: bool) -> type[Strict]:
    """The schema of one judging pass: every rubric criterion exactly once, in rubric order.

    The pass that lists the anchors in descending order exists to average out position bias in
    the scores, so it returns scores only; observations and coverage come from the other pass.
    """
    scores: dict[str, Any] = {c: (CriterionOut, ...) for c in criteria}
    fields: dict[str, Any] = {
        "scores": (create_model("CriteriaOut", __base__=Strict, **scores), ...)
    }
    if observations:
        fields["observations"] = (list[UnitObservationOut], Field(max_length=3))
        fields["coverage"] = (list[RequirementOut], Field(max_length=10))
    return create_model("UnitJudgementOut", __base__=Strict, **fields)


def unit_judgements(output: Strict) -> JudgementsOut:
    """Convert a validated pass into the shape shared with the evidence checks."""
    data = output.model_dump()
    return JudgementsOut(
        scores=[
            JudgementOut(
                criterion_id=criterion,
                score=item["score"],
                reason=item["reason"],
                evidence=[EvidenceData(**e) for e in item["evidence"]],
            )
            for criterion, item in data["scores"].items()
        ],
        observations=[
            ObservationOut(
                kind=item["kind"],
                text=item["text"],
                evidence=[EvidenceData(**e) for e in item["evidence"]],
            )
            for item in data.get("observations", [])
        ],
    )


def unit_coverage(output: Strict) -> list[RequirementOut]:
    return [RequirementOut.model_validate(c) for c in output.model_dump().get("coverage", [])]


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


class UnitData(Strict):
    id: str
    topic_id: str
    kind: str
    question_seqs: list[int]
    answer_seqs: list[int]

    def domain(self) -> AnswerUnit:
        return AnswerUnit(
            self.id, self.topic_id, self.kind, tuple(self.question_seqs), tuple(self.answer_seqs)
        )


class DeliveryData(Strict):
    id: str
    value: float | None
    unit: str
    detail: str
    turn_seq: int | None

    def domain(self) -> DeliveryMetric:
        return DeliveryMetric(self.id, self.value, self.unit, self.detail, self.turn_seq)


class VersionData(Strict):
    seq: int
    revision: int


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
    units: list[UnitData]
    unit_scores: list[ScoreData]
    delivery: list[DeliveryData]
    revisions: list[VersionData]

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
            units=tuple(u.domain() for u in self.units),
            unit_scores=tuple(s.domain() for s in self.unit_scores),
            delivery=tuple(d.domain() for d in self.delivery),
            revisions=tuple(TranscriptVersion(r.seq, r.revision) for r in self.revisions),
        )
