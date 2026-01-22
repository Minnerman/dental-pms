"""Add role field to R4 users

Revision ID: 0039_r4_users_role
Revises: 0038_r4_users
Create Date: 2026-01-22 19:35:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0039_r4_users_role"
down_revision = "0038_r4_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("r4_users", sa.Column("role", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("r4_users", "role")
