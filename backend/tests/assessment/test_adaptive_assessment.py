import json
from dataclasses import replace

from probeloop.ai.fake import FakeChatModel
from probeloop.ai.ports import ChatRequest, LlmError
from probeloop.assessment.application.interview_review import InterviewReviewer
from probeloop.assessment.application.rubrics import load_rubric
from probeloop.assessment.application.schemas import ReportData
from probeloop.assessment.domain.comparability import assessment_profile_id
from probeloop.assessment.domain.model import QuestionTrace
from probeloop.assessment.domain.progress import scorer_key
from probeloop.assessment.infrastructure.fake import scripted_assessment
from probeloop.context.domain.model import RoleProfile
from probeloop.interview.domain.model import (
    EndReason,
    InterviewContext,
    InterviewerMove,
    InterviewSession,
    MoveAction,
    MovePurpose,
    Topic,
    TurnIntent,
)
from tests.assessment.test_exports import sample_report
from tests.conftest import make_session


def session() -> InterviewSession:
    context = InterviewContext(
        "",
        "",
        (
            Topic("t1", "Economic reasoning", rubric_kind="technical", solvable=True),
            Topic("t2", "Communicating uncertainty", rubric_kind="hypothetical", solvable=True),
        ),
        role_profile=RoleProfile("Economics", "Economist", "junior", confirmed=True),
        policy_version="adaptive.v1",
    )
    session = InterviewSession("synthetic", make_session().config, context, 0)
    session.start(0)
    for i, topic in enumerate(context.topics):
        now = i * 60
        intent = TurnIntent(
            MovePurpose.NEW_TOPIC,
            elicited_criteria=("reasoning", "autonomy"),
            rubric_kind=topic.rubric_kind,
        )
        session.record_move(
            InterviewerMove(
                MoveAction.NEW_TOPIC,
                topic.id,
                "How would you check the assumptions and explain uncertainty?",
                intent=intent,
            ),
            now,
        )
        session.finish_speaking(now + 1)
        session.start_answer(now + 2)
        session.finish_answer(now + 20)
        session.record_answer(
            "I would check the definitions and explain the limits of the evidence.", now + 21
        )
    session.end(EndReason.USER_ENDED, 150)
    return session


async def progress(_fraction: float, _message: str | None) -> None:
    pass


async def test_recorded_elicitation_routes_rubrics_and_counts_autonomy_once() -> None:
    model = FakeChatModel([scripted_assessment])  # Deliberately diagnoses both questions as HR.
    reviewer = InterviewReviewer(model)
    result = await reviewer.review(session(), None, "en", progress)
    assert [u.kind for u in result.units] == ["technical", "hypothetical"]
    assert [s.criterion_id for s in result.scores].count("common.autonomy") == 1
    assert next(s for s in result.scores if s.criterion_id == "common.autonomy").value == 3
    assert next(s for s in result.scores if s.criterion_id == "technical.ownership").value is None
    assert next(s for s in result.scores if s.criterion_id == "technical.depth").value is None
    assert any(c.status == "diagnostic_disagreement" for c in result.coverage)
    assert "technical.v3" in reviewer.rubric_ref_for(session())
    assert "judge_unit@v6" in reviewer.prompt_ref_for(session())
    judged = [
        json.loads(r.messages[0].content)
        for r in model.requests
        if '"unit"' in r.messages[0].content
    ]
    assert judged[0]["approved_context"]["confirmed_role"]["seniority"] == "junior"
    assert {c["id"] for c in judged[0]["rubric"]["criteria"]} == {"reasoning", "autonomy"}


async def test_a_failed_diagnostic_classifier_does_not_prevent_intent_based_assessment() -> None:
    def script(request: ChatRequest) -> str:
        if isinstance(json.loads(request.messages[0].content), list):
            raise LlmError("diagnostic unavailable")
        return scripted_assessment(request)

    result = await InterviewReviewer(FakeChatModel([script])).review(
        session(), None, "en", progress
    )
    assert result.units[0].kind == "technical"
    assert any(score.value is not None for score in result.scores)
    assert any(check.status == "unavailable" for check in result.coverage)


