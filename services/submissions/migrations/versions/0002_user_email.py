"""add user_email, denormalized from the JWT at upload time

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-10

Nullable: rows created before this migration have no email. Indexed so the
admin can search by submitter.
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("submission", sa.Column("user_email", sa.String(length=320), nullable=True))
    op.create_index(op.f("ix_submission_user_email"), "submission", ["user_email"])


def downgrade() -> None:
    op.drop_index(op.f("ix_submission_user_email"), table_name="submission")
    op.drop_column("submission", "user_email")
