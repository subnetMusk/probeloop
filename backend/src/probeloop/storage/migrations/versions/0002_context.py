"""Documents, profiles of resources, context preparations and snapshots.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "context_extractions",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column("filename", sa.String(255), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=False),
    )
    op.create_index("ix_documents_sha256", "documents", ["sha256"])
    op.create_table(
        "profiles",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.Float(), nullable=False),
    )
    op.create_table(
        "profile_resources",
        sa.Column(
            "profile_id",
            sa.String(32),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("position", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.String(32), sa.ForeignKey("documents.id"), nullable=False),
    )
    op.create_table(
        "preparations",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("job_mode", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("document_ids", sa.JSON(), nullable=False),
        sa.Column("facts", sa.JSON(), nullable=False),
        sa.Column("matches", sa.JSON(), nullable=False),
        sa.Column("area", sa.JSON(), nullable=True),
        sa.Column("vocabulary", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("profile_id", sa.String(32), nullable=True),
        sa.Column("snapshot_id", sa.String(32), nullable=True),
    )
    op.create_table(
        "context_snapshots",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("preparation_id", sa.String(32), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    with op.batch_alter_table("interview_sessions") as batch:
        batch.add_column(sa.Column("snapshot_id", sa.String(32), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("interview_sessions") as batch:
        batch.drop_column("snapshot_id")
    op.drop_table("context_snapshots")
    op.drop_table("preparations")
    op.drop_table("profile_resources")
    op.drop_table("profiles")
    op.drop_index("ix_documents_sha256", table_name="documents")
    op.drop_table("documents")
    op.drop_table("context_extractions")
