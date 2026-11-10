import json
from dataclasses import replace

import pytest

from probeloop.ai.fake import FakeChatModel
from probeloop.ai.ports import ChatRequest, estimated_tokens
from probeloop.ai.prompts import PromptRenderer
from probeloop.ai.structured import StructuredOutputError
from probeloop.context.domain.model import Fact, FactKind, FactOrigin, Review, RoleProfile, Subject
from probeloop.interview.application.adaptive_interviewer import (
    AdaptiveChoice,
    AdaptiveDecision,
    AdaptiveHeader,
    adaptive_request,
    checked_header,
    selected_facts,
    validate_header,
)
from probeloop.interview.application.llm_interviewer import LlmInterviewer
from probeloop.interview.application.orchestrator import SessionOrchestrator
from probeloop.interview.application.phrases import (
    CLOSING_FAREWELL,
    CONTINUE,
    FALLBACK,
    OPENING,
    TOPIC_CHANGE,
    TOPIC_QUESTION,
)
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


def test_prompt_fits_the_context_window_keeping_the_latest_answer_verbatim() -> None:
    req = request()
    facts = tuple(
        Fact(
            f"f{n}",
            Subject.CANDIDATE,
            FactKind.PROJECT,
            "Short summary",
            FactOrigin.DECLARED,
            "doc",
            f"Long documentary passage {n}: " + "measured, reviewed and reported. " * 12,
        )
        for n in range(40)
    )
    turns: list[InterviewerTurn | CandidateTurn] = []
    for n in range(0, 60, 2):
        turns.append(
            InterviewerTurn(
                n,
                0,
                0,
                InterviewerMove(
                    MoveAction.FOLLOW_UP,
                    "t1",
                    f"Question {n}: " + "what would you check and why? " * 6,
                    intent=TurnIntent(MovePurpose.REASONING_PROBE, rubric_kind="technical"),
                ),
            )
        )
        text = f"Answer {n + 1}: " + "I would compare the series and explain limits. " * 8
        turns.append(
            replace(
                answer(n + 1),
                revisions=(TranscriptRevision(1, text, RevisionSource.USER_EDIT, 1),),
            )
        )
    req = replace(req, context=replace(req.context, facts=facts), turns=tuple(turns))

    def build(window: int | None) -> ChatRequest:
        chat, _ = adaptive_request(
            PromptRenderer("probeloop.interview"),
            req,
            language_name="English",
            type_guidance="professional",
            difficulty_guidance="medium",
            temperature=0.2,
            top_p=0.9,
            context_window=window,
        )
        return chat

    assert estimated_tokens(build(None)) > 8192
    fitted = build(8192)
    assert estimated_tokens(fitted) <= 8192
    content = "".join(m.content for m in fitted.messages)
    assert turns[-1].text in content
    assert "earlier_turns_abridged" in content
    assert len(req.context.facts) == 40


def test_explicit_recall_limit_requires_a_grounded_quote_and_a_change_of_approach() -> None:
    req = request()
    prior = InterviewerTurn(
        0,
        0,
        0,
        InterviewerMove(
            MoveAction.NEW_TOPIC,
            "t1",
            "Describe a decision.",
            intent=TurnIntent(MovePurpose.NEW_TOPIC, True, rubric_kind="technical"),
        ),
    )
    reply = replace(
        answer(1),
        revisions=(
            TranscriptRevision(
                1, "I cannot recall that detail accurately.", RevisionSource.USER_EDIT, 1
            ),
        ),
    )
    req = replace(req, turns=(prior, reply))
    limit = {"kind": "cannot_recall", "quote": "I cannot recall that detail accurately."}
    with pytest.raises(StructuredOutputError, match="change the evidence approach"):
        validate_header(
            header(
                action="follow_up",
                purpose="evidence_probe",
                past_example=True,
                answer_seq=1,
                answer_limit=limit,
            ),
            req,
        )
    # Asking again for the missing detail is not a clarification.
    with pytest.raises(StructuredOutputError, match="change the evidence approach"):
        validate_header(
            header(
                action="clarify",
                purpose="clarification",
                answer_seq=1,
                answer_limit=limit,
                elicited_criteria=[],
            ),
            req,
        )
    validate_header(
        header(action="follow_up", purpose="reasoning_probe", answer_seq=1, answer_limit=limit), req
    )
    with pytest.raises(StructuredOutputError, match="latest answer"):
        validate_header(
            header(
                action="follow_up",
                purpose="reasoning_probe",
                answer_seq=1,
                answer_limit={"kind": "cannot_recall", "quote": "An invented limitation."},
            ),
            req,
        )


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
        "".join(e.text for e in events if isinstance(e, MoveDelta))
        == "Buongiorno. Consideriamo uno scenario ipotetico. What would you check first?"
    )
    assert isinstance(events[-1], MoveDone)
    assert events[-1].move.intent is not None


