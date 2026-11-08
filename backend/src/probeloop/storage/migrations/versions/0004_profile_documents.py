"""A profile also holds a CV and a job offer.

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("profiles") as batch:
        batch.add_column(sa.Column("cv_document_id", sa.String(32), nullable=True))
        batch.add_column(sa.Column("job_offer_document_id", sa.String(32), nullable=True))
        batch.create_foreign_key("fk_profiles_cv_document", "documents", ["cv_document_id"], ["id"])
        batch.create_foreign_key(
            "fk_profiles_job_offer_document", "documents", ["job_offer_document_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("profiles") as batch:
        batch.drop_constraint("fk_profiles_job_offer_document", type_="foreignkey")
        batch.drop_constraint("fk_profiles_cv_document", type_="foreignkey")
        batch.drop_column("job_offer_document_id")
        batch.drop_column("cv_document_id")
