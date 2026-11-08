from __future__ import annotations

import asyncio

import pytest

from probeloop.interview.application.service import SessionService
from probeloop.interview.domain.model import InvalidTransitionError
from tests.conftest import FakeClock, MemoryStore, ScriptedInterviewer, make_session


async def test_start_waits_for_background_work_and_reserves_the_interview() -> None:
    store = MemoryStore()
    sample = make_session()
    await store.save(sample)
    busy = True
    sessions = SessionService(
        store=store,
        interviewer=ScriptedInterviewer(),
        clock=FakeClock(),
        background_busy=lambda: busy,
    )

    async def listen(seq: int | None, event: object) -> None:
        pass

    await sessions.connect(sample.id, listen)
    with pytest.raises(InvalidTransitionError, match="background processing"):
        await sessions.start(sample.id)
    busy = False
    await sessions.start(sample.id)
    assert sessions.any_active()
    await asyncio.sleep(0.02)
    assert sessions.any_active()
    await sessions.shutdown()
