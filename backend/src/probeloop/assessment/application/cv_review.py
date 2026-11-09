"""CV judgement against a frozen target, with deterministic checks and source verification."""

from __future__ import annotations

import json
import re

from probeloop.ai.ports import ChatMessage, ChatModel, ChatRequest
from probeloop.ai.prompts import PromptRenderer
from probeloop.ai.structured import complete_structured
from probeloop.assessment.application.cv_checks import cv_checks
from probeloop.assessment.application.evidence import Source, checked_judgements
from probeloop.assessment.application.labels import label
from probeloop.assessment.application.rubrics import Rubric
from probeloop.assessment.application.schemas import criterion_judgements, cv_output
from probeloop.assessment.domain.model import Check, Observation, Score
from probeloop.context.application.analysis import chunks
from probeloop.context.application.snapshots import job_brief
from probeloop.context.domain.model import ContextSnapshot, DocumentKind
from probeloop.platform.jobs import Progress


class CvReviewer:
    prompt_ref = "review_cv@v2:off"

    def __init__(self, model: ChatModel, rubric: Rubric) -> None:
        self.model = model
        self.rubric = rubric
        self._prompts = PromptRenderer("probeloop.assessment")

    async def review(
        self,
        snapshot: ContextSnapshot,
        language: str,
        progress: Progress,
    ) -> tuple[tuple[Score, ...], tuple[Observation, ...], tuple[Check, ...], int]:
        cv = next((d for d in snapshot.documents if d.kind is DocumentKind.CV), None)
        if cv is None:
            raise ValueError("the approved context has no CV")
        pieces = chunks(cv.text, size=3000)
        collected: dict[str, list[Score]] = {}
        observations: list[Observation] = []
        dropped = 0
        for index, piece in enumerate(pieces):
            await progress(index / len(pieces), f"{index + 1}/{len(pieces)}")
            prompt = self._prompts.render(
                "review_cv",
                2,
                language_name="Italian" if language == "it" else "English",
                source_id=cv.id,
                rubric_ref=self.rubric.ref,
                rubric=self.rubric.prompt(),
                target=job_brief(snapshot),
                index=index + 1,
                passages=len(pieces),
            )
            request = ChatRequest(
                instructions=prompt.text,
                messages=(
                    ChatMessage(
                        "user", json.dumps({"source_id": cv.id, "text": piece}, ensure_ascii=False)
                    ),
                ),
                temperature=0.1,
                presence_penalty=0,
                max_output_tokens=3500,
                reasoning="off",
            )
            schema = cv_output(tuple(c.id for c in self.rubric.criteria))
            output = criterion_judgements(
                (await complete_structured(self.model, request, schema)).value
            )
            # An unvisited URL proves only that the link is printed, never skill or readability.
            evidence_lists = [s.evidence for s in output.scores] + [
                n.evidence for n in output.observations
            ]
            for evidence_list in evidence_lists:
                evidence_list[:] = [
                    e for e in evidence_list if not re.fullmatch(r"https?://\S+", e.quote.strip())
                ]
            scores, notes, rejected = checked_judgements(
                output,
                self.rubric,
                {cv.id: Source(piece)},
                language=language,
            )
            for score in scores:
                collected.setdefault(score.criterion_id, []).append(score)
            observations.extend(n for n in notes if n.kind != "technical_error")
            dropped += rejected + sum(n.kind == "technical_error" for n in notes)
        aggregated = []
        for criterion in self.rubric.criteria:
            candidates = collected.get(criterion.id, [])
            available = [s for s in candidates if s.value is not None]
            if available:
                # Equal passage weights; each judgement still exposes its supporting excerpts.
                values = [s.value for s in available if s.value is not None]
                aggregated.append(
                    Score(
                        criterion.id,
                        label(criterion.label, language),
                        round(sum(values) / len(values), 2),
                        "\n".join(dict.fromkeys(s.reason for s in available)),
                        tuple(dict.fromkeys(e for s in available for e in s.evidence)),
                    )
                )
            else:
                aggregated.append(
                    Score(
                        criterion.id,
                        label(criterion.label, language),
                        None,
                        "Evidenza insufficiente." if language == "it" else "Insufficient evidence.",
                    )
                )
        return tuple(aggregated), tuple(observations), cv_checks(cv, language), dropped
