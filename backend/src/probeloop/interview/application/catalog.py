"""Default topics and the sample brief bundled with the package."""

from __future__ import annotations

from importlib import resources
from typing import Any

import yaml

from probeloop.interview.domain.model import InterviewContext, InterviewType, Topic


def _load(name: str) -> Any:
    text = resources.files("probeloop.interview").joinpath("catalog", name).read_text("utf-8")
    return yaml.safe_load(text)


def default_topics(interview_type: InterviewType) -> tuple[Topic, ...]:
    entries = _load("topics.yaml")[interview_type.value]
    return tuple(Topic(id=str(e["id"]), title=str(e["title"])) for e in entries)


def default_context(
    interview_type: InterviewType,
    *,
    candidate_brief: str | None = None,
    job_brief: str | None = None,
) -> InterviewContext:
    sample = _load("sample_brief.yaml")
    return InterviewContext(
        candidate_brief=(candidate_brief or sample["candidate"]).strip(),
        job_brief=(job_brief or sample["job"]).strip(),
        topics=default_topics(interview_type),
    )