async def test_prose_cannot_penalize_an_unelicited_criterion() -> None:
    def script(request: ChatRequest) -> str:
        data = json.loads(scripted_assessment(request))
        if "scores" in data:
            for observation in data.get("observations", []):
                observation["criterion_id"] = "ownership"
                observation["text"] = "Unasked ownership criticism."
        return json.dumps(data)

    result = await InterviewReviewer(FakeChatModel([script])).review(
        session(), None, "en", progress
    )
    assert not result.observations
    assert result.dropped >= 2


def hinted_session() -> InterviewSession:
    """One reasoning task followed by a recorded hint; neither intent lists autonomy."""
    context = InterviewContext(
        "",
        "",
        (Topic("t1", "Real and nominal growth", rubric_kind="technical", solvable=True),),
        role_profile=RoleProfile("Economics", "Economist", "junior", confirmed=True),
        policy_version="adaptive.v1",
    )
    session = InterviewSession("hinted", make_session().config, context, 0)
    session.start(0)
    moves = (
        (MoveAction.NEW_TOPIC, TurnIntent(MovePurpose.NEW_TOPIC, elicited_criteria=("accuracy",))),
        (
            MoveAction.FOLLOW_UP,
            TurnIntent(
                MovePurpose.HINT,
                elicited_criteria=("accuracy",),
                answer_seq=1,
                hint_level=1,
            ),
        ),
    )
    for i, (action, intent) in enumerate(moves):
        now = i * 60
        intent = replace(intent, rubric_kind="technical")
        session.record_move(
            InterviewerMove(action, "t1", "How would you remove the price effect?", intent=intent),
            now,
        )
        session.finish_speaking(now + 1)
        session.start_answer(now + 2)
        session.finish_answer(now + 20)
        session.record_answer("I would divide the nominal factor by the price factor.", now + 21)
    session.end(EndReason.USER_ENDED, 150)
    return session


async def test_a_recorded_hint_makes_autonomy_assessable_without_a_deduction_rule() -> None:
    model = FakeChatModel([scripted_assessment])
    result = await InterviewReviewer(model).review(hinted_session(), None, "en", progress)
    autonomy = next(s for s in result.scores if s.criterion_id == "common.autonomy")
    assert autonomy.value is not None
    judged = [
        json.loads(r.messages[0].content)
        for r in model.requests
        if '"unit"' in r.messages[0].content
    ]
    assert {c["id"] for c in judged[0]["rubric"]["criteria"]} == {"accuracy", "autonomy"}


def test_policy_context_roundtrips_and_level_changes_break_comparability() -> None:
    current = session()
    profile = current.context.role_profile
    assert profile is not None
    trace = tuple(
        QuestionTrace(t.seq, t.move.topic_id, t.move.utterance, t.move.intent)
        for t in current.interviewer_turns()
        if t.move.intent
    )
    report = replace(
        sample_report(),
        policy_version="adaptive.v1",
        role_profile=profile,
        objectives=current.context.topics,
        question_trace=trace,
        assessment_profile_id=assessment_profile_id(profile, "adaptive.v1"),
    )
    assert ReportData.of(report).domain() == report
    senior = replace(
        report,
        assessment_profile_id=assessment_profile_id(
            replace(profile, seniority="senior"), "adaptive.v1"
        ),
    )
    assert scorer_key(report) != scorer_key(senior)
    assert (
        assessment_profile_id(replace(profile, rationale="New wording"), "adaptive.v1")
        == report.assessment_profile_id
    )


def test_autonomy_anchors_are_shared_and_rubrics_fit_the_eight_criterion_boundary() -> None:
    rubrics = [
        load_rubric(name, version=version)
        for name, version in (("technical", 3), ("hr", 2), ("behavioral", 2), ("hypothetical", 2))
    ]
    anchors = [next(c for c in rubric.criteria if c.id == "autonomy").anchors for rubric in rubrics]
    assert all(value == anchors[0] for value in anchors)
    assert all(len(rubric.criteria) <= 8 for rubric in rubrics)
