"""Pure report presentation shared by the local Markdown and PDF renderers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from math import floor
from statistics import median

from probeloop.assessment.application.labels import label
from probeloop.assessment.application.score_scale import score_100
from probeloop.assessment.domain.model import (
    Check,
    Evidence,
    Observation,
    Report,
    ReportKind,
    Score,
)

INTERVIEW_SECTIONS = (
    "overview",
    "improvements",
    "strengths",
    "questions",
    "requirements",
    "delivery",
    "practice",
    "technical",
)
CV_SECTIONS = (
    "overview",
    "criteria",
    "requirements",
    "checks",
    "improvements",
    "strengths",
    "rewrites",
    "practice",
    "original",
    "technical",
)
CHECK_ORDER = {"review": 0, "info": 1, "pass": 2, "not_assessable": 3}


@dataclass(frozen=True)
class Quote:
    text: str
    answer: int | None


@dataclass(frozen=True)
class Note:
    kind: str
    text: str
    replacement: str | None
    quotes: tuple[Quote, ...]
    unit: int | None


@dataclass(frozen=True)
class Criterion:
    id: str
    label: str
    value: float | None
    reason: str
    unstable: bool
    quotes: tuple[Quote, ...]


@dataclass(frozen=True)
class Answer:
    number: int
    text: str


@dataclass(frozen=True)
class Assistance:
    purpose: str
    text: str
    answer: int | None
    level: int


@dataclass(frozen=True)
class Unit:
    number: int
    kind: str
    scored: bool
    questions: tuple[str, ...]
    answers: tuple[Answer, ...]
    scores: tuple[Criterion, ...]
    assistance: tuple[Assistance, ...] = ()


@dataclass(frozen=True)
class Requirement:
    id: str
    text: str
    interview: str | None = None
    documents: str | None = None
    quotes: tuple[Quote, ...] = ()


@dataclass(frozen=True)
class Diagnostic:
    id: str
    status: str
    detail: str
    quotes: tuple[Quote, ...]


@dataclass(frozen=True)
class AnswerDelivery:
    answer: int
    duration: float | None
    rate: float | None
    fillers: float | None
    pauses: float | None
    latency: float | None


@dataclass(frozen=True)
class Delivery:
    median_rate: float | None
    median_latency: float | None
    fillers_per_minute: float | None
    long_pauses: float | None
    talk_share: float | None
    budget_share: float | None
    per_answer: tuple[AnswerDelivery, ...]


@dataclass(frozen=True)
class Technical:
    model: str
    prompt: str
    rubric: str
    rubric_hash: str
    fingerprint: str
    dropped: int
    edited_answers: int
    duration_s: float
    disclaimer: str


@dataclass(frozen=True)
class ReportOutline:
    title: str
    sections: tuple[str, ...]
    overall: float | None
    band: str | None
    assessed: int
    criteria_count: int
    summary: Note | None
    improvements: tuple[Note, ...]
    strengths: tuple[Note, ...]
    rewrites: tuple[Note, ...]
    practice: tuple[Note, ...]
    criteria: tuple[Criterion, ...]
    units: tuple[Unit, ...]
    requirements: tuple[Requirement, ...]
    checks: tuple[Diagnostic, ...]
    delivery: Delivery | None
    technical: Technical
    unstable: bool
    original: str | None
    target: str | None = None
    references: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExportSources:
    transcript: Mapping[int, str]
    requirements: tuple[Check, ...] = ()
    original: str | None = None


def _band(value: float | None) -> str | None:
    return (
        None
        if value is None
        else "solid"
        if value >= 4
        else "developing"
        if value >= 2.5
        else "needs_work"
    )


def _delivery(report: Report, answers: Mapping[int, int]) -> Delivery | None:
    if not report.delivery:
        return None
    by_turn: dict[int, dict[str, float | None]] = {}
    global_values: dict[str, float | None] = {}
    for metric in report.delivery:
        if metric.turn_seq is None:
            global_values[metric.id] = metric.value
        else:
            by_turn.setdefault(metric.turn_seq, {})[metric.id] = metric.value
    rows = tuple(
        AnswerDelivery(
            answers.get(seq, 0),
            *(
                values.get(key)
                for key in (
                    "answer_duration",
                    "speaking_rate",
                    "fillers",
                    "long_pauses",
                    "answer_latency",
                )
            ),
        )
        for seq, values in sorted(by_turn.items())
    )

    def known(key: str) -> list[float]:
        return [value for values in by_turn.values() if (value := values.get(key)) is not None]

    def middle(key: str) -> float | None:
        values = known(key)
        return median(values) if values else None

    seconds = sum(known("answer_duration"))
    fillers = known("fillers")
    pauses = known("long_pauses")
    return Delivery(
        middle("speaking_rate"),
        middle("answer_latency"),
        floor(sum(fillers) / (seconds / 60) * 10 + 0.5) / 10 if seconds > 0 and fillers else None,
        sum(pauses) if pauses else None,
        global_values.get("candidate_talk_share"),
        global_values.get("answer_budget_share"),
        rows,
    )


def report_outline(
    report: Report,
    questions: Mapping[int, str],
    *,
    requirements: tuple[Check, ...] = (),
    original: str | None = None,
) -> ReportOutline:
    """`questions` contains prompts and frozen answer texts by transcript sequence.

    Document requirements may be supplied from the immutable approved snapshot for CV reports.
    No identifiers or full hashes are exposed in the reading sections.
    """
    answer_seqs = sorted(
        {seq for unit in report.units for seq in unit.answer_seqs}
        | {r.seq for r in report.revisions}
    )
    answers = {seq: n for n, seq in enumerate(answer_seqs, 1)}
    units = {unit.id: n for n, unit in enumerate(report.units, 1)}

    def quotes(evidence: tuple[Evidence, ...]) -> tuple[Quote, ...]:
        return tuple(
            Quote(e.quote, answers.get(e.turn_seq) if e.turn_seq is not None else None)
            for e in evidence
        )

    def note(item: Observation) -> Note:
        return Note(
            item.kind,
            item.text,
            item.replacement,
            quotes(item.evidence),
            units.get(item.unit_id) if item.unit_id else None,
        )

    def criterion(item: Score) -> Criterion:
        reason = next((line.strip() for line in item.reason.splitlines() if line.strip()), "")
        return Criterion(
            item.criterion_id,
            item.label,
            score_100(item.value),
            reason,
            item.unstable,
            quotes(item.evidence),
        )

    notes = tuple(note(item) for item in report.observations)
    coverage: dict[str, Requirement] = {}
    for check in (*report.checks, *requirements):
        prefix, _, key = check.id.partition(":")
        if not key or prefix not in {"requirement", "document_requirement"}:
            continue
        row = coverage.get(key, Requirement(key, check.detail))
        if prefix == "requirement":
            row = replace(
                row,
                interview="not_shown" if check.status == "not_shown" else "discussed",
                quotes=quotes(check.evidence),
            )
        else:
            row = replace(
                row, documents=check.status if check.status in {"met", "partial"} else "not_shown"
            )
        coverage[key] = row
    cv = report.kind is ReportKind.CV
    return ReportOutline(
        label("CV report" if cv else "Interview report", report.language),
        CV_SECTIONS if cv else INTERVIEW_SECTIONS,
        score_100(report.overall),
        _band(report.overall),
        report.assessed,
        report.criteria,
        next((item for item in notes if item.kind == "summary"), None),
        tuple(
            item
            for item in notes
            if item.kind
            in (
                {"improvement", "technical_error"}
                if cv
                else {"improvement", "technical_error", "rewrite"}
            )
        ),
        tuple(item for item in notes if item.kind == "strength"),
        tuple(item for item in notes if item.kind == "rewrite") if cv else (),
        tuple(item for item in notes if item.kind == "question"),
        tuple(criterion(item) for item in report.scores),
        tuple(
            Unit(
                n,
                unit.kind,
                unit.kind not in {"logistics", "unclassified"},
                tuple(questions.get(seq, "") for seq in unit.question_seqs),
                tuple(Answer(answers[seq], questions.get(seq, "")) for seq in unit.answer_seqs),
                tuple(criterion(item) for item in report.unit_scores if item.unit_id == unit.id),
                tuple(
                    Assistance(
                        trace.intent.purpose.value,
                        trace.text,
                        answers.get(trace.intent.answer_seq)
                        if trace.intent.answer_seq is not None
                        else None,
                        trace.intent.hint_level,
                    )
                    for trace in report.question_trace
                    if trace.question_seq in unit.question_seqs
                    and trace.intent.purpose.value in {"clarification", "hint"}
                ),
            )
            for n, unit in enumerate(report.units, 1)
        ),
        tuple(
            sorted(
                coverage.values(),
                key=lambda row: {"not_shown": 0, "partial": 1, "met": 2}.get(
                    row.documents or "", 0
                ),
            )
        )
        if cv
        else tuple(coverage.values()),
        tuple(
            Diagnostic(
                item.id,
                item.status if item.status in CHECK_ORDER else "not_assessable",
                item.detail,
                quotes(item.evidence),
            )
            for item in sorted(report.checks, key=lambda item: CHECK_ORDER.get(item.status, 3))
        )
        if cv
        else (),
        _delivery(report, answers),
        Technical(
            report.model_ref,
            report.prompt_ref,
            report.rubric_id,
            report.rubric_hash[:8],
            report.input_fingerprint[:8],
            report.dropped,
            sum(r.revision > 1 for r in report.revisions),
            report.duration_s,
            report.disclaimer,
        ),
        any(item.unstable for item in (*report.scores, *report.unit_scores)),
        original,
        " · ".join(
            (
                report.role_profile.profession,
                report.role_profile.target_role,
                report.role_profile.seniority,
            )
        )
        if report.role_profile
        else None,
        tuple(document.title for document in report.reference_documents),
    )
