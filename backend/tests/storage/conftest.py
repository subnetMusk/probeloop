"""Database fixtures. Store tests run on SQLite, and on PostgreSQL when
`PROBELOOP_TEST_DATABASE_URL` points to an empty database (CI does this)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from probeloop.interview.domain.model import (
    InterviewerMove,
    InterviewSession,
    MoveAction,
    MoveStatus,
)
from probeloop.storage.database import create_engine, downgrade, migrate, sessionmaker
from probeloop.storage.session_files import SessionFiles
from probeloop.storage.sql_sessions import SqlSessionStore
from tests.conftest import make_session

POSTGRES_URL = os.environ.get("PROBELOOP_TEST_DATABASE_URL")
SESSION_ID = "a" * 32

DATABASES = [
    "sqlite",
    pytest.param(
        "postgresql",
        marks=pytest.mark.skipif(POSTGRES_URL is None, reason="no PostgreSQL configured"),
    ),
]


def database_url(kind: str, tmp_path: Path) -> str:
    if kind == "sqlite":
        return f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    assert POSTGRES_URL is not None
    return POSTGRES_URL


@pytest.fixture(params=DATABASES)
async def engine(request: pytest.FixtureRequest, tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(database_url(request.param, tmp_path))
    await downgrade(engine, "base")  # PostgreSQL is shared between tests: start empty
    await migrate(engine)
    yield engine
    await engine.dispose()


@pytest.fixture
def store(engine: AsyncEngine, tmp_path: Path) -> SqlSessionStore:
    return SqlSessionStore(sessionmaker(engine), SessionFiles(tmp_path / "sessions"))


def played_session(session_id: str = SESSION_ID) -> InterviewSession:
    s = make_session(session_id=session_id)
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
    s.record_answer("Un servizio di routing.", 15, engine_ref="stt-worker/live")
    s.pause(
        16,
        partial_move=InterviewerMove(
            MoveAction.FOLLOW_UP, "t2", "x", status=MoveStatus.INTERRUPTED
        ),
    )
    return s
