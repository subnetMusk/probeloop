"""Reports record the saved profile they belong to.

Interview reports take the profile of their interview. A CV report takes the profile of the
preparations that approved its context, when they name exactly one.

Revision ID: 0009
Revises: 0008
"""

from __future__ import annotations

from collections import defaultdict

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("reports") as batch:
        batch.add_column(sa.Column("profile_id", sa.String(32), nullable=True))
        batch.create_index("ix_reports_profile_id", ["profile_id"])
    connection = op.get_bind()
    sessions: dict[str, str] = dict(
        connection.execute(
            sa.text("SELECT id, profile_id FROM interview_sessions WHERE profile_id IS NOT NULL")
        ).all()
    )
    approved: defaultdict[str, set[str]] = defaultdict(set)
    for snapshot_id, profile_id in connection.execute(
        sa.text(
            "SELECT snapshot_id, profile_id FROM preparations"
            " WHERE snapshot_id IS NOT NULL AND profile_id IS NOT NULL"
        )
    ).all():
        approved[snapshot_id].add(profile_id)
    owners: dict[str, str] = {}
    for report_id, kind, session_id, snapshot_id in connection.execute(
        sa.text("SELECT id, kind, session_id, snapshot_id FROM reports")
    ).all():
        if kind == "interview" and session_id in sessions:
            owners[report_id] = sessions[session_id]
        elif kind == "cv" and len(approved.get(snapshot_id, ())) == 1:
            (owners[report_id],) = approved[snapshot_id]
    for report_id, profile_id in owners.items():
        connection.execute(
            sa.text("UPDATE reports SET profile_id = :profile WHERE id = :id"),
            {"profile": profile_id, "id": report_id},
        )


def downgrade() -> None:
    with op.batch_alter_table("reports") as batch:
        batch.drop_index("ix_reports_profile_id")
        batch.drop_column("profile_id")
