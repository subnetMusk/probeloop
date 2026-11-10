import json
from dataclasses import replace

import pytest

from probeloop.ai.fake import FakeChatModel
from probeloop.ai.prompts import PromptRenderer
from probeloop.ai.structured import StructuredOutputError
from probeloop.context.domain.model import Fact, FactKind, FactOrigin, Review, RoleProfile, Subject
from probeloop.interview.application.adaptive_interviewer import (
    AdaptiveChoice,
    AdaptiveHeader,
    adaptive_request,
    checked_header,
    selected_facts,
    validate_header,
)
from probeloop.interview.application.llm_interviewer import LlmInterviewer
from probeloop.interview.application.orchestrator import SessionOrchestrator
from probeloop.interview.application.ports import MoveDelta, MoveDone, MoveRequest
from probeloop.interview.domain.model import (
    CandidateTurn,
    InterviewContext,
    InterviewerMove,
    InterviewerTurn,
    InterviewSession,
    MoveAction,
    MovePurpose,
    RevisionSource,
    Topic,
    TranscriptRevision,
    TurnIntent,
)
from probeloop.interview.domain.time_policy import TimeDirective
from tests.conftest import EventRecorder, FakeClock, MemoryStore, ScriptedInterviewer, make_session


def request() -> MoveRequest:
    session = make_session()
    context = InterviewContext(
        "",
        "",
        (
            Topic(
                "t1",
                "Economic reasoning",
                "Explore uncertainty",
                "technical",
                3,
                criteria=("reasoning", "problem_solving", "autonomy"),
                solvable=True,
            ),
            Topic("t2", "Closing", rubric_kind="logistics"),
        ),
        role_profile=RoleProfile("Economics", "Economist", "junior", confirmed=True),
        policy_version="adaptive.v1",
    )
    return MoveRequest(session.config, context, (), session.coverage, TimeDirective.NORMAL, 300)


def test_prompt_uses_source_words_and_omits_unasserted_personal_inferences() -> None:
    req = request()
    facts = (
        Fact(
            "declared",
            Subject.CANDIDATE,
            FactKind.PROJECT,
            "A sweeping summary",
            FactOrigin.DECLARED,
            "doc",
            "Built a small analysis under supervision.",
        ),
        Fact(
            "inferred",
            Subject.CANDIDATE,
            FactKind.SKILL,
            "Model-only personal inference",
            FactOrigin.INFERRED,
        ),
        Fact(
            "corrected",
            Subject.CANDIDATE,
            FactKind.PROJECT,
            "Unverified interpretation",
            FactOrigin.INFERRED,
            review=Review.CORRECTED,
            corrected="I reviewed the observations myself.",
        ),
    )
    req = replace(req, context=replace(req.context, facts=facts))
    assert {f.id for f in selected_facts(req)} == {"declared", "corrected"}
    payload, _ = adaptive_request(
        PromptRenderer("probeloop.interview"),
        req,
        language_name="English",
        type_guidance="professional",
        difficulty_guidance="medium",
        temperature=0.2,
        top_p=0.9,
    )
    text = payload.messages[0].content
    assert "Built a small analysis under supervision." in text
    assert "A sweeping summary" not in text
    assert "Model-only personal inference" not in text
    assert "I reviewed the observations myself." in text


def header(**changes: object) -> AdaptiveHeader:
    return AdaptiveHeader.model_validate(
        {
            "action": "new_topic",
            "topic_id": "t1",
            "purpose": "new_topic",
            "past_example": False,
            "elicited_criteria": ["reasoning", "autonomy"],
            "fact_ids": [],
            "answer_seq": None,
            "hint_level": 0,
            "covered_topic_ids": [],
            **changes,
        }
    )


def answer(seq: int) -> CandidateTurn:
    return CandidateTurn(
        seq,
        0,
        0,
        (TranscriptRevision(1, "I am unsure about the next step.", RevisionSource.STT, 0),),
    )


async def test_one_model_call_keeps_role_context_and_validates_metadata_before_streaming() -> None:
    output = {
        **{
            k: v
            for k, v in header().model_dump(mode="json").items()
            if k in AdaptiveChoice.model_fields
        },
        "utterance": "What would you check first? A second question?",
    }
    model = FakeChatModel([json.dumps(output)], chunk_size=7)
    events = [event async for event in LlmInterviewer(model).next_move(request())]
    assert len(model.requests) == 1
    assert "junior" in model.requests[0].messages[0].content
    assert "Economics" in model.requests[0].messages[0].content
    assert (
        "".join(e.text for e in events if isinstance(e, MoveDelta)) == "What would you check first?"
    )
    assert isinstance(events[-1], MoveDone)
    assert events[-1].move.intent is not None