async def test_the_spoken_experience_frame_elicits_the_recorded_contribution_criteria() -> None:
    req = request()
    topics = (replace(req.context.topics[0], past_example=True), req.context.topics[1])
    req = replace(req, context=replace(req.context, topics=topics))
    choice = AdaptiveChoice(
        topic_id="t1",
        purpose=MovePurpose.NEW_TOPIC,
        past_example=False,
        elicited_criteria=["reasoning"],
        fact_ids=[],
        covered_topic_ids=[],
    )
    model = FakeChatModel(
        [
            json.dumps(
                {**choice.model_dump(mode="json"), "utterance": "How did you check the result?"}
            )
        ]
    )
    events = [event async for event in LlmInterviewer(model).next_move(req)]
    assert isinstance(events[-1], MoveDone)
    move = events[-1].move
    assert move.intent is not None
    assert move.intent.past_example
    assert {"ownership", "experience"} <= set(move.intent.elicited_criteria)
    assert "esempio reale" in move.utterance
    assert "contributo personale" in move.utterance
    assert "".join(e.text for e in events if isinstance(e, MoveDelta)).strip() == move.utterance


def decision(**changes: object) -> str:
    return json.dumps(
        {
            "answer_limit": None,
            "topic_id": "t1",
            "purpose": "new_topic",
            "past_example": False,
            "elicited_criteria": ["reasoning"],
            "fact_ids": [],
            "covered_topic_ids": [],
            "focus": "How the candidate would check an uncertain estimate.",
            **changes,
        }
    )


async def test_two_step_turn_validates_the_decision_before_any_question_text() -> None:
    utterance = json.dumps({"utterance": "Suppose the estimate is uncertain: what first? More?"})
    model = FakeChatModel([decision(), utterance], chunk_size=5)
    events = [e async for e in LlmInterviewer(model, two_step=True).next_move(request())]
    assert len(model.requests) == 2
    first, second = model.requests
    assert "utterance" not in json.dumps(first.response_schema)
    assert first.messages[-1].content.endswith("Do not write the question yet.")
    # The question call extends the decision call, so a provider can reuse the processed prefix.
    assert second.messages[: len(first.messages)] == first.messages
    assert "hypothetical" in second.messages[-1].content
    text = "".join(e.text for e in events if isinstance(e, MoveDelta))
    assert text == "Buongiorno. Suppose the estimate is uncertain: what first?"
    assert isinstance(events[-1], MoveDone)
    assert events[-1].move.intent is not None
    assert "autonomy" in events[-1].move.intent.elicited_criteria
    assert events[-1].move.prompt_ref is not None
    assert "interviewer_adaptive@v3" in events[-1].move.prompt_ref
    assert "two_step" in events[-1].move.prompt_ref


async def test_a_rejected_decision_is_returned_once_with_its_reason() -> None:
    model = FakeChatModel(
        [decision(topic_id="t9"), decision(), json.dumps({"utterance": "What would you check?"})]
    )
    events = [e async for e in LlmInterviewer(model, two_step=True).next_move(request())]
    assert len(model.requests) == 3
    assert "unknown objective" in model.requests[1].messages[-1].content
    assert isinstance(events[-1], MoveDone)


async def test_two_step_keeps_the_decided_frame_and_states_limits_for_the_question() -> None:
    req = request()
    topics = (replace(req.context.topics[0], past_example=True), req.context.topics[1])
    prior = InterviewerTurn(
        0,
        0,
        0,
        InterviewerMove(
            MoveAction.NEW_TOPIC,
            "t1",
            "Describe a decision you made.",
            intent=TurnIntent(MovePurpose.NEW_TOPIC, True, rubric_kind="technical"),
        ),
    )
    reply = replace(
        answer(1),
        revisions=(
            TranscriptRevision(
                1, "I cannot recall that detail accurately.", RevisionSource.USER_EDIT, 1
            ),
        ),
    )
    req = replace(req, context=replace(req.context, topics=topics), turns=(prior, reply))
    limit = {"kind": "cannot_recall", "quote": "I cannot recall that detail accurately."}
    model = FakeChatModel(
        [
            json.dumps({"quotes": []}),
            decision(purpose="reasoning_probe", answer_limit=limit),
            json.dumps({"utterance": "Assume a similar case: what would you check?"}),
        ]
    )
    events = [e async for e in LlmInterviewer(model, two_step=True).next_move(req)]
    move = events[-1]
    assert isinstance(move, MoveDone)
    assert move.move.intent is not None
    assert not move.move.intent.past_example
    assert move.move.utterance == "Assume a similar case: what would you check?"
    assert "Do not ask for that detail again" in model.requests[2].messages[-1].content
    # Both labels are recorded for audits and future classifier data.
    assert move.move.intent.answer_limit == "cannot_recall"
    assert move.move.intent.focus == "How the candidate would check an uncertain estimate."


