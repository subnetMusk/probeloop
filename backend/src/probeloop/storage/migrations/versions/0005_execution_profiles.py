"""Interviews and preparations record their execution profile (ADR 0015).

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("interview_sessions") as batch:
        batch.add_column(sa.Column("execution_profile", sa.String(16), nullable=True))
        batch.add_column(sa.Column("profile_id", sa.String(32), nullable=True))
    with op.batch_alter_table("preparations") as batch:
        batch.add_column(sa.Column("execution_profile", sa.String(16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("preparations") as batch:
        batch.drop_column("execution_profile")
    with op.batch_alter_table("interview_sessions") as batch:
        batch.drop_column("profile_id")
        batch.drop_column("execution_profile")
