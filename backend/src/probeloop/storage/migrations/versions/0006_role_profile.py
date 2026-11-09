"""Retain the confirmed target role independently of interview difficulty.

Revision ID: 0006
Revises: 0005
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("preparations") as batch:
        batch.add_column(sa.Column("role_profile", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("preparations") as batch:
        batch.drop_column("role_profile")
