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


async def test_upgrading_keeps_the_rows_of_tables_that_reference_rebuilt_ones(
    engine: AsyncEngine,
) -> None:
    # Migration 0004 rebuilds `profiles` on SQLite; its resources must survive.
    await downgrade(engine, "0003")
    async with engine.begin() as connection:
        await connection.exec_driver_sql(
            "INSERT INTO documents (id, kind, title, origin, text, media_type, filename, sha256,"
            " warnings, created_at) VALUES ('d1', 'resource', 'Note', 'typed', 'Testo', "
            "'text/plain', NULL, NULL, '[]', 0)"
        )
        await connection.exec_driver_sql(
            "INSERT INTO profiles (id, name, created_at, updated_at) VALUES ('p1', 'B', 0, 0)"
        )
        await connection.exec_driver_sql(
            "INSERT INTO profile_resources (profile_id, position, document_id)"
            " VALUES ('p1', 0, 'd1')"
        )
    await migrate(engine)
    async with engine.connect() as connection:
        count = await connection.exec_driver_sql("SELECT count(*) FROM profile_resources")
        assert count.scalar_one() == 1
