"""Classify, judge twice, check corrections, verify and aggregate a frozen transcript.

Model calls per review, all sequential on one local model:

- one classification call per eight answer units;
- two judging passes per scored unit, with the rubric anchors in ascending and in descending
  order (the scores of both are averaged in code); only the ascending pass also returns
  observations and requirement coverage, so the two passes do not duplicate them;
- one independent check per statement that a judge reported as a technical error;
- one editorial synthesis call that selects existing observations by id and writes a summary.

The approved context is compacted once per review and placed first in every judging request,
so the provider can reuse the processed prefix between calls.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, replace
from typing import Any, Literal

from pydantic import BaseModel

from probeloop.ai.ports import ChatMessage, ChatModel, ChatRequest, LlmError
from probeloop.ai.prompts import PromptRenderer
from probeloop.ai.structured import complete_structured
from probeloop.assessment.application.elicitation import (
    elicited_criteria,
    elicited_scores,
    recorded_units,
)
from probeloop.assessment.application.evidence import Source, checked_evidence, checked_judgements
from probeloop.assessment.application.rubrics import Rubric, load_rubric
from probeloop.assessment.application.schemas import (
    ClaimCheckOut,
    SelectionOut,
    SynthesisOut,
    criterion_judgements,
    unit_coverage,
    unit_output,
)
from probeloop.assessment.application.segmentation import (
    KindsOut,
    answer_units,
    classified,
    past_examples,
)
from probeloop.assessment.domain.model import AnswerUnit, Check, Evidence, Observation, Score
from probeloop.assessment.domain.units import aggregate_scores, paired_scores
from probeloop.context.domain.model import ContextSnapshot, DocumentKind, FactKind
from probeloop.interview.domain.model import CandidateTurn, InterviewSession, Turn
from probeloop.platform.jobs import Progress

type Reasoning = Literal["off", "default"]

# Output budgets sized to the schemas, plus room for thinking when it is enabled.
_JUDGE_TOKENS = {True: 2000, False: 1400}
_THINKING_TOKENS = 7000
_CLAIM_TOKENS = 500
_SYNTHESIS_TOKENS = 800
# The model's default presence penalty (1.5 for qwen3.5) penalises tokens that were already
# generated, such as a quotation repeated for several criteria, and verbatim quotes are required.
_PRESENCE_PENALTY = 0.0


def turn_data(turn: Turn) -> dict[str, object]:
    return {
        "seq": turn.seq,
        "source_id": f"turn-{turn.seq}",
        "speaker": turn.speaker.value,
        "text": turn.text if isinstance(turn, CandidateTurn) else turn.move.utterance,
    }


def evaluation_context(
    session: InterviewSession, snapshot: ContextSnapshot | None
) -> dict[str, object]:
    """The approved context for the judges, without metadata or repeated content.

    Documents are sent once, as approved. Facts are reduced to their reviewed statements: their
    quotations repeat the documents. Without a snapshot the interviewer briefs are the context.
    """
    adaptive = session.context.policy_version is not None
    topics = [
        asdict(t) if adaptive else {"id": t.id, "title": t.title} for t in session.context.topics
    ]
    target = (
        {
            "policy_version": session.context.policy_version,
            "confirmed_role": asdict(session.context.role_profile)
            if session.context.role_profile
            else None,
        }
        if adaptive
        else {}
    )
    if snapshot is None:
        return {
            **target,
            "topics": topics,
            "candidate_brief": session.context.candidate_brief,
            "job_brief": session.context.job_brief,
            "requirements": [],
            "documents": [],
        }
    status = {m.requirement_id: m.status.value for m in snapshot.matches}
    return {
        **target,
        "topics": topics,
        "job_mode": snapshot.job_mode.value,
        "target_area": (
            {"area": snapshot.area.area, "seniority": snapshot.area.seniority}
            if snapshot.area
            else None
        ),
        "requirements": [
            {"id": f.id, "kind": f.kind.value, "text": f.text, "cv_match": status.get(f.id)}
            for f in snapshot.job_facts
            if f.kind in (FactKind.REQUIREMENT, FactKind.NICE_TO_HAVE)
        ],
        "candidate_facts": [
            {"kind": f.kind.value, "text": f.text} for f in snapshot.candidate_facts
        ],
        "documents": [
            {"kind": d.kind.value, "title": d.title, "text": d.text} for d in snapshot.documents
        ],
    }


@dataclass(frozen=True, slots=True)
class CallTrace:
    """Diagnostics of one logical model call, repairs included. Never holds prompt text."""

    phase: str
    unit_id: str | None
    reasoning: str
    attempts: int
    prompt_tokens: int | None
    output_tokens: int | None
    duration_s: float
    stop_reasons: tuple[str | None, ...]


@dataclass(frozen=True)
class InterviewJudgement:
    units: tuple[AnswerUnit, ...]
    unit_scores: tuple[Score, ...]
    scores: tuple[Score, ...]
    observations: tuple[Observation, ...]
    dropped: int
    coverage: tuple[Check, ...]
    calls: tuple[CallTrace, ...] = ()
    disputed: int = 0


class InterviewReviewer:
    def __init__(
        self,
        model: ChatModel,
        *,
        judge_reasoning: Reasoning = "off",
        presence_penalty: float | None = _PRESENCE_PENALTY,
    ) -> None:
        self.model = model
        self.judge_reasoning: Reasoning = judge_reasoning
        self.presence_penalty = presence_penalty
        self.rubrics = {
            name: load_rubric(name, version=2 if name == "technical" else 1)
            for name in ("hr", "behavioral", "technical", "hypothetical")
        }
        self.adaptive_rubrics = {
            name: load_rubric(name, version=3 if name == "technical" else 2)
            for name in self.rubrics
        }
        self._outputs = {
            (rubric.ref, full): unit_output(
                tuple(c.id for c in rubric.criteria),
                observations=full,
                elicitation=rubric in self.adaptive_rubrics.values(),
            )
            for rubric in (*self.rubrics.values(), *self.adaptive_rubrics.values())
            for full in (True, False)
        }
        self._prompts = PromptRenderer("probeloop.assessment")

    @property
    def rubric_ref(self) -> str:
        return "+".join(r.ref for _, r in sorted(self.rubrics.items()))

    def rubrics_for(self, session: InterviewSession) -> dict[str, Rubric]:
        return self.adaptive_rubrics if session.context.policy_version else self.rubrics

    def rubric_ref_for(self, session: InterviewSession) -> str:
        return "+".join(r.ref for _, r in sorted(self.rubrics_for(session).items()))

    def prompt_ref_for(self, session: InterviewSession) -> str:
        if not session.context.policy_version:
            return self.prompt_ref
        judging = "think" if self.judge_reasoning == "default" else "off"
        return (
            f"classify_units@v6:diagnostic:off+judge_unit@v5:asc,desc-scores:{judging}"
            "+check_claim@v2:off+synthesise@v4:off+elicitation@v1"
        )

    @property
    def prompt_ref(self) -> str:
        judging = "think" if self.judge_reasoning == "default" else "off"
        return (
            f"classify_units@v5:off+judge_unit@v3:asc,desc-scores:{judging}"
            "+check_claim@v1:off+synthesise@v3:off"
        )

    async def review(
        self,
        session: InterviewSession,
        snapshot: ContextSnapshot | None,
        language: str,
        progress: Progress,
    ) -> InterviewJudgement:
        calls: list[CallTrace] = []
        diagnostics: tuple[Check, ...] = ()
        adaptive = session.context.policy_version is not None
        try:
            units, past = await self._classify(session, calls)
        except LlmError:
            if not adaptive:
                raise
            units, past = answer_units(session), {}
            diagnostics = (
                Check(
                    "classification",
                    "unavailable",
                    "Diagnostic classification unavailable; recorded elicitation was retained.",
                ),
            )
        if adaptive:
            units, past, agreements = recorded_units(session, units)
            diagnostics = (*diagnostics, *agreements)
        rubrics = self.rubrics_for(session)
        context = evaluation_context(session, snapshot)
        references = [
            {"title": d.title, "text": d.text}
            for d in (snapshot.documents if snapshot else ())
            if d.kind is DocumentKind.RESOURCE
        ]
        requirements = (
            {
                f.id: f
                for f in snapshot.job_facts
                if f.kind in (FactKind.REQUIREMENT, FactKind.NICE_TO_HAVE)
            }
            if snapshot
            else {}
        )
        topics = {t.id: t.title for t in session.context.topics}
        unit_scores: list[Score] = []
        observations: list[Observation] = []
        coverage: dict[str, list[Evidence]] = {}
        checked_claims: dict[str, str] = {}
        dropped = sum(u.kind == "unclassified" for u in units)
        disputed = 0
        for index, unit in enumerate(units):
            await progress(index / (max(1, len(units)) + 1), f"{index + 1}/{len(units)}")
            if unit.kind not in rubrics:
                continue
            rubric = rubrics[unit.kind]
            answers = [t for t in session.candidate_turns() if t.seq in unit.answer_seqs]
            sources = {f"turn-{t.seq}": Source(t.text, t.seq) for t in answers}
            selected = {*unit.question_seqs, *unit.answer_seqs}
            # Each unit is judged on its own turns only (proposal section 5.2). Neighbouring
            # answers were observed to leak into judgements in both directions; follow-ups that
            # depend on an answer already belong to the same unit.
            unit_data: dict[str, object] = {
                "unit_id": unit.id,
                "kind": unit.kind,
                "topic": topics.get(unit.topic_id),
                "difficulty": session.config.difficulty.value,
                "turns": [turn_data(t) for t in session.turns if t.seq in selected],
            }
            if adaptive:
                unit_data["question_intents"] = [
                    {"question_seq": t.seq, **asdict(t.move.intent)}
                    for t in session.interviewer_turns()
                    if t.seq in unit.question_seqs and t.move.intent
                ]
            active = (
                tuple(c.id for c in rubric.criteria if c.id in elicited_criteria(session, unit))
                if adaptive
                else None
            )
            if adaptive and not past[unit.id]:
                active = tuple(
                    c
                    for c in active or ()
                    if c
                    not in {
                        "experience",
                        "ownership",
                        "specificity",
                        "results",
                        "reflection",
                        "followup_depth",
                    }
                )
            if adaptive:
                unit_data["assessable_criteria"] = active
            passes: list[tuple[Score, ...]] = []
            notes: tuple[Observation, ...] = ()
            for descending in (False, True):
                full = not descending
                output = await self._call(
                    calls,
                    "judge_descending" if descending else "judge_ascending",
                    unit.id,
                    self._judge_request(
                        context,
                        rubric,
                        unit_data,
                        descending,
                        language,
                        adaptive=adaptive,
                        active=active,
                    ),
                    unit_output(
                        active or (),
                        observations=full,
                        elicitation=True,
                        coverage=bool(requirements),
                    )
                    if adaptive
                    else self._outputs[(rubric.ref, full)],
                )
                if adaptive and full:
                    data = output.model_dump()
                    allowed = elicited_criteria(session, unit)
                    if not past[unit.id]:
                        allowed -= {
                            "experience",
                            "ownership",
                            "specificity",
                            "results",
                            "reflection",
                            "followup_depth",
                        }
                    kept_notes = [o for o in data["observations"] if o["criterion_id"] in allowed]
                    dropped += len(data["observations"]) - len(kept_notes)
                    data["observations"] = kept_notes
                    output = type(output).model_validate(data)
                scores, pass_notes, rejected = checked_judgements(
                    criterion_judgements(output),
                    rubric,
                    sources,
                    language=language,
                    unit_id=unit.id,
                )
                dropped += rejected
                scores = _without_unelicited(scores, unit, past[unit.id], language)
                if adaptive:
                    scores = elicited_scores(scores, session, unit, language)
                passes.append(scores)
                if full:
                    notes = pass_notes
                    for claim in unit_coverage(output):
                        evidence = checked_evidence(claim.evidence, sources)
                        if claim.requirement_id in requirements and evidence:
                            coverage.setdefault(claim.requirement_id, []).extend(evidence)
                        else:
                            dropped += 1
            kept: list[Observation] = []
            unit_disputed = False
            for note in _distinct(notes):
                if adaptive and note.kind == "question" and not note.text.rstrip().endswith("?"):
                    dropped += 1
                    continue
                if note.kind == "technical_error" and unit.kind != "technical":
                    # Corrections concern technical statements; on other units the label was
                    # observed to carry judgements about the candidate instead.
                    dropped += 1
                    continue
                if note.kind == "technical_error":
                    statement = " … ".join(e.quote for e in note.evidence)
                    if statement not in checked_claims:
                        checked_claims[statement] = await self._check_claim(
                            calls, unit, session, statement, references, language
                        )
                    if checked_claims[statement] != "incorrect":
                        # Two model readings disagree: the correction is not shown as an error
                        # and the unit's accuracy score is marked as unstable.
                        dropped += 1
                        disputed += 1
                        unit_disputed = True
                        continue
                kept.append(note)
            observations.extend(kept)
            paired = paired_scores(passes[0], passes[1])
            if unit_disputed:
                paired = tuple(
                    replace(s, unstable=True)
                    if s.criterion_id == "accuracy" and s.value is not None
                    else s
                    for s in paired
                )
            unit_scores.extend(
                replace(
                    s,
                    criterion_id=(
                        "common.autonomy"
                        if adaptive and s.criterion_id == "autonomy"
                        else f"{unit.kind}.{s.criterion_id}"
                    ),
                )
                for s in paired
            )
        scores = aggregate_scores(tuple(unit_scores))
        await progress(len(units) / (len(units) + 1), None)
        unique = _distinct(observations)
        summary, ordered, rejected = await self._synthesise(
            calls, scores, unique, language, adaptive=adaptive
        )
        dropped += rejected
        return InterviewJudgement(
            units,
            tuple(unit_scores),
            scores,
            (*summary, *ordered),
            dropped,
            (
                *diagnostics,
                *tuple(
                    Check(
                        f"requirement:{key}",
                        "discussed_model" if key in coverage else "not_shown",
                        fact.text,
                        tuple(dict.fromkeys(coverage.get(key, []))),
                    )
                    for key, fact in requirements.items()
                ),
            ),
            tuple(calls),
            disputed,
        )

    async def _classify(
        self, session: InterviewSession, calls: list[CallTrace]
    ) -> tuple[tuple[AnswerUnit, ...], dict[str, bool]]:
        units = answer_units(session)
        turns = {t.seq: t for t in session.turns}
        result: list[AnswerUnit] = []
        past: dict[str, bool] = {}
        for offset in range(0, len(units), 8):
            batch = units[offset : offset + 8]
            data = [
                {"unit_id": u.id, "questions": [turn_data(turns[n]) for n in u.question_seqs]}
                for u in batch
            ]
            prompt = self._prompts.render(
                "classify_units", 6 if session.context.policy_version else 5
            )
            request = ChatRequest(
                instructions=prompt.text,
                messages=(ChatMessage("user", json.dumps(data, ensure_ascii=False)),),
                temperature=0.1,
                presence_penalty=self.presence_penalty,
                max_output_tokens=200 + 60 * len(batch),
                reasoning="off",
            )
            kinds = await self._call(calls, "classify", None, request, KindsOut)
            result.extend(classified(batch, kinds))
            past.update(past_examples(batch, kinds))
        return tuple(result), past

    def _judge_request(
        self,
        context: dict[str, object],
        rubric: Rubric,
        unit: dict[str, object],
        descending: bool,
        language: str,
        *,
        adaptive: bool = False,
        active: tuple[str, ...] | None = None,
    ) -> ChatRequest:
        prompt = self._prompts.render(
            "judge_unit", 5 if adaptive else 3, language_name=_language_name(language)
        )
        payload = {
            # The approved context comes first and is identical in every judging request.
            "approved_context": context,
            "rubric": {
                "id": rubric.ref,
                "anchor_order": "descending" if descending else "ascending",
                "criteria": [
                    c
                    for c in rubric.data(descending=descending)
                    if active is None or c["id"] in active
                ],
            },
            "unit": unit,
            "task": (
                "Score every criterion. This pass returns scores only."
                if descending
                else "Score every criterion, then give observations and coverage."
            ),
        }
        thinking = self.judge_reasoning == "default"
        return ChatRequest(
            instructions=prompt.text,
            messages=(ChatMessage("user", json.dumps(payload, ensure_ascii=False)),),
            temperature=0.1,
            presence_penalty=self.presence_penalty,
            max_output_tokens=(
                _JUDGE_TOKENS[not descending]
                + (800 if adaptive else 0)
                + (_THINKING_TOKENS if thinking else 0)
            ),
            reasoning=self.judge_reasoning,
        )

    async def _check_claim(
        self,
        calls: list[CallTrace],
        unit: AnswerUnit,
        session: InterviewSession,
        statement: str,
        references: list[dict[str, str]],
        language: str,
    ) -> str:
        """Ask for an independent verdict, without showing the judge's correction."""
        turns = {t.seq: t for t in session.turns}
        payload: dict[str, object] = {
            "references": references,
            "question": " / ".join(str(turn_data(turns[n])["text"]) for n in unit.question_seqs),
            "answer": " / ".join(str(turn_data(turns[n])["text"]) for n in unit.answer_seqs),
            "statement": statement,
        }
        if session.context.policy_version:
            payload["confirmed_role"] = (
                asdict(session.context.role_profile) if session.context.role_profile else None
            )
        prompt = self._prompts.render(
            "check_claim",
            2 if session.context.policy_version else 1,
            language_name=_language_name(language),
        )
        request = ChatRequest(
            instructions=prompt.text,
            messages=(ChatMessage("user", json.dumps(payload, ensure_ascii=False)),),
            temperature=0.1,
            presence_penalty=self.presence_penalty,
            max_output_tokens=_CLAIM_TOKENS,
            reasoning="off",
        )
        return (await self._call(calls, "check_claim", unit.id, request, ClaimCheckOut)).verdict

    async def _synthesise(
        self,
        calls: list[CallTrace],
        scores: tuple[Score, ...],
        observations: Sequence[Observation],
        language: str,
        *,
        adaptive: bool = False,
    ) -> tuple[tuple[Observation, ...], tuple[Observation, ...], int]:
        """A summary over existing observations, which are referenced and never copied."""
        if not observations:
            return (), (), 0
        ids = {f"o{n + 1}": note for n, note in enumerate(observations)}
        payload = {
            "scale": "1 weakest to 5 strongest; null is not assessable",
            "scores": [
                {
                    "criterion_id": s.criterion_id,
                    "label": s.label,
                    "value": s.value,
                    "band": _band(s.value),
                    "answers": s.reason,
                }
                for s in scores
            ],
            "observations": [
                {
                    "id": key,
                    "unit_id": note.unit_id,
                    "kind": note.kind,
                    "text": note.text,
                    "quotes": [e.quote for e in note.evidence],
                }
                for key, note in ids.items()
            ],
        }
        prompt = self._prompts.render(
            "synthesise", 4 if adaptive else 3, language_name=_language_name(language)
        )
        request = ChatRequest(
            instructions=prompt.text,
            messages=(ChatMessage("user", json.dumps(payload, ensure_ascii=False)),),
            temperature=0.1,
            presence_penalty=self.presence_penalty,
            max_output_tokens=_SYNTHESIS_TOKENS,
            reasoning="off",
        )
        output = await self._call(
            calls, "synthesise", None, request, SelectionOut if adaptive else SynthesisOut
        )
        assert isinstance(output, (SelectionOut, SynthesisOut))
        chosen = list(dict.fromkeys((*output.priorities, *output.strengths)))
        selected = [ids[key] for key in chosen if key in ids]
        rejected = len(chosen) - len(selected)
        rest = tuple(note for note in observations if note not in selected)
        if not selected:
            # A summary that rests on no verified observation is not shown.
            return (), tuple(observations), rejected + 1
        evidence = tuple(dict.fromkeys(e for note in selected for e in note.evidence))[:3]
        if isinstance(output, SelectionOut):
            labels = ", ".join(score.label for score in scores if score.value is not None)
            text = (
                (
                    f"Le evidenze raccolte consentono un feedback su: {labels}. "
                    "I criteri non esplorati restano non valutabili."
                    if language == "it"
                    else f"The collected evidence supports feedback on: {labels}. "
                    "Unexplored criteria remain unavailable."
                )
                if labels
                else (
                    "Il feedback citato è disponibile qui sotto; "
                    "i giudizi numerici non sono sufficientemente supportati."
                    if language == "it"
                    else "Quoted feedback is available below; "
                    "numeric judgements are not sufficiently supported."
                )
            )
        else:
            text = output.summary
        summary = Observation("summary", text, evidence)
        return (summary,), (*selected, *rest), rejected

    async def _call[T: BaseModel](
        self,
        calls: list[CallTrace],
        phase: str,
        unit_id: str | None,
        request: ChatRequest,
        output: type[T],
    ) -> T:
        started = time.perf_counter()
        result = await complete_structured(self.model, request, output)
        attempts = result.attempts or (result.usage,)
        calls.append(
            CallTrace(
                phase=phase,
                unit_id=unit_id,
                reasoning=request.reasoning,
                attempts=len(attempts),
                prompt_tokens=_total(a.prompt_tokens for a in attempts),
                output_tokens=_total(a.output_tokens for a in attempts),
                duration_s=round(time.perf_counter() - started, 3),
                stop_reasons=tuple(a.stop_reason for a in attempts),
            )
        )
        return result.value


