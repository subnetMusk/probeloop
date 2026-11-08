"""The topic plan of an interview prepared from the candidate's documents.

The model proposes the topics from the briefs; a closing topic is always added last. If the
model fails, the default topics of the interview type are used, so an interview can always start.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field

from probeloop.ai.ports import ChatMessage, ChatModel, ChatRequest, LlmError
from probeloop.ai.prompts import PromptRenderer
from probeloop.ai.structured import complete_structured
from probeloop.interview.application.catalog import default_topics
from probeloop.interview.application.llm_interviewer import (
    LANGUAGE_NAMES,
    TYPE_GUIDANCE,
    TYPE_LABELS,
)
from probeloop.interview.domain.model import InterviewConfig, Topic

logger = logging.getLogger(__name__)

PLAN_PROMPT_VERSION = 1
CLOSING = "Candidate questions and closing"


class TopicOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=5, max_length=200)
    reason: str = Field(max_length=300)


class PlanOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topics: list[TopicOut] = Field(min_length=2, max_length=8)


def topic_count(minutes: float) -> int:
    """Topics before the closing one: about one every three minutes, between 3 and 6."""
    return max(3, min(6, round(minutes / 3)))


class TopicPlanner:
    def __init__(self, model: ChatModel) -> None:
        self._model = model
        self._prompts = PromptRenderer("probeloop.interview")

    async def plan(
        self, config: InterviewConfig, candidate_brief: str, job_brief: str
    ) -> tuple[Topic, ...]:
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
