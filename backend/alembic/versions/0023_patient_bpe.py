"""add patient bpe fields

Revision ID: 0023_patient_bpe
Revises: 0022_patient_recall_fields
Create Date: 2026-01-11 15:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0023_patient_bpe"
down_revision = "0022_patient_recall_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("bpe_scores", sa.String(length=40), nullable=True))
    op.add_column(
        "patients",
        sa.Column("bpe_recorded_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("patients", "bpe_recorded_at")
    op.drop_column("patients", "bpe_scores")
