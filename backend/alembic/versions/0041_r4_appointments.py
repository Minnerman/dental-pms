"""Add R4 appointments table

Revision ID: 0041_r4_appointments
Revises: 0040_r4_treatment_transactions_cursor_index
Create Date: 2026-01-22 22:05:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0041_r4_appointments"
down_revision = "0040_r4_treatment_transactions_cursor_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "r4_appointments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("legacy_source", sa.String(length=120), nullable=False, server_default="r4"),
        sa.Column("legacy_appointment_id", sa.Integer(), nullable=False),
        sa.Column("patient_code", sa.Integer(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("clinician_code", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=120), nullable=True),
        sa.Column("cancelled", sa.Boolean(), nullable=True),
        sa.Column("clinic_code", sa.Integer(), nullable=True),
        sa.Column("treatment_code", sa.Integer(), nullable=True),
        sa.Column("appointment_type", sa.String(length=200), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("appt_flag", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.UniqueConstraint(
            "legacy_source",
            "legacy_appointment_id",
            name="uq_r4_appointments_legacy_key",
        ),
    )
    op.create_index(
        "ix_r4_appointments_patient_code_starts_at",
        "r4_appointments",
        ["patient_code", "starts_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_r4_appointments_patient_code_starts_at", table_name="r4_appointments")
    op.drop_table("r4_appointments")
