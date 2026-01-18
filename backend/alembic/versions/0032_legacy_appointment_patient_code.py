"""add legacy patient code for appointments

Revision ID: 0032_legacy_appointment_patient_code
Revises: 0031_r4_legacy_import_scaffold
Create Date: 2026-01-18 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0032_legacy_appointment_patient_code"
down_revision = "0031_r4_legacy_import_scaffold"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "appointments",
        sa.Column("legacy_patient_code", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("appointments", "legacy_patient_code")
