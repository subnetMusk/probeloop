from __future__ import annotations

import json
from pathlib import Path

from probeloop.interview.domain.model import (
    EndReason,
    InterviewerMove,
    InterviewSession,
    MoveAction,
)
from tests.conftest import make_session


def synthetic_session() -> InterviewSession:
    rows = json.loads(
        (Path(__file__).parents[1] / "fixtures/synthetic/assessment/interview.json").read_text()
    )
    session = make_session()
    session.start(0)
    for index, row in enumerate(rows):
        now = index * 60.0
        session.record_move(InterviewerMove(MoveAction(row["action"]), "t1", row["question"]), now)
        session.finish_speaking(now + 5)
        session.start_answer(now + 7)
        session.finish_answer(now + 30)
        session.record_answer(row["answer"], now + 31)
    session.end(EndReason.USER_ENDED, 300)
    return session