_PAST_CRITERIA = ("experience", "ownership", "results", "reflection")


def _without_unelicited(
    scores: tuple[Score, ...], unit: AnswerUnit, past_example: bool, language: str
) -> tuple[Score, ...]:
    """Not assessable when the questions did not ask for it, whatever the judge scored."""
    it = language == "it"
    reasons = {}
    if len(unit.question_seqs) < 2:
        reasons["followup_depth"] = (
            "Approfondimento non richiesto." if it else "Follow-up not elicited."
        )
    if not past_example:
        for criterion in _PAST_CRITERIA:
            reasons[criterion] = (
                "Nessuna domanda chiedeva un esempio passato."
                if it
                else "No question asked for a past example."
            )
    return tuple(
        replace(s, value=None, evidence=(), reason=reasons[s.criterion_id])
        if s.criterion_id in reasons
        else s
        for s in scores
    )


def _distinct(observations: Sequence[Observation]) -> tuple[Observation, ...]:
    """One observation per unit, kind and quoted evidence; the first wording is kept."""
    seen: dict[tuple[Any, ...], Observation] = {}
    for note in observations:
        key = (note.unit_id, note.kind, tuple(e.quote for e in note.evidence))
        seen.setdefault(key, note)
    return tuple(seen.values())


def _total(values: Iterable[int | None]) -> int | None:
    numbers = [v for v in values if v is not None]
    return sum(numbers) if numbers else None


def _band(value: float | None) -> str:
    """Words for the synthesis, computed here so the summary cannot misread the scale."""
    if value is None:
        return "not assessable"
    if value <= 2:
        return "weak"
    return "strong" if value >= 4 else "mixed"


def _language_name(language: str) -> str:
    return "Italian" if language == "it" else "English"
