"""Deterministic allocation of candidate engagement time, independent of model latency."""

from collections.abc import Mapping
from dataclasses import dataclass

from probeloop.interview.domain.model import Topic, TopicCoverage

MIN_TOPIC_S = 45.0
MAX_TOPIC_S = 240.0
MAX_HINTS = 2


@dataclass(frozen=True, slots=True)
class TopicWindow:
    topic_id: str
    budget_s: float
    spent_s: float
    available: bool


def topic_windows(
    topics: tuple[Topic, ...],
    coverage: Mapping[str, TopicCoverage],
    spent: Mapping[str, float],
    remaining_s: float,
) -> tuple[TopicWindow, ...]:
    """Allocate remaining time by priority and uncovered objectives; never grade this clock.

    A topic's spent time survives leaving it, pausing and reconnecting. The global closing
    policy always takes precedence over these ordinary windows, including the minimum.
    """
    unfinished = [
        t
        for t in topics
        if t.rubric_kind != "logistics" and coverage.get(t.id) is not TopicCoverage.COVERED
    ]
    weight = sum(t.priority for t in unfinished) or 1
    windows = []
    for topic in topics:
        budget = min(MAX_TOPIC_S, max(MIN_TOPIC_S, remaining_s * topic.priority / weight))
        used = max(0.0, spent.get(topic.id, 0.0))
        available = topic in unfinished and used < budget and remaining_s > 0
        windows.append(TopicWindow(topic.id, round(budget, 1), round(used, 1), available))
    return tuple(windows)
