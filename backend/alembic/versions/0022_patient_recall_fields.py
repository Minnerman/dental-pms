"""add patient recall tracking fields

Revision ID: 0022_patient_recall_fields
Revises: 0021_practice_profile
Create Date: 2026-01-11 14:34:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0022_patient_recall_fields"
down_revision = "0021_practice_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("recall_type", sa.String(length=40), nullable=True))
    op.add_column(
        "patients",
        sa.Column("recall_last_contacted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("patients", sa.Column("recall_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("patients", "recall_notes")
    op.drop_column("patients", "recall_last_contacted_at")
    op.drop_column("patients", "recall_type")
