"""Coordinate data operations with mutations, background jobs and live connections."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Protocol

from probeloop.ids import new_id


class DataStore(Protocol):
    async def summary(self) -> dict[str, int]: ...
    async def export_json(self) -> bytes: ...
    async def backup(self) -> Path: ...
    async def delete_all(self) -> None: ...
    async def restore(self, archive: Path) -> None: ...


BusyReason = Literal["interview", "background_job"]


class DataBusyError(RuntimeError):
    def __init__(self, reason: BusyReason) -> None:
        self.reason = reason
        super().__init__(
            "close the live interview first"
            if reason == "interview"
            else "wait for background jobs to finish first"
        )


class DataService:
    def __init__(
        self,
        store: DataStore,
        *,
        connected: Callable[[], bool],
        pending: Callable[[], Awaitable[bool]],
        clear_live: Callable[[], Awaitable[None]],
    ) -> None:
        self.store = store
        self._connected = connected
        self._pending = pending
        self._clear_live = clear_live
        self.write_lock = asyncio.Lock()
        self.busy = False
        self._downloads: dict[str, Path] = {}

    async def ensure_idle(self) -> None:
        """Raise unless no live interview is connected and no job is queued or running.

        Callers hold `write_lock`, as the API does for every mutating request, so that no new
        work starts between the check and their change.
        """
        if self._connected():
            raise DataBusyError("interview")
        if await self._pending():
            raise DataBusyError("background_job")

    @asynccontextmanager
    async def operation(self) -> AsyncIterator[None]:
        async with self.write_lock:
            await self.ensure_idle()
            self.busy = True
            try:
                yield
            finally:
                self.busy = False

    async def export_json(self) -> bytes:
        async with self.operation():
            return await self.store.export_json()

    async def prepare_backup(self) -> str:
        async with self.operation():
            path = await self.store.backup()
            token = new_id()
            self._downloads[token] = path
            return token

    def take_backup(self, token: str) -> Path:
        return self._downloads.pop(token)

    async def delete_all(self) -> None:
        async with self.operation():
            await self.store.delete_all()
            self._downloads.clear()
            await self._clear_live()

    async def restore(self, archive: Path) -> None:
        async with self.operation():
            await self.store.restore(archive)

    async def close(self) -> None:
        for path in self._downloads.values():
            await asyncio.to_thread(path.unlink, missing_ok=True)
        self._downloads.clear()
