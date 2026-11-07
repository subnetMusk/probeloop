"""Sessions, turns, transcript revisions, turn metrics and jobs.

Revision ID: 0001
Revises:
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_sessions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("phase", sa.String(32), nullable=True),
        sa.Column("interview_type", sa.String(16), nullable=False),
        sa.Column("difficulty", sa.String(16), nullable=False),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("modality", sa.String(8), nullable=False),
        sa.Column("target_duration_s", sa.Integer(), nullable=False),
        sa.Column("custom_instructions", sa.Text(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("coverage", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.Float(), nullable=True),
        sa.Column("ended_at", sa.Float(), nullable=True),
        sa.Column("end_reason", sa.String(16), nullable=True),
        sa.Column("failure", sa.Text(), nullable=True),
        sa.Column("paused_at", sa.Float(), nullable=True),
        sa.Column("paused_total_s", sa.Float(), nullable=False),
        sa.Column("paused_phase", sa.String(32), nullable=True),
        sa.Column("final_question_asked", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "turns",
        sa.Column(
            "session_id",
            sa.String(32),
            sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("seq", sa.Integer(), primary_key=True),
        sa.Column("speaker", sa.String(16), nullable=False),
        sa.Column("at", sa.Float(), nullable=False),
        sa.Column("elapsed_s", sa.Float(), nullable=False),
        sa.Column("move", sa.JSON(), nullable=True),
    )
    op.create_table(
        "transcript_revisions",
        sa.Column("session_id", sa.String(32), primary_key=True),
        sa.Column("turn_seq", sa.Integer(), primary_key=True),
        sa.Column("number", sa.Integer(), primary_key=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("engine_ref", sa.String(200), nullable=True),
        sa.Column("words", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id", "turn_seq"],
            ["turns.session_id", "turns.seq"],
            ondelete="CASCADE",
        ),
    )
    op.create_table(
        "turn_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.String(32),
            sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("record", sa.JSON(), nullable=False),
    )
    op.create_index("ix_turn_metrics_session_id", "turn_metrics", ["session_id"])
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("subject_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("started_at", sa.Float(), nullable=True),
        sa.Column("finished_at", sa.Float(), nullable=True),
    )
    op.create_index("ix_jobs_subject", "jobs", ["subject_id", "kind"])
    op.create_index("ix_jobs_status", "jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_subject", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("ix_turn_metrics_session_id", table_name="turn_metrics")
    op.drop_table("turn_metrics")
    op.drop_table("transcript_revisions")
    op.drop_table("turns")
    op.drop_table("interview_sessions")
