from __future__ import annotations

import asyncio

import pytest

from probeloop.ai.ports import LlmError
from probeloop.interview.application.events import (
    AnswerRecorded,
    ErrorRaised,
    MoveCompleted,
    Preparing,
    SessionEnded,
    StateChanged,
    UtteranceDelta,
)
from probeloop.interview.application.orchestrator import SessionOrchestrator
from probeloop.interview.application.phrases import FALLBACK, FAREWELL
from probeloop.interview.application.ports import MoveRequest
from probeloop.interview.domain.model import (
    EndReason,
    InterviewerMove,
    InterviewerTurn,
    InvalidTransitionError,
    Language,
    MoveAction,
    MoveStatus,
    Phase,
    SessionStatus,
)
from probeloop.interview.domain.time_policy import TimeDirective
from tests.conftest import (
    EventRecorder,
    FakeClock,
    MemoryStore,
    ScriptedInterviewer,
    failing,
    make_session,
)


def orchestrator(
    clock: FakeClock,
    store: MemoryStore,
    recorder: EventRecorder,
    interviewer: ScriptedInterviewer | None = None,
    minutes: int = 15,
) -> tuple[SessionOrchestrator, ScriptedInterviewer]:
    interviewer = interviewer or ScriptedInterviewer()
    o = SessionOrchestrator(
        make_session(minutes), interviewer=interviewer, store=store, clock=clock, sink=recorder
    )
    return o, interviewer


async def answer(o: SessionOrchestrator, clock: FakeClock, text: str, seconds: float) -> None:
    await o.playback_finished()
    await o.start_answer()
    clock.advance(seconds)
    await o.end_answer(text)
    await o.wait_for_move()


