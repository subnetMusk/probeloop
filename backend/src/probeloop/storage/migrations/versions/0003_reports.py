"""Versioned CV and interview reports.

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("subject_id", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column(
            "session_id", sa.String(32), sa.ForeignKey("interview_sessions.id", ondelete="CASCADE")
        ),
        sa.Column("snapshot_id", sa.String(32), sa.ForeignKey("context_snapshots.id")),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_reports_subject_version", "reports", ["kind", "subject_id", "version"], unique=True
    )
    op.create_index("ix_reports_session_id", "reports", ["session_id"])


def downgrade() -> None:
    op.drop_table("reports")