def recalled(text: str) -> MoveRequest:
    """An actual-experience question on t1 followed by the given answer."""
    req = request()
    topics = (replace(req.context.topics[0], past_example=True), req.context.topics[1])
    prior = InterviewerTurn(
        0,
        0,
        0,
        InterviewerMove(
            MoveAction.NEW_TOPIC,
            "t1",
            "Describe a release you planned.",
            intent=TurnIntent(MovePurpose.NEW_TOPIC, True, rubric_kind="technical"),
        ),
    )
    reply = replace(answer(1), revisions=(TranscriptRevision(1, text, RevisionSource.STT, 1),))
    return replace(req, context=replace(req.context, topics=topics), turns=(prior, reply))


async def test_two_step_reads_stated_limits_before_deciding_and_keeps_only_quoted_ones() -> None:
    req = recalled("I planned the rollout in two waves, but I cannot recall the exact error rates.")
    limits = {"quotes": ["I cannot recall  the exact error rates", "I never ran a rollout before"]}
    model = FakeChatModel(
        [
            json.dumps(limits),
            decision(purpose="evidence_probe", past_example=True, elicited_criteria=[]),
            json.dumps({"utterance": "Who decided when the second wave started?"}),
        ]
    )
    events = [e async for e in LlmInterviewer(model, two_step=True).next_move(req)]
    assert len(model.requests) == 3
    read, decide, ask = model.requests
    assert "exact error rates" in read.messages[-1].content
    assert "Describe a release you planned." in read.messages[-1].content
    # Only the quote found in the answer reaches the decision and the question.
    assert "I cannot recall the exact error rates" in decide.messages[-1].content
    assert "I never ran a rollout" not in decide.messages[-1].content
    assert ask.messages[: len(decide.messages)] == decide.messages
    assert 'said: "I cannot recall the exact error rates". Do not ask for that detail' in (
        ask.messages[-1].content
    )
    done = events[-1]
    assert isinstance(done, MoveDone)
    # A statement read by the separate step constrains the question, not the whole episode.
    assert (done.move.action, done.move.topic_id) == (MoveAction.FOLLOW_UP, "t1")
    assert done.move.intent is not None
    assert done.move.intent.past_example
    assert done.move.intent.answer_limit == "stated_limit"
    assert done.move.prompt_ref is not None
    assert "interviewer_limits@v1" in done.move.prompt_ref


async def test_a_malformed_limits_reply_leaves_the_turn_to_the_decision() -> None:
    req = recalled("I planned the rollout in two waves.")
    model = FakeChatModel(
        [
            "not json",
            decision(purpose="evidence_probe", past_example=True, elicited_criteria=[]),
            json.dumps({"utterance": "Who decided when the second wave started?"}),
        ]
    )
    events = [e async for e in LlmInterviewer(model, two_step=True).next_move(req)]
    assert len(model.requests) == 3
    assert "stated limits" not in model.requests[1].messages[-1].content
    done = events[-1]
    assert isinstance(done, MoveDone)
    assert done.move.intent is not None
    assert done.move.intent.answer_limit is None


async def test_two_step_decodes_only_legal_objectives_and_repairs_a_misnamed_topic_change() -> None:
    req = request()
    extra = Topic("t3", "Evidence checks", rubric_kind="technical", criteria=("reasoning",))
    context = replace(req.context, topics=(req.context.topics[0], extra, req.context.topics[1]))
    req = replace(req, context=context, topic_engagement_s={"t1": 241})
    model = FakeChatModel(
        [
            decision(topic_id="t3", purpose="reasoning_probe"),
            json.dumps({"utterance": "How would you check the evidence?"}),
        ]
    )
    events = [e async for e in LlmInterviewer(model, two_step=True).next_move(req)]
    schema = model.requests[0].response_schema
    assert schema is not None
    assert schema["properties"]["topic_id"]["enum"] == ["t3"]
    assert list(schema["properties"]) == list(AdaptiveDecision.model_fields)
    done = events[-1]
    assert isinstance(done, MoveDone)
    assert (done.move.action, done.move.topic_id) == (MoveAction.NEW_TOPIC, "t3")


