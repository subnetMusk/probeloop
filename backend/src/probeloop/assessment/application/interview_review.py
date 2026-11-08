"""Classify, judge twice, verify and aggregate a frozen transcript with its approved context."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace

from probeloop.ai.ports import ChatMessage, ChatModel, ChatRequest
from probeloop.ai.prompts import PromptRenderer
from probeloop.ai.structured import complete_structured
from probeloop.assessment.application.evidence import Source, checked_evidence, checked_judgements
from probeloop.assessment.application.rubrics import Rubric, load_rubric
from probeloop.assessment.application.schemas import SynthesisOut, UnitJudgementsOut
from probeloop.assessment.application.segmentation import KindsOut, answer_units, classified
from probeloop.assessment.domain.model import AnswerUnit, Check, Evidence, Observation, Score
from probeloop.assessment.domain.units import aggregate_scores, paired_scores
from probeloop.context.domain.model import ContextSnapshot, FactKind
from probeloop.interview.domain.model import CandidateTurn, InterviewSession, Turn
from probeloop.platform.jobs import Progress


def turn_data(turn: Turn) -> dict[str, object]:
    return {
        "seq": turn.seq,
        "source_id": f"turn-{turn.seq}",
        "speaker": turn.speaker.value,
        "text": turn.text if isinstance(turn, CandidateTurn) else turn.move.utterance,
    }


@dataclass(frozen=True)
class InterviewJudgement:
    units: tuple[AnswerUnit, ...]
    unit_scores: tuple[Score, ...]
    scores: tuple[Score, ...]
    observations: tuple[Observation, ...]
    dropped: int
    coverage: tuple[Check, ...]


class InterviewReviewer:
    def __init__(self, model: ChatModel) -> None:
        self.model = model
        self.rubrics = {
            name: load_rubric(name) for name in ("hr", "behavioral", "technical", "hypothetical")
        }
        self._prompts = PromptRenderer("probeloop.assessment")

    async def review(
        self,
        session: InterviewSession,
        snapshot: ContextSnapshot | None,
        language: str,
        progress: Progress,
    ) -> InterviewJudgement:
        units = answer_units(session)
        turns = {t.seq: t for t in session.turns}
        result_units: list[AnswerUnit] = []
        for offset in range(0, len(units), 8):
            batch = units[offset : offset + 8]
            classification_data = [
                {"unit_id": u.id, "questions": [turn_data(turns[n]) for n in u.question_seqs]}
                for u in batch
            ]
            request = self._request("classify_units", classification_data, tokens=1200)
            classification = (await complete_structured(self.model, request, KindsOut)).value
            result_units.extend(classified(batch, classification))
        units = tuple(result_units)
        unit_scores: list[Score] = []
        observations: list[Observation] = []
        requirements = (
            {
                f.id: f
                for f in snapshot.job_facts
                if f.kind in (FactKind.REQUIREMENT, FactKind.NICE_TO_HAVE)
            }
            if snapshot
            else {}
        )
        coverage: dict[str, list[Evidence]] = {}
        dropped = sum(u.kind == "unclassified" for u in units)
        for index, unit in enumerate(units):
            await progress(index / max(1, len(units)), f"{index + 1}/{len(units)}")
            if unit.kind not in self.rubrics:
                continue
            rubric = self.rubrics[unit.kind]
            sources = {
                f"turn-{answer.seq}": Source(answer.text, answer.seq)
                for answer in session.candidate_turns()
                if answer.seq in unit.answer_seqs
            }
            selected = set((*unit.question_seqs, *unit.answer_seqs))
            unit_turns = [turn_data(t) for t in session.turns if t.seq in selected]
            positions = [i for i, t in enumerate(session.turns) if t.seq in selected]
            surrounding = [
                turn_data(t)
                for t in session.turns[max(0, min(positions) - 2) : max(positions) + 3]
                if t.seq not in selected
            ]
            judge_data = {
                "unit_id": unit.id,
                "kind": unit.kind,
                "turns": unit_turns,
                "surrounding_turns": surrounding,
                "approved_snapshot": asdict(snapshot) if snapshot else None,
                "interview_context": asdict(session.context),
                "difficulty": session.config.difficulty.value,
            }
            judgements = []
            for descending in (False, True):
                request = self._request(
                    "judge_unit",
                    judge_data,
                    tokens=9000,
                    language=language,
                    rubric=rubric,
                    descending=descending,
                )
                judgement = (
                    await complete_structured(self.model, request, UnitJudgementsOut)
                ).value
                scores, notes, rejected = checked_judgements(
                    judgement,
                    rubric,
                    sources,
                    language=language,
                    unit_id=unit.id,
                )
                if len(unit.question_seqs) < 2:
                    scores = tuple(
                        replace(
                            s,
                            value=None,
                            reason="Approfondimento non richiesto."
                            if language == "it"
                            else "Follow-up not elicited.",
                        )
                        if s.criterion_id == "followup_depth"
                        else s
                        for s in scores
                    )
                judgements.append(scores)
                observations.extend(notes)
                for claim in judgement.coverage:
                    evidence = checked_evidence(claim.evidence, sources)
                    if claim.requirement_id in requirements and evidence:
                        coverage.setdefault(claim.requirement_id, []).extend(evidence)
                    else:
                        dropped += 1
                dropped += rejected
            unit_scores.extend(
                replace(s, criterion_id=f"{unit.kind}.{s.criterion_id}")
                for s in paired_scores(*judgements)
            )
        scores = aggregate_scores(tuple(unit_scores))
        # Synthesis consumes verified evidence in bounded groups. Every candidate turn remains
        # available to at least one group; long input is rejected rather than silently truncated.
        assessed_units = tuple(u for u in units if u.kind in self.rubrics)
        for offset in range(0, len(assessed_units), 2):
            batch = assessed_units[offset : offset + 2]
            selected_answers = {n for u in batch for n in u.answer_seqs}
            selected_units = {u.id for u in batch}
            candidates = [t for t in session.candidate_turns() if t.seq in selected_answers]
            synthesis_data = {
                "turns": [turn_data(t) for t in candidates],
                "observations": [asdict(n) for n in observations if n.unit_id in selected_units],
                "scores": [
                    {"criterion_id": s.criterion_id, "value": s.value, "unstable": s.unstable}
                    for s in unit_scores
                    if s.unit_id in selected_units
                ],
            }
            request = self._request("synthesise", synthesis_data, tokens=2400, language=language)
            synthesis = (await complete_structured(self.model, request, SynthesisOut)).value
            sources = {f"turn-{t.seq}": Source(t.text, t.seq) for t in candidates}
            _, notes, rejected = checked_judgements(
                synthesis, self.rubrics["hr"], sources, language=language
            )
            observations.extend(
                n for n in notes if n.kind in ("summary", "strength", "improvement", "question")
            )
            dropped += rejected
        return InterviewJudgement(
            units,
            tuple(unit_scores),
            scores,
            tuple(dict.fromkeys(observations)),
            dropped,
            tuple(
                Check(
                    f"requirement:{key}",
                    "discussed_model" if key in coverage else "not_shown",
                    fact.text,
                    tuple(dict.fromkeys(coverage.get(key, []))),
                )
                for key, fact in requirements.items()
            ),
        )

    def _request(
        self,
        name: str,
        data: object,
        *,
        tokens: int,
        language: str = "en",
        rubric: Rubric | None = None,
        descending: bool = False,
    ) -> ChatRequest:
        prompt = self._prompts.render(
            name,
            2 if name in ("judge_unit", "synthesise") else 1,
            language_name="Italian" if language == "it" else "English",
            rubric_ref=rubric.ref if rubric else "",
            rubric=rubric.prompt(descending=descending) if rubric else "",
        )
        return ChatRequest(
            instructions=prompt.text
            + "\nLimit internal reasoning to 600 tokens; reserve the rest for valid JSON.",
            messages=(ChatMessage("user", json.dumps(data, ensure_ascii=False)),),
            temperature=0.1,
            max_output_tokens=tokens,
            reasoning="default" if name == "judge_unit" else "off",
        )
