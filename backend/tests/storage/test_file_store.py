from __future__ import annotations

from pathlib import Path

import pytest

from probeloop.interview.domain.model import (
    EndReason,
    InterviewerMove,
    MoveAction,
    MoveStatus,
    SessionStatus,
)
from probeloop.storage.file_store import FileSessionStore, from_dict, to_dict
from tests.conftest import make_session

SESSION_ID = "a" * 32


def played_session():  # type: ignore[no-untyped-def]
    s = make_session(session_id=SESSION_ID)
    s.start(10)
    s.record_move(
        InterviewerMove(
            MoveAction.NEW_TOPIC, "t2", "Progetto?", ("t1",), model_ref="m", prompt_ref="p@v1"
        ),
        11,
    )
    s.finish_speaking(12)
    s.start_answer(13)
    s.finish_answer(14)
    s.record_answer("Un servizio di routing.", 15)
    s.pause(
        16,
        partial_move=InterviewerMove(
            MoveAction.FOLLOW_UP, "t2", "x", status=MoveStatus.INTERRUPTED
        ),
    )
    return s


def test_mapping_round_trip() -> None:
    s = played_session()
    assert from_dict(to_dict(s)) == s


def test_unknown_schema_version_is_rejected() -> None:
    data = to_dict(played_session())
    data["schema_version"] = 99
    with pytest.raises(ValueError, match="schema version"):
        from_dict(data)


async def test_save_load_list_delete(tmp_path: Path) -> None:
    store = FileSessionStore(tmp_path)
    s = played_session()
    await store.save(s)
    s.end(EndReason.USER_ENDED, 20)
    await store.save(s)

    loaded = await store.load(SESSION_ID)
    assert loaded == s
    assert [x.status for x in await store.summaries()] == [SessionStatus.ENDED]
    assert not list((tmp_path / SESSION_ID).glob("*.tmp"))

    assert await store.delete(SESSION_ID)
    assert not (tmp_path / SESSION_ID).exists()
    assert await store.load(SESSION_ID) is None
    assert not await store.delete(SESSION_ID)


@pytest.mark.parametrize("bad_id", ["../etc", "A" * 32, "abc", "a" * 31 + "/"])
async def test_ids_cannot_escape_the_store(tmp_path: Path, bad_id: str) -> None:
    store = FileSessionStore(tmp_path / "sessions")
    assert await store.load(bad_id) is None
    assert not await store.delete(bad_id)
    with pytest.raises(ValueError, match="invalid session id"):
        store.session_dir(bad_id)
