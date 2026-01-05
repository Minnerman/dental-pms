"""expand audit action length

Revision ID: 0003_expand_audit_action_len
Revises: 0002_add_must_change_password
Create Date: 2026-01-05 22:27:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_expand_audit_action_len"
down_revision = "0002_add_must_change_password"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "audit_logs",
        "action",
        existing_type=sa.String(length=20),
        type_=sa.String(length=64),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "audit_logs",
        "action",
        existing_type=sa.String(length=64),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