async def test_code_decides_a_closing_that_is_the_only_legal_move() -> None:
    prior = asked("t1")
    req = replace(request(), directive=TimeDirective.FINAL_QUESTION, turns=(prior, answer(1)))
    model = FakeChatModel([json.dumps({"utterance": "Do you have any questions for us?"})])
    events = [e async for e in LlmInterviewer(model, two_step=True).next_move(req)]
    assert len(model.requests) == 1
    done = events[-1]
    assert isinstance(done, MoveDone)
    assert (done.move.action, done.move.topic_id) == (MoveAction.WRAP_UP, "t2")
    assert done.move.intent is not None
    assert done.move.intent.purpose is MovePurpose.CLOSING
    assert done.move.intent.focus is None  # code made this decision

    wrap_up = asked("t2", action=MoveAction.WRAP_UP, fallback=True)
    req = replace(request(), turns=(prior, answer(1), wrap_up, answer(3)))
    model = FakeChatModel([json.dumps({"utterance": "Thank you, goodbye."})])
    events = [e async for e in LlmInterviewer(model, two_step=True).next_move(req)]
    done = events[-1]
    assert isinstance(done, MoveDone)
    assert done.move.action is MoveAction.END
    assert "supplied documents" in model.requests[0].messages[-1].content


def test_a_started_closing_ends_and_an_early_one_waits_for_the_objectives() -> None:
    closing = {"topic_id": "t2", "purpose": "closing", "elicited_criteria": []}
    started = (asked("t1"), answer(1), asked("t2", action=MoveAction.WRAP_UP, fallback=True))
    validate_header(
        header(action="end", **closing), replace(request(), turns=(*started, answer(3)))
    )
    with pytest.raises(StructuredOutputError, match="time left precede the closing"):
        validate_header(
            header(action="wrap_up", **closing), replace(request(), turns=(asked("t1"), answer(1)))
        )


def test_open_reasoning_can_elicit_autonomy_without_admitting_solution_hints() -> None:
    req = request()
    topics = (replace(req.context.topics[0], solvable=False), req.context.topics[1])
    req = replace(req, context=replace(req.context, topics=topics))
    choice = AdaptiveChoice(
        topic_id="t1",
        purpose=MovePurpose.NEW_TOPIC,
        past_example=False,
        elicited_criteria=["reasoning"],
        fact_ids=[],
        covered_topic_ids=[],
    )
    assert "autonomy" in checked_header(choice, req).elicited_criteria


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


def fallback_for(req: MoveRequest, *turns: InterviewerTurn | CandidateTurn) -> InterviewerMove:
    context = replace(
        req.context,
        topics=(
            req.context.topics[0],
            Topic("t3", "Internal English title", rubric_kind="behavioral", past_example=True),
            req.context.topics[1],
        ),
    )
    session = InterviewSession("synthetic", req.config, context, 0)
    orchestrator = SessionOrchestrator(
        session,
        interviewer=ScriptedInterviewer(),
        store=MemoryStore(),
        clock=FakeClock(),
        sink=EventRecorder(),
    )
    return orchestrator._adaptive_fallback(replace(req, context=context, turns=turns))


def asked(
    topic: str, *, action: MoveAction = MoveAction.FOLLOW_UP, fallback: bool = False
) -> InterviewerTurn:
    return InterviewerTurn(0, 0, 0, InterviewerMove(action, topic, "Question?", fallback=fallback))


def test_a_fallback_never_asks_the_candidate_to_repeat_a_recorded_answer() -> None:
    language = request().config.language
    move = fallback_for(request(), asked("t1"), answer(1))
    assert (move.action, move.topic_id) == (MoveAction.CLARIFY, "t1")
    assert move.utterance == CONTINUE[language]
    assert move.utterance != FALLBACK[language]


def test_a_second_fallback_in_a_row_moves_on_without_speaking_the_internal_title() -> None:
    language = request().config.language
    move = fallback_for(request(), asked("t1", fallback=True), answer(1))
    assert (move.action, move.topic_id) == (MoveAction.NEW_TOPIC, "t3")
    assert move.utterance == f"{TOPIC_CHANGE[language]} {TOPIC_QUESTION[(language, True)]}"
    assert "Internal English title" not in move.utterance


def test_a_failed_opening_starts_an_objective_with_a_greeting() -> None:
    language = request().config.language
    move = fallback_for(request())
    assert move.action is MoveAction.NEW_TOPIC
    assert move.utterance.startswith(OPENING[language])


def test_a_fallback_never_reopens_a_started_closing() -> None:
    language = request().config.language
    move = fallback_for(request(), asked("t2", action=MoveAction.WRAP_UP), answer(1))
    assert (move.action, move.topic_id) == (MoveAction.END, "t2")
    assert move.utterance == CLOSING_FAREWELL[language]
