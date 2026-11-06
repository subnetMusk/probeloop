from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import pytest

from probeloop.interview.domain.model import (
    EndReason,
    InterviewConfig,
    InterviewContext,
    InterviewerMove,
    InterviewSession,
    InvalidConfigError,
    InvalidTransitionError,
    MoveAction,
    MoveStatus,
    Phase,
    SessionStatus,
    Topic,
    TopicCoverage,
)
from tests.conftest import make_config, make_context, make_session

MOVE = InterviewerMove(MoveAction.NEW_TOPIC, "t1", "Mi parli di lei?")
END = InterviewerMove(MoveAction.END, "t3", "Grazie e arrivederci.")


def in_phase(phase: Phase) -> InterviewSession:
    s = make_session()
    s.start(0)
    steps: list[Callable[[], None]] = [
        lambda: s.record_move(MOVE, 1),
        lambda: s.finish_speaking(2),
        lambda: s.start_answer(3),
        lambda: s.finish_answer(4),
    ]
    order = [
        Phase.INTERVIEWER_THINKING,
        Phase.INTERVIEWER_SPEAKING,
        Phase.AWAITING_CANDIDATE,
        Phase.CANDIDATE_SPEAKING,
        Phase.FINALIZING_TRANSCRIPT,
    ]
    for step in steps[: order.index(phase)]:
        step()
    assert s.phase is phase
    return s


OPERATIONS: dict[str, Callable[[InterviewSession], None]] = {
    "record_move": lambda s: s.record_move(MOVE, 10),
    "finish_speaking": lambda s: s.finish_speaking(10),
    "start_answer": lambda s: s.start_answer(10),
    "finish_answer": lambda s: s.finish_answer(10),
    "record_answer": lambda s: s.record_answer("risposta", 10),
}

ALLOWED = {
    Phase.INTERVIEWER_THINKING: "record_move",
    Phase.INTERVIEWER_SPEAKING: "finish_speaking",
    Phase.AWAITING_CANDIDATE: "start_answer",
    Phase.CANDIDATE_SPEAKING: "finish_answer",
    Phase.FINALIZING_TRANSCRIPT: "record_answer",
}

NEXT = {
    Phase.INTERVIEWER_THINKING: Phase.INTERVIEWER_SPEAKING,
    Phase.INTERVIEWER_SPEAKING: Phase.AWAITING_CANDIDATE,
    Phase.AWAITING_CANDIDATE: Phase.CANDIDATE_SPEAKING,
    Phase.CANDIDATE_SPEAKING: Phase.FINALIZING_TRANSCRIPT,
    Phase.FINALIZING_TRANSCRIPT: Phase.INTERVIEWER_THINKING,
}


@pytest.mark.parametrize("phase", list(Phase))
@pytest.mark.parametrize("operation", list(OPERATIONS))
def test_transition_table(phase: Phase, operation: str) -> None:
    session = in_phase(phase)
    if ALLOWED[phase] == operation:
        OPERATIONS[operation](session)
        assert session.phase is NEXT[phase]
    else:
        with pytest.raises(InvalidTransitionError):
            OPERATIONS[operation](session)


@pytest.mark.parametrize("operation", list(OPERATIONS))
def test_turn_operations_require_a_started_session(operation: str) -> None:
    with pytest.raises(InvalidTransitionError):
        OPERATIONS[operation](make_session())


def test_end_move_closes_the_session_after_speaking() -> None:
    s = make_session()
    s.start(0)
    s.record_move(END, 5)
    s.finish_speaking(6)
    assert s.status is SessionStatus.ENDED
    assert s.end_reason is EndReason.COMPLETED
    assert s.phase is None


def test_moves_update_topic_coverage() -> None:
    s = make_session()
    s.start(0)
    s.record_move(
        InterviewerMove(MoveAction.NEW_TOPIC, "t2", "Progetto?", covered_topic_ids=("t1", "zz")), 1
    )
    assert s.coverage == {
        "t1": TopicCoverage.COVERED,
        "t2": TopicCoverage.IN_PROGRESS,
        "t3": TopicCoverage.NOT_STARTED,
    }


