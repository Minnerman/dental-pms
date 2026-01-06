"""domiciliary patient fields and appointment workflow

Revision ID: 0010_domiciliary_patient_fields
Revises: 0009_billing_foundations_v1
Create Date: 2026-01-06 21:40:00.000000
"""

from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "0010_domiciliary_patient_fields"
down_revision = "0009_billing_foundations_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    care_setting = sa.Enum(
        "clinic",
        "home",
        "care_home",
        "hospital",
        name="care_setting",
    )
    location_type = sa.Enum("clinic", "visit", name="appointment_location_type")

    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    def has_column(table: str, column: str) -> bool:
        return any(col["name"] == column for col in inspector.get_columns(table))

    care_setting.create(bind, checkfirst=True)
    location_type.create(bind, checkfirst=True)

    if "patients" in tables:
        if not has_column("patients", "care_setting"):
            op.add_column(
                "patients",
                sa.Column(
                    "care_setting",
                    care_setting,
                    nullable=False,
                    server_default="clinic",
                ),
            )
        if not has_column("patients", "visit_address_text"):
            op.add_column("patients", sa.Column("visit_address_text", sa.Text(), nullable=True))
        if not has_column("patients", "access_notes"):
            op.add_column("patients", sa.Column("access_notes", sa.Text(), nullable=True))
        if not has_column("patients", "primary_contact_name"):
            op.add_column(
                "patients", sa.Column("primary_contact_name", sa.String(length=120), nullable=True)
            )
        if not has_column("patients", "primary_contact_phone"):
            op.add_column(
                "patients", sa.Column("primary_contact_phone", sa.String(length=50), nullable=True)
            )
        if not has_column("patients", "primary_contact_relationship"):
            op.add_column(
                "patients",
                sa.Column("primary_contact_relationship", sa.String(length=80), nullable=True),
            )

    if "appointments" in tables:
        op.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_enum
                    WHERE enumlabel = 'arrived'
                    AND enumtypid = 'appointment_status'::regtype
                ) THEN
                    ALTER TYPE appointment_status ADD VALUE 'arrived';
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM pg_enum
                    WHERE enumlabel = 'in_progress'
                    AND enumtypid = 'appointment_status'::regtype
                ) THEN
                    ALTER TYPE appointment_status ADD VALUE 'in_progress';
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM pg_enum
                    WHERE enumlabel = 'no_show'
                    AND enumtypid = 'appointment_status'::regtype
                ) THEN
                    ALTER TYPE appointment_status ADD VALUE 'no_show';
                END IF;
            END$$;
            """
        )
        if not has_column("appointments", "location_type"):
            op.add_column(
                "appointments",
                sa.Column(
                    "location_type",
                    location_type,
                    nullable=False,
                    server_default="clinic",
                ),
            )
        if not has_column("appointments", "location_text"):
            op.add_column("appointments", sa.Column("location_text", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    def has_column(table: str, column: str) -> bool:
        return any(col["name"] == column for col in inspector.get_columns(table))

    if "appointments" in tables:
        if has_column("appointments", "location_text"):
            op.drop_column("appointments", "location_text")
        if has_column("appointments", "location_type"):
            op.drop_column("appointments", "location_type")

    if "patients" in tables:
        for column in (
            "primary_contact_relationship",
            "primary_contact_phone",
            "primary_contact_name",
            "access_notes",
            "visit_address_text",
            "care_setting",
        ):
            if has_column("patients", column):
                op.drop_column("patients", column)

    op.execute("DROP TYPE IF EXISTS appointment_location_type")
    op.execute("DROP TYPE IF EXISTS care_setting")
