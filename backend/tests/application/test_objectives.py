import json
from dataclasses import asdict

from probeloop.ai.fake import FakeChatModel
from probeloop.ai.ports import LlmError
from probeloop.context.domain.model import RoleProfile
from probeloop.interview.application.planner import TopicPlanner
from probeloop.interview.domain.model import Difficulty, InterviewConfig, InterviewType, Language
from tests.context.test_preparation import ROLE


def config() -> InterviewConfig:
    return InterviewConfig(InterviewType.TECHNICAL, Difficulty.MEDIUM, Language.ENGLISH, 600)


async def test_objectives_keep_provenance_and_intent_instead_of_a_question_script() -> None:
    profile = RoleProfile("Economics", "Economist", "junior", confirmed=True)
    goal = {
        "title": "Economic reasoning",
        "objective": "Explore assumptions and uncertainty.",
        "rubric_kind": "technical",
        "priority": 3,
        "fact_ids": [ROLE.id],
        "criteria": ["reasoning", "ownership", "communication"],
        "past_example": True,
        "solvable": True,
    }
    model = FakeChatModel(
        [json.dumps({"objectives": [goal, {**goal, "title": "Evidence checks"}]})]
    )
    topics = await TopicPlanner(model).plan(config(), "", "", role_profile=profile, facts=(ROLE,))
    assert topics[0].fact_ids == (ROLE.id,)
    assert topics[0].criteria == ("reasoning", "ownership")
    assert topics[0].solvable
    assert topics[0].past_example
    assert topics[0].objective == goal["objective"]
    assert topics[-1].rubric_kind == "logistics"
    payload = json.loads(model.requests[0].messages[0].content)
    assert payload["confirmed_role"] == json.loads(json.dumps(asdict(profile)))
    assert "not a list of questions" in model.requests[0].instructions


async def test_unknown_goal_references_trigger_a_role_grounded_fallback() -> None:
    profile = RoleProfile("Medicine", "Medical trainee", "CT1 under supervision", confirmed=True)
    goal = {
        "title": "Invented experience",
        "objective": "Explore an unsupported claim.",
        "rubric_kind": "technical",
        "priority": 1,
        "fact_ids": ["made-up"],
        "criteria": ["reasoning"],
        "past_example": False,
        "solvable": True,
    }
    model = FakeChatModel([json.dumps({"objectives": [goal, goal]})])
    topics = await TopicPlanner(model).plan(config(), "", "", role_profile=profile)
    assert all(not t.fact_ids for t in topics)
    assert "Medical trainee" in topics[0].title
    assert all("query" not in t.title.lower() and "software" not in t.title.lower() for t in topics)


async def test_provider_failure_without_a_cv_does_not_invent_personal_experience() -> None:
    profile = RoleProfile("Teaching", "Teacher", "trainee", confirmed=True)
    topics = await TopicPlanner(FakeChatModel([LlmError("offline")])).plan(
        config(), "", "", role_profile=profile
    )
    assert all(not t.past_example for t in topics)
    assert all(not t.fact_ids for t in topics)


async def test_documentary_links_alone_do_not_replace_exploring_actual_experience() -> None:
    profile = RoleProfile("Economics", "Economist", "junior", confirmed=True)
    goal = {
        "title": "Future professional reasoning",
        "objective": "Explore a hypothetical task.",
        "rubric_kind": "technical",
        "priority": 2,
        "fact_ids": [ROLE.id],
        "criteria": ["reasoning"],
        "past_example": False,
        "solvable": True,
    }
    topics = await TopicPlanner(FakeChatModel([json.dumps({"objectives": [goal, goal]})])).plan(
        config(),
        "",
        "",
        role_profile=profile,
        facts=(ROLE,),
    )
    assert topics[0].past_example
    assert topics[0].fact_ids == (ROLE.id,)
    assert "ownership" in topics[0].criteria
