"""add patient referral fields

Revision ID: 0016_patient_referral_fields
Revises: 0015_clinical_chart
Create Date: 2026-01-11 12:20:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0016_patient_referral_fields"
down_revision = "0015_clinical_chart"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("referral_source", sa.String(length=120), nullable=True))
    op.add_column(
        "patients", sa.Column("referral_contact_name", sa.String(length=120), nullable=True)
    )
    op.add_column(
        "patients", sa.Column("referral_contact_phone", sa.String(length=50), nullable=True)
    )
    op.add_column("patients", sa.Column("referral_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("patients", "referral_notes")
    op.drop_column("patients", "referral_contact_phone")
    op.drop_column("patients", "referral_contact_name")
    op.drop_column("patients", "referral_source")
