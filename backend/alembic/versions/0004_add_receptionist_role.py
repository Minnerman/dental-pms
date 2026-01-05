"""add receptionist role

Revision ID: 0004_add_receptionist_role
Revises: 0003_expand_audit_action_len
Create Date: 2026-01-05 22:56:00.000000
"""

from alembic import op

revision = "0004_add_receptionist_role"
down_revision = "0003_expand_audit_action_len"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE role_enum ADD VALUE IF NOT EXISTS 'receptionist'")


def downgrade() -> None:
    # Postgres enums cannot easily drop values; leave as-is.
    pass
