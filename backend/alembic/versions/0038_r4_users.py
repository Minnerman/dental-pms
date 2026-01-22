"""Add R4 users lookup table

Revision ID: 0038_r4_users
Revises: 0037_r4_treatment_transactions
Create Date: 2026-01-22 12:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0038_r4_users"
down_revision = "0037_r4_treatment_transactions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "r4_users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("legacy_source", sa.String(length=120), nullable=False, server_default="r4"),
        sa.Column("legacy_user_code", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("title", sa.String(length=80), nullable=True),
        sa.Column("forename", sa.String(length=120), nullable=True),
        sa.Column("surname", sa.String(length=120), nullable=True),
        sa.Column("initials", sa.String(length=40), nullable=True),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column(
            "is_current",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
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
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.UniqueConstraint(
            "legacy_source",
            "legacy_user_code",
            name="uq_r4_users_legacy_key",
        ),
    )


def downgrade() -> None:
    op.drop_table("r4_users")
