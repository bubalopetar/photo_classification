"""initial submission table

Revision ID: 0001
Revises:
Create Date: 2026-07-10

Indexes are created on every column the admin panel filters or sorts by
(age, gender, place_of_living, country_of_origin, created_at) plus user_id for
the per-user listing — so those lookups stay index-backed as the table grows.
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "submission",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("place_of_living", sa.String(length=200), nullable=False),
        sa.Column("gender", sa.String(length=32), nullable=False),
        sa.Column("country_of_origin", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("photo_key", sa.String(length=512), nullable=False),
        sa.Column("photo_content_type", sa.String(length=100), nullable=False),
        sa.Column("classification", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_submission_user_id"), "submission", ["user_id"])
    op.create_index(op.f("ix_submission_age"), "submission", ["age"])
    op.create_index(op.f("ix_submission_gender"), "submission", ["gender"])
    op.create_index(
        op.f("ix_submission_place_of_living"), "submission", ["place_of_living"]
    )
    op.create_index(
        op.f("ix_submission_country_of_origin"), "submission", ["country_of_origin"]
    )
    op.create_index(op.f("ix_submission_created_at"), "submission", ["created_at"])


def downgrade() -> None:
    op.drop_table("submission")
