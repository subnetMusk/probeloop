"""Data operations wait for live interviews and background jobs, with fakes."""

from __future__ import annotations

from pathlib import Path

import pytest

from probeloop.workspace.service import DataBusyError, DataService


class Store:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def summary(self) -> dict[str, int]:
        return {}

    async def export_json(self) -> bytes:
        self.calls.append("export")
        return b"{}"

    async def backup(self) -> Path:
        self.calls.append("backup")
        return Path("backup.zip")

    async def delete_all(self) -> None:
        self.calls.append("delete")

    async def restore(self, archive: Path) -> None:
        self.calls.append("restore")


def service(store: Store, *, connected: bool = False, pending: bool = False) -> DataService:
    async def jobs() -> bool:
        return pending

    async def clear() -> None:
        store.calls.append("clear")

    return DataService(store, connected=lambda: connected, pending=jobs, clear_live=clear)


@pytest.mark.parametrize(
    ("connected", "pending", "reason"),
    [(True, False, "interview"), (False, True, "background_job"), (True, True, "interview")],
)
async def test_operations_are_refused_while_the_app_is_busy(
    connected: bool, pending: bool, reason: str
) -> None:
    store = Store()
    data = service(store, connected=connected, pending=pending)
    for operation in (
        data.export_json,
        data.prepare_backup,
        data.delete_all,
        lambda: data.restore(Path("backup.zip")),
    ):
        with pytest.raises(DataBusyError) as refused:
            await operation()
        assert refused.value.reason == reason
    assert store.calls == []
    assert not data.busy


async def test_operations_run_when_idle_and_deleting_clears_live_state() -> None:
    store = Store()
    data = service(store)
    await data.export_json()
    token = await data.prepare_backup()
    assert data.take_backup(token) == Path("backup.zip")
    await data.delete_all()
    assert store.calls == ["export", "backup", "delete", "clear"]
