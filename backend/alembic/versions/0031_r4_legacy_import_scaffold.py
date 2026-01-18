"""add legacy import scaffolding fields

Revision ID: 0031_r4_legacy_import_scaffold
Revises: 0030_capabilities_scaffold
Create Date: 2026-01-18 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0031_r4_legacy_import_scaffold"
down_revision = "0030_capabilities_scaffold"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("legacy_source", sa.String(length=120), nullable=True))
    op.add_column("patients", sa.Column("legacy_id", sa.String(length=255), nullable=True))
    op.create_unique_constraint(
        "uq_patients_legacy_source_legacy_id",
        "patients",
        ["legacy_source", "legacy_id"],
    )

    op.add_column(
        "appointments", sa.Column("legacy_source", sa.String(length=120), nullable=True)
    )
    op.add_column("appointments", sa.Column("legacy_id", sa.String(length=255), nullable=True))
    op.create_unique_constraint(
        "uq_appointments_legacy_source_legacy_id",
        "appointments",
        ["legacy_source", "legacy_id"],
    )
    op.alter_column(
        "appointments",
        "patient_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "appointments",
        "patient_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.drop_constraint(
        "uq_appointments_legacy_source_legacy_id",
        "appointments",
        type_="unique",
    )
    op.drop_column("appointments", "legacy_id")
    op.drop_column("appointments", "legacy_source")

    op.drop_constraint(
        "uq_patients_legacy_source_legacy_id",
        "patients",
        type_="unique",
    )
    op.drop_column("patients", "legacy_id")
    op.drop_column("patients", "legacy_source")
