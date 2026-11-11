"""Freeze per-role tool choices with preparations and interviews.

Revision ID: 0007
Revises: 0006
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("interview_sessions", "preparations"):
        with op.batch_alter_table(table) as batch:
            batch.alter_column("execution_profile", existing_type=sa.String(16), type_=sa.Text())


def downgrade() -> None:
    for name in ("interview_sessions", "preparations"):
        table = sa.table(name, sa.column("execution_profile", sa.Text()))
        mixed = op.get_bind().scalar(
            sa.select(sa.func.count())
            .select_from(table)
            .where(table.c.execution_profile.not_in(("local", "cloud")))
        )
        if mixed:
            raise RuntimeError("cannot downgrade while per-role execution plans are stored")
    for name in ("interview_sessions", "preparations"):
        with op.batch_alter_table(name) as batch:
            batch.alter_column("execution_profile", existing_type=sa.Text(), type_=sa.String(16))
