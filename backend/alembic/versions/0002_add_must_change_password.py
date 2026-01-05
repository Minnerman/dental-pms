"""add must_change_password flag

Revision ID: 0002_add_must_change_password
Revises: 0001_initial
Create Date: 2026-01-04 15:56:30.000000
"""

from alembic import op


revision = "0002_add_must_change_password"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users "
        "ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS must_change_password")
