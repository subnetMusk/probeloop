from __future__ import annotations

import asyncio
from contextlib import suppress

from probeloop.ai.fake import FakeChatModel
from probeloop.ai.ports import ChatMessage, ChatRequest
from probeloop.ai.scheduled import ScheduledChatModel
from probeloop.platform.model_access import BackgroundModelAccess


async def test_background_calls_wait_for_a_live_interview_and_serialize() -> None:
    active = True
    idle = asyncio.Event()

    async def wait() -> None:
        await idle.wait()

    access = BackgroundModelAccess(wait, lambda: active)
    raw = FakeChatModel(["response"], chunk_delay_s=0.01)
    model = ScheduledChatModel(raw, access.acquire)
    request = ChatRequest("rules", (ChatMessage("user", "input"),))
    pending = asyncio.create_task(model.complete(request))
    await asyncio.sleep(0.02)
    assert raw.requests == []
    active = False
    idle.set()
    await asyncio.sleep(0.005)
    assert access.busy
    assert (await pending).text == "response"
    assert not access.busy


async def test_cancelled_background_work_releases_model_access() -> None:
    async def idle() -> None:
        pass

    access = BackgroundModelAccess(idle, lambda: False)
    entered = asyncio.Event()

    async def work() -> None:
        async with access.acquire():
            entered.set()
            await asyncio.Event().wait()

    pending = asyncio.create_task(work())
    await entered.wait()
    assert access.busy
    pending.cancel()
    with suppress(asyncio.CancelledError):
        await pending
    assert not access.busy
    async with access.acquire():
        assert access.busy
