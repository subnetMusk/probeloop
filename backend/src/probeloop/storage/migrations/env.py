"""Alembic environment. Migrations run on a connection passed by `storage.database.migrate`."""

from __future__ import annotations

from alembic import context

from probeloop.storage.database import Base

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("run migrations through probeloop.storage.database.migrate")

context.configure(
    connection=connection,
    target_metadata=Base.metadata,
    render_as_batch=True,  # ALTER TABLE support on SQLite
    compare_type=True,
)
with context.begin_transaction():
    context.run_migrations()
