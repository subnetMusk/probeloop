"""Serialize non-live model work and reserve the model while an interview is active."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager


class BackgroundModelAccess:
    def __init__(self, idle: Callable[[], Awaitable[None]], active: Callable[[], bool]) -> None:
        self._idle = idle
        self._active = active
        self._lock = asyncio.Lock()
        self.busy = False

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[None]:
        while True:
            await self._idle()
            await self._lock.acquire()
            if not self._active():
                break
            self._lock.release()
        self.busy = True
        try:
            yield
        finally:
            self.busy = False
            self._lock.release()
