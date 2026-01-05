"""add appointment fields

Revision ID: 0005_add_appointment_fields
Revises: 0004_add_receptionist_role
Create Date: 2026-01-05 23:20:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_add_appointment_fields"
down_revision = "0004_add_receptionist_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "appointments",
        sa.Column("clinician_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "appointments",
        sa.Column("appointment_type", sa.String(length=120), nullable=True),
    )
    op.create_foreign_key(
        "appointments_clinician_user_id_fkey",
        "appointments",
        "users",
        ["clinician_user_id"],
        ["id"],
    )
    op.create_index(
        "ix_appointments_starts_at",
        "appointments",
        ["starts_at"],
    )
    op.create_index(
        "ix_appointments_patient_id",
        "appointments",
        ["patient_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_appointments_patient_id", table_name="appointments")
    op.drop_index("ix_appointments_starts_at", table_name="appointments")
    op.drop_constraint(
        "appointments_clinician_user_id_fkey", "appointments", type_="foreignkey"
    )
    op.drop_column("appointments", "appointment_type")
    op.drop_column("appointments", "clinician_user_id")
