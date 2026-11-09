from tests.conftest import make_session

from probeloop.interview.domain.model import EndReason, InterviewerMove, MoveAction


def test_topic_clock_excludes_pauses_generation_and_transcription_delays() -> None:
    session = make_session()
    session.start(0)
    session.record_move(InterviewerMove(MoveAction.NEW_TOPIC, "t1", "Reasoning?"), 20)
    session.finish_speaking(30)
    session.start_answer(40)
    session.finish_answer(50)
    session.record_answer("A synthetic answer.", 150)
    session.record_move(InterviewerMove(MoveAction.FOLLOW_UP, "t1", "Evidence?"), 250)
    session.finish_speaking(260)
    session.pause(270)
    session.resume(370)
    session.start_answer(380)
    session.finish_answer(390)
    session.record_answer("A further synthetic answer.", 500)
    session.end(EndReason.USER_ENDED, 600)
    assert session.topic_engagement_s == {"t1": 50}
    assert session.engagement_since is None
