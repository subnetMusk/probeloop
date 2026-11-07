from __future__ import annotations

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from probeloop.storage.database import Base, downgrade, migrate


async def test_the_migrated_schema_matches_the_models(engine: AsyncEngine) -> None:
    def diff(connection: Connection) -> list[object]:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        return list(compare_metadata(context, Base.metadata))

    async with engine.connect() as connection:
        assert await connection.run_sync(diff) == []


async def test_migrations_go_down_and_up_again(engine: AsyncEngine) -> None:
    def tables(connection: Connection) -> set[str]:
        return set(inspect(connection).get_table_names()) - {"alembic_version"}

    await downgrade(engine, "base")
    async with engine.connect() as connection:
        assert await connection.run_sync(tables) == set()
    await migrate(engine)
    async with engine.connect() as connection:
        assert await connection.run_sync(tables) == set(Base.metadata.tables)
