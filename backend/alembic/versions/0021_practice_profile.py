"""add practice profile settings

Revision ID: 0021_practice_profile
Revises: 0020_patient_docs_attach
Create Date: 2026-01-11 13:55:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0021_practice_profile"
down_revision = "0020_patient_docs_attach"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "practice_profile",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("address_line1", sa.String(length=200), nullable=True),
        sa.Column("address_line2", sa.String(length=200), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("postcode", sa.String(length=20), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("website", sa.String(length=120), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("practice_profile")
