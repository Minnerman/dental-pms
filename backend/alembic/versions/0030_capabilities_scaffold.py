"""add capabilities scaffold

Revision ID: 0030_capabilities_scaffold
Revises: 0029_recall_comm_last_contact_index
Create Date: 2026-01-18 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0030_capabilities_scaffold"
down_revision = "0029_recall_comm_last_contact_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "capabilities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_capabilities_code", "capabilities", ["code"], unique=True)

    op.create_table(
        "user_capabilities",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column(
            "capability_id",
            sa.Integer(),
            sa.ForeignKey("capabilities.id"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("user_capabilities")
    op.drop_index("ix_capabilities_code", table_name="capabilities")
    op.drop_table("capabilities")
