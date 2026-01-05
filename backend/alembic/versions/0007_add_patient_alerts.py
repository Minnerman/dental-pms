"""add patient alerts

Revision ID: 0007_add_patient_alerts
Revises: 0006_add_domiciliary_fields
Create Date: 2026-01-05 23:38:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_add_patient_alerts"
down_revision = "0006_add_domiciliary_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("allergies", sa.Text(), nullable=True))
    op.add_column("patients", sa.Column("medical_alerts", sa.Text(), nullable=True))
    op.add_column("patients", sa.Column("safeguarding_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("patients", "safeguarding_notes")
    op.drop_column("patients", "medical_alerts")
    op.drop_column("patients", "allergies")
