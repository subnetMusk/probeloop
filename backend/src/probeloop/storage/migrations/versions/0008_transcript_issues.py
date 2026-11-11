"""Record why an answer's transcript needs review: lost live audio or a missing reading.

Revision ID: 0008
Revises: 0007
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("turns") as batch:
        batch.add_column(sa.Column("issues", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("turns") as batch:
        batch.drop_column("issues")
