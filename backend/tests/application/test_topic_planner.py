from __future__ import annotations

import pytest

from probeloop.ai.fake import FakeChatModel
from probeloop.interview.application.planner import TopicPlanner
from probeloop.interview.domain.model import Difficulty, InterviewConfig, InterviewType, Language


@pytest.mark.asyncio
async def test_practice_questions_are_delimited_suggestions() -> None:
    model = FakeChatModel(
        [
            '{"topics":[{"title":"Background and experience","reason":"Relevance"},'
            '{"title":"Personal contribution","reason":"Practice"}]}'
        ]
    )
    topics = await TopicPlanner(model).plan(
        InterviewConfig(InterviewType.HR, Difficulty.MEDIUM, Language.ITALIAN, 600),
        "CV brief",
        "Role brief",
        ("What was your personal contribution?",),
    )
    assert topics[-1].title == "Candidate questions and closing"
    assert "What was your personal contribution?" in model.requests[0].instructions
    assert "untrusted suggestions" in model.requests[0].instructions