def test_move_with_unknown_topic_is_rejected() -> None:
    s = make_session()
    s.start(0)
    with pytest.raises(InvalidConfigError):
        s.record_move(InterviewerMove(MoveAction.NEW_TOPIC, "t9", "?"), 1)


def test_elapsed_excludes_pauses() -> None:
    s = make_session()
    s.start(100)
    s.pause(160)
    assert s.elapsed_s(500) == 60
    s.resume(400)
    assert s.elapsed_s(430) == 90
    s.end(EndReason.USER_ENDED, 450)
    assert s.elapsed_s(10_000) == 110


@pytest.mark.parametrize(
    ("phase", "expected"),
    [
        (Phase.INTERVIEWER_THINKING, Phase.INTERVIEWER_THINKING),
        (Phase.INTERVIEWER_SPEAKING, Phase.AWAITING_CANDIDATE),
        (Phase.AWAITING_CANDIDATE, Phase.AWAITING_CANDIDATE),
        (Phase.CANDIDATE_SPEAKING, Phase.AWAITING_CANDIDATE),
        (Phase.FINALIZING_TRANSCRIPT, Phase.FINALIZING_TRANSCRIPT),
    ],
)
def test_resume_phase(phase: Phase, expected: Phase) -> None:
    s = in_phase(phase)
    s.pause(20)
    assert s.status is SessionStatus.PAUSED
    s.resume(30)
    assert s.status is SessionStatus.IN_PROGRESS
    assert s.phase is expected


def test_pause_while_thinking_keeps_a_partial_move() -> None:
    s = in_phase(Phase.INTERVIEWER_THINKING)
    partial = InterviewerMove(MoveAction.FOLLOW_UP, "t1", "Mi parli", status=MoveStatus.INTERRUPTED)
    s.pause(5, partial_move=partial)
    s.resume(9)
    assert s.phase is Phase.AWAITING_CANDIDATE
    assert s.last_move() == partial


def test_pause_without_partial_regenerates_the_move() -> None:
    s = in_phase(Phase.INTERVIEWER_THINKING)
    s.pause(5, partial_move=InterviewerMove(MoveAction.FOLLOW_UP, "t1", "   "))
    s.resume(9)
    assert s.phase is Phase.INTERVIEWER_THINKING
    assert s.turns == []


def test_terminal_sessions_reject_changes() -> None:
    s = in_phase(Phase.AWAITING_CANDIDATE)
    s.end(EndReason.USER_ENDED, 10)
    for op in (
        lambda: s.end(EndReason.USER_ENDED, 11),
        lambda: s.pause(11),
        lambda: s.fail("x", 11),
    ):
        with pytest.raises(InvalidTransitionError):
            op()


def test_answers_are_recorded_with_sequence_numbers() -> None:
    s = in_phase(Phase.FINALIZING_TRANSCRIPT)
    s.record_answer("  Ho lavorato con FastAPI.  ", 50)
    assert [t.seq for t in s.turns] == [0, 1]
    assert s.turns[-1].text == "Ho lavorato con FastAPI."  # type: ignore[union-attr]


def test_config_validation() -> None:
    with pytest.raises(InvalidConfigError):
        replace(make_config(), target_duration_s=60)
    with pytest.raises(InvalidConfigError):
        replace(make_config(), custom_instructions="x" * 1001)
    assert isinstance(make_config(), InterviewConfig)


def test_context_validation() -> None:
    with pytest.raises(InvalidConfigError):
        InterviewContext("c", "j", ())
    with pytest.raises(InvalidConfigError):
        InterviewContext("c", "j", (Topic("t1", "a"), Topic("t1", "b")))
    assert make_context().has_topic("t2")
