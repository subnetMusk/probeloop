"""The topic plan of an interview prepared from the candidate's documents.

The model proposes the topics from the briefs; a closing topic is always added last. If the
model fails, the default topics of the interview type are used, so an interview can always start.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from probeloop.ai.ports import ChatMessage, ChatModel, ChatRequest, LlmError
from probeloop.ai.prompts import PromptRenderer
from probeloop.ai.structured import complete_structured
from probeloop.context.application.snapshots import select_facts
from probeloop.context.domain.model import Fact, FactOrigin, RoleProfile, Subject
from probeloop.interview.application.catalog import default_topics
from probeloop.interview.application.llm_interviewer import (
    LANGUAGE_NAMES,
    TYPE_GUIDANCE,
    TYPE_LABELS,
)
from probeloop.interview.domain.model import ASSESSMENT_CRITERIA, InterviewConfig, Topic

logger = logging.getLogger(__name__)

PLAN_PROMPT_VERSION = 2
CLOSING = "Candidate questions and closing"


class TopicOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=5, max_length=200)
    reason: str = Field(max_length=300)


class PlanOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topics: list[TopicOut] = Field(min_length=2, max_length=8)


class ObjectiveOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=200)
    objective: str = Field(min_length=5, max_length=400)
    rubric_kind: Literal["technical", "hr", "behavioral", "hypothetical"]
    priority: int = Field(ge=1, le=3)
    fact_ids: list[str] = Field(max_length=12)
    criteria: list[str] = Field(min_length=1, max_length=8)
    past_example: bool
    solvable: bool


class ObjectivesOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objectives: list[ObjectiveOut] = Field(min_length=2, max_length=6)


def topic_count(minutes: float) -> int:
    """Topics before the closing one: about one every three minutes, between 3 and 6."""
    return max(3, min(6, round(minutes / 3)))


class TopicPlanner:
    def __init__(self, model: ChatModel) -> None:
        self._model = model
        self._prompts = PromptRenderer("probeloop.interview")

    async def plan(
        self,
        config: InterviewConfig,
        candidate_brief: str,
        job_brief: str,
        practice_questions: tuple[str, ...] = (),
        *,
        role_profile: RoleProfile | None = None,
        facts: tuple[Fact, ...] = (),
    ) -> tuple[Topic, ...]:
        if role_profile is not None:
            if not role_profile.confirmed:
                raise ValueError("confirm the target role before planning")
            return await self._objectives(config, role_profile, facts, practice_questions)
        minutes = config.target_duration_s / 60
        count = topic_count(minutes)
        prompt = self._prompts.render(
            "plan_topics",
            PLAN_PROMPT_VERSION,
            interview_type_label=TYPE_LABELS[config.interview_type],
            interview_type_guidance=TYPE_GUIDANCE[config.interview_type],
            language_name=LANGUAGE_NAMES[config.language],
            minutes=round(minutes),
            count=count,
            candidate_brief=candidate_brief,
            job_brief=job_brief,
            practice_questions=practice_questions,
        )
        request = ChatRequest(
            instructions=prompt.text,
            messages=(ChatMessage("user", "Plan the topics."),),
            temperature=0.3,
            max_output_tokens=900,
        )
        try:
            plan = (await complete_structured(self._model, request, PlanOut)).value
        except LlmError:
            logger.warning("topic planning failed; using the default topics")
            return default_topics(config.interview_type)
        titles = [" ".join(t.title.split()) for t in plan.topics[:count]]
        titles = [t for t in titles if CLOSING.lower() not in t.lower()]
        topics = [Topic(id=f"t{n}", title=title) for n, title in enumerate(titles, start=1)]
        topics.append(Topic(id=f"t{len(topics) + 1}", title=CLOSING))
        return tuple(topics)

    async def _objectives(
        self,
        config: InterviewConfig,
        profile: RoleProfile,
        facts: tuple[Fact, ...],
        suggestions: tuple[str, ...],
    ) -> tuple[Topic, ...]:
        # Model interpretations remain available to the interviewer as such, but cannot
        # substantiate an objective's personal/documentary reference.
        verified = {f.id: f for f in facts if f.origin is not FactOrigin.INFERRED}
        query = " ".join((profile.target_role, *profile.competencies))
        selected = tuple(
            f
            for subject in Subject
            for f in select_facts(
                tuple(f for f in verified.values() if f.subject is subject),
                query=query,
                preferred_ids=profile.basis_fact_ids,
                max_chars=6000,
            )
        )
        prompt = self._prompts.render(
            "plan_objectives",
            1,
            count=topic_count(config.target_duration_s / 60),
            minutes=round(config.target_duration_s / 60),
            interview_type_label=TYPE_LABELS[config.interview_type],
            interview_type_guidance=TYPE_GUIDANCE[config.interview_type],
            language_name=LANGUAGE_NAMES[config.language],
        )
        request = ChatRequest(
            instructions=prompt.text,
            messages=(
                ChatMessage(
                    "user",
                    json.dumps(
                        {
                            "confirmed_role": asdict(profile),
                            "difficulty": config.difficulty.value,
                            "facts": [
                                {
                                    "id": f.id,
                                    "subject": f.subject.value,
                                    "kind": f.kind.value,
                                    "text": f.text,
                                    "origin": f.origin.value,
                                }
                                for f in selected
                            ],
                            "rubric_families": ASSESSMENT_CRITERIA,
                            "untrusted_practice_suggestions": suggestions,
                        },
                        ensure_ascii=False,
                    ),
                ),
            ),
            temperature=0.2,
            max_output_tokens=2200,
        )
        try:
            result = (await complete_structured(self._model, request, ObjectivesOut)).value
            topics: list[Topic] = []
            for item in result.objectives[: topic_count(config.target_duration_s / 60)]:
                if not set(item.fact_ids) <= {f.id for f in selected}:
                    raise ValueError("unknown objective provenance")
                if "?" in item.title:
                    raise ValueError("an objective is not a scripted question")
                criteria = tuple(
                    dict.fromkeys(
                        c for c in item.criteria if c in ASSESSMENT_CRITERIA[item.rubric_kind]
                    )
                )
                if not criteria:
                    raise ValueError("objective has no supported criteria")
                topics.append(
                    Topic(
                        f"t{len(topics) + 1}",
                        item.title.strip(),
                        item.objective.strip(),
                        item.rubric_kind,
                        item.priority,
                        tuple(dict.fromkeys(item.fact_ids)),
                        criteria,
                        item.past_example,
                        item.solvable,
                    )
                )
            candidate = [f for f in verified.values() if f.subject is Subject.CANDIDATE]
            if candidate and not any(set(t.fact_ids) & {f.id for f in candidate} for t in topics):
                topics[0] = experience_objective(candidate[0], config)
        except (LlmError, ValueError) as exc:
            logger.warning(
                "objective planning failed; using role-grounded objectives",
                extra={
                    "error_type": type(exc).__name__,
                    "reason": str(exc) if isinstance(exc, ValueError) else type(exc).__name__,
                },
            )
            topics = fallback_objectives(config, profile, tuple(verified.values()))
        topics.append(Topic(f"t{len(topics) + 1}", CLOSING, rubric_kind="logistics"))
        return tuple(topics)


def experience_objective(fact: Fact, config: InterviewConfig) -> Topic:
    kind = "technical" if config.interview_type.value in ("technical", "mixed") else "behavioral"
    criteria = (
        ("experience", "ownership", "reasoning")
        if kind == "technical"
        else ("ownership", "results", "reflection")
    )
    return Topic(
        "t1",
        "Relevant documented experience",
        "Explore own actions, responsibility and learning in this documented experience.",
        kind,
        3,
        (fact.id,),
        criteria,
        True,
    )


def fallback_objectives(
    config: InterviewConfig, profile: RoleProfile, facts: tuple[Fact, ...]
) -> list[Topic]:
    candidate = next((f for f in facts if f.subject is Subject.CANDIDATE), None)
    topics = [experience_objective(candidate, config)] if candidate else []
    kind = "technical" if config.interview_type.value in ("technical", "mixed") else "hypothetical"
    criteria = (
        ("problem_solving", "reasoning", "autonomy")
        if kind == "technical"
        else ("clarification", "plan", "autonomy")
    )
    for competency in (
        profile.competencies or (f"Professional judgement in {profile.target_role}",)
    )[:3]:
        topics.append(
            Topic(
                f"t{len(topics) + 1}",
                competency,
                "Explore reasoning, constraints and limits appropriate to the confirmed "
                "role and supervision.",
                kind,
                2,
                (),
                criteria,
                False,
                True,
            )
        )
    if config.interview_type.value == "hr":
        topics.append(
            Topic(
                f"t{len(topics) + 1}",
                "Role motivation",
                "Explore interest in the confirmed role and relevant background.",
                "hr",
                2,
                (),
                ("motivation", "relevance"),
            )
        )
    if config.interview_type.value == "hr":
        topics = [topics[-1], *topics[:-1]]
    topics = topics[: topic_count(config.target_duration_s / 60)]
    return [
        Topic(
            f"t{i}",
            t.title,
            t.objective,
            t.rubric_kind,
            t.priority,
            t.fact_ids,
            t.criteria,
            t.past_example,
            t.solvable,
        )
        for i, t in enumerate(topics, 1)
    ]