@pytest.mark.parametrize(
    "changes",
    [
        {"fact_ids": ["invented-cv-fact"]},
        {"topic_id": "invented-objective"},
    ],
)
async def test_invalid_intent_never_emits_text_or_audio(changes: dict[str, object]) -> None:
    output = {
        **{
            k: v
            for k, v in header(**changes).model_dump(mode="json").items()
            if k in AdaptiveChoice.model_fields
        },
        "utterance": "Unsupported question?",
    }
    model = FakeChatModel([json.dumps(output)])
    emitted = []

    async def consume() -> None:
        async for event in LlmInterviewer(model).next_move(request()):
            emitted.append(event)

    with pytest.raises(StructuredOutputError):
        await consume()
    assert emitted == []


def test_control_fields_and_unelicited_criteria_are_derived_in_code() -> None:
    base = {k: v for k, v in header().model_dump().items() if k in AdaptiveChoice.model_fields}
    choice = AdaptiveChoice.model_validate(
        {
            **base,
            "purpose": "clarification",
            "elicited_criteria": ["reasoning", "ownership"],
            "covered_topic_ids": ["t1"],
        }
    )
    req = replace(request(), turns=(answer(1),))
    clean = checked_header(choice, req)
    assert clean.action == "clarify"
    assert clean.hint_level == 0
    assert clean.answer_seq == 1
    assert clean.elicited_criteria == []
    assert clean.covered_topic_ids == []
    reasoning = AdaptiveChoice.model_validate({**base, "elicited_criteria": ["reasoning"]})
    assert checked_header(reasoning, request()).elicited_criteria == ["reasoning", "autonomy"]


def test_budget_expiry_and_global_closing_override_a_follow_up() -> None:
    req = replace(request(), topic_engagement_s={"t1": 241})
    with pytest.raises(StructuredOutputError, match="exhausted"):
        validate_header(header(), req)
    with pytest.raises(StructuredOutputError, match="global closing"):
        validate_header(header(), replace(request(), directive=TimeDirective.FINAL_QUESTION))


def test_two_hints_are_allowed_but_not_a_third_or_a_hint_for_remembered_experience() -> None:
    initial = InterviewerTurn(
        0, 0, 0, InterviewerMove(MoveAction.NEW_TOPIC, "t1", "Reasoning?", intent=header().intent())
    )
    req = replace(request(), turns=(initial, answer(1)))
    first = header(action="follow_up", purpose="hint", answer_seq=1, hint_level=1)
    validate_header(first, req)
    hint1 = InterviewerTurn(
        2,
        0,
        0,
        InterviewerMove(MoveAction.FOLLOW_UP, "t1", "First partial cue?", intent=first.intent()),
    )
    req = replace(req, turns=(*req.turns, hint1, answer(3)))
    second = header(action="follow_up", purpose="hint", answer_seq=3, hint_level=2)
    validate_header(second, req)
    hint2 = InterviewerTurn(
        4,
        0,
        0,
        InterviewerMove(MoveAction.FOLLOW_UP, "t1", "Second partial cue?", intent=second.intent()),
    )
    with pytest.raises(StructuredOutputError, match="at most two"):
        validate_header(
            header(action="follow_up", purpose="hint", answer_seq=5, hint_level=2),
            replace(req, turns=(*req.turns, hint2, answer(5))),
        )
    historical = replace(
        initial,
        move=replace(initial.move, intent=TurnIntent(MovePurpose.NEW_TOPIC, past_example=True)),
    )
    with pytest.raises(StructuredOutputError, match="existing solvable task"):
        validate_header(first, replace(request(), turns=(historical, answer(1))))


def test_legitimate_clarification_is_not_recorded_as_a_hint_or_new_scored_requirement() -> None:
    req = replace(request(), turns=(answer(1),))
    clarification = header(
        action="clarify", purpose="clarification", answer_seq=1, elicited_criteria=[]
    )
    validate_header(clarification, req)
    assert clarification.hint_level == 0


def test_provider_failure_still_moves_past_an_exhausted_objective() -> None:
    req = request()
    context = replace(
        req.context,
        topics=(
            req.context.topics[0],
            Topic("t3", "Evidence checks", rubric_kind="technical", criteria=("reasoning",)),
            req.context.topics[1],
        ),
    )
    session = InterviewSession("synthetic", req.config, context, 0)
    recorder = EventRecorder()
    orchestrator = SessionOrchestrator(
        session,
        interviewer=ScriptedInterviewer(),
        store=MemoryStore(),
        clock=FakeClock(),
        sink=recorder,
    )
    move = orchestrator._adaptive_fallback(
        replace(req, context=context, topic_engagement_s={"t1": 241})
    )
    assert move.topic_id == "t3"
    assert move.action is MoveAction.NEW_TOPIC
    assert move.fallback
    assert move.intent is None