async def test_full_interview_ends_between_100_and_115_percent(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    o, interviewer = orchestrator(clock, store, recorder)
    await o.start()
    await o.wait_for_move()
    for _ in range(40):
        if o.session.is_terminal or o.session.last_move().action is MoveAction.END:  # type: ignore[union-attr]
            break
        await answer(o, clock, "Risposta di prova.", 100)
    await o.playback_finished()

    session = o.session
    ratio = session.elapsed_s(clock.now()) / session.config.target_duration_s
    assert session.status is SessionStatus.ENDED
    assert session.end_reason is EndReason.COMPLETED
    assert 1.0 <= ratio <= 1.15
    directives = [r.directive for r in interviewer.requests]
    assert TimeDirective.BEGIN_WRAP_UP in directives
    assert directives[-2:] == [TimeDirective.FINAL_QUESTION, TimeDirective.CLOSE]
    assert session.last_move().action is MoveAction.END  # type: ignore[union-attr]
    assert isinstance(recorder.events[-1], SessionEnded)
    assert store.sessions[session.id] is session


async def test_forced_close_uses_the_template_without_the_llm(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    o, interviewer = orchestrator(clock, store, recorder)
    await o.start()
    await o.wait_for_move()
    calls_before = len(interviewer.requests)
    await answer(o, clock, "Una risposta lunghissima.", 15 * 60 * 1.2)

    move = o.session.last_move()
    assert move is not None
    assert move.action is MoveAction.END
    assert move.utterance == FAREWELL[Language.ITALIAN]
    assert len(interviewer.requests) == calls_before
    await o.playback_finished()
    assert o.session.status is SessionStatus.ENDED


async def test_close_directive_forces_the_end_action(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    def never_ends(request):  # type: ignore[no-untyped-def]
        return InterviewerMove(MoveAction.FOLLOW_UP, "t1", "Un'altra domanda?")

    o, _ = orchestrator(clock, store, recorder, ScriptedInterviewer(never_ends))
    o.session.final_question_asked = True
    await o.start()
    await o.wait_for_move()
    assert o.session.last_move().action is MoveAction.END  # type: ignore[union-attr]


async def test_events_describe_the_move_and_the_answer(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    o, _ = orchestrator(clock, store, recorder)
    await o.start()
    await o.wait_for_move()
    await answer(o, clock, "  Ciao  ", 10)

    deltas = "".join(e.text for e in recorder.of(UtteranceDelta) if e.turn_seq == 0)
    completed = recorder.of(MoveCompleted)
    assert deltas == completed[0].utterance == "Domanda numero 1?"
    assert recorder.of(AnswerRecorded)[0].text == "Ciao"
    phases = [e.phase for e in recorder.of(StateChanged)]
    assert phases[:4] == [
        Phase.INTERVIEWER_THINKING,
        Phase.INTERVIEWER_SPEAKING,
        Phase.AWAITING_CANDIDATE,
        Phase.CANDIDATE_SPEAKING,
    ]


async def test_llm_failure_is_retried_once(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    o, interviewer = orchestrator(clock, store, recorder, ScriptedInterviewer(failing(1)))
    await o.start()
    await o.wait_for_move()
    move = o.session.last_move()
    assert move is not None
    assert not move.fallback
    assert len(interviewer.requests) == 2
    assert recorder.of(ErrorRaised) == []


async def test_repeated_llm_failure_falls_back_to_a_fixed_phrase(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    o, _ = orchestrator(clock, store, recorder, ScriptedInterviewer(failing(5)))
    await o.start()
    await o.wait_for_move()
    move = o.session.last_move()
    assert move is not None
    assert move.fallback
    assert move.utterance == FALLBACK[Language.ITALIAN]
    assert o.session.phase is Phase.INTERVIEWER_SPEAKING
    assert recorder.of(ErrorRaised)[0].code == "llm_unavailable"


async def test_pause_during_generation_keeps_the_spoken_part(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    slow = ScriptedInterviewer(chunk_size=3, chunk_delay_s=0.01)
    first_delta = asyncio.Event()

    async def sink(event: object) -> None:
        await recorder(event)  # type: ignore[arg-type]
        if isinstance(event, UtteranceDelta):
            first_delta.set()

    o = SessionOrchestrator(make_session(), interviewer=slow, store=store, clock=clock, sink=sink)
    await o.start()
    await asyncio.wait_for(first_delta.wait(), timeout=2)
    await o.pause()

    assert o.session.status is SessionStatus.PAUSED
    turn = o.session.turns[-1]
    assert isinstance(turn, InterviewerTurn)
    assert turn.move.status is MoveStatus.INTERRUPTED
    assert "Domanda numero 1?".startswith(turn.move.utterance)
    await o.resume()
    assert o.session.phase is Phase.AWAITING_CANDIDATE


async def test_pause_before_any_text_regenerates_the_move(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    slow = ScriptedInterviewer(chunk_delay_s=0.2)
    o, interviewer = orchestrator(clock, store, recorder, slow)
    await o.start()
    await asyncio.sleep(0.01)
    await o.pause()
    assert o.session.turns == []
    slow.chunk_delay_s = 0
    await o.resume()
    await o.wait_for_move()
    assert len(interviewer.requests) == 2
    assert o.session.last_move().status is MoveStatus.COMPLETED  # type: ignore[union-attr]


async def test_end_cancels_the_running_move(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    slow = ScriptedInterviewer(chunk_delay_s=0.2)
    o, _ = orchestrator(clock, store, recorder, slow)
    await o.start()
    await asyncio.sleep(0.01)
    await o.end()
    assert o.session.status is SessionStatus.ENDED
    assert o.session.end_reason is EndReason.USER_ENDED
    assert o.session.turns == []
    assert isinstance(recorder.events[-1], SessionEnded)


async def test_start_loads_the_model_before_the_first_question(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    o, interviewer = orchestrator(clock, store, recorder)
    await o.start()
    with pytest.raises(InvalidTransitionError, match="already starting"):
        await o.start()
    await o.wait_for_move()
    assert interviewer.prepared == 1
    progress = recorder.of(Preparing)
    assert [[(s.name, s.state) for s in p.steps] for p in progress] == [
        [("language_model", "loading")],
        [("language_model", "ready")],
    ]
    assert progress[-1].progress == 1.0
    kinds = [type(e) for e in recorder.events]
    assert kinds.index(Preparing) < kinds.index(MoveCompleted)
    assert o.session.status is SessionStatus.IN_PROGRESS


async def test_a_model_that_cannot_load_keeps_the_session_ready(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    interviewer = ScriptedInterviewer(prepare_errors=[LlmError("connection refused")])
    o, _ = orchestrator(clock, store, recorder, interviewer)
    await o.start()
    await o.wait_for_move()
    assert o.session.status is SessionStatus.READY
    (error,) = recorder.of(ErrorRaised)
    assert error.code == "preparation_failed"
    assert "language model" in error.message
    assert recorder.of(Preparing)[-1].steps[0].state == "failed"
    assert interviewer.requests == []

    await o.start()  # the client tries again, and this time the model loads
    await o.wait_for_move()
    assert o.session.status is SessionStatus.IN_PROGRESS
    assert interviewer.prepared == 2


async def test_cancelling_the_start_leaves_the_session_ready(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    gate = asyncio.Event()

    class SlowModel(ScriptedInterviewer):
        async def prepare(self, request: MoveRequest) -> None:
            await gate.wait()

    o, _ = orchestrator(clock, store, recorder, SlowModel())
    await o.start()
    await asyncio.sleep(0)
    await o.cancel_start()
    gate.set()
    await o.wait_for_move()
    assert o.session.status is SessionStatus.READY
    assert recorder.of(MoveCompleted) == []


async def test_broken_event_sink_does_not_break_the_session(
    clock: FakeClock, store: MemoryStore
) -> None:
    async def broken(event: object) -> None:
        raise ConnectionError("client gone")

    o = SessionOrchestrator(
        make_session(), interviewer=ScriptedInterviewer(), store=store, clock=clock, sink=broken
    )
    await o.start()
    await o.wait_for_move()
    assert o.session.phase is Phase.INTERVIEWER_SPEAKING
