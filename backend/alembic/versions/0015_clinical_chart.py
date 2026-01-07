"""add clinical chart tables

Revision ID: 0015_clinical_chart
Revises: 0014_patient_ledger_entries
Create Date: 2026-01-08 09:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0015_clinical_chart"
down_revision = "0014_patient_ledger_entries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if (
        inspector.has_table("tooth_notes")
        and inspector.has_table("procedures")
        and inspector.has_table("treatment_plan_items")
    ):
        return

    procedure_status = postgresql.ENUM(
        "completed",
        name="procedure_status",
        create_type=False,
    )
    procedure_status.create(bind, checkfirst=True)

    treatment_plan_status = postgresql.ENUM(
        "proposed",
        "accepted",
        "declined",
        "completed",
        "cancelled",
        name="treatment_plan_status",
        create_type=False,
    )
    treatment_plan_status.create(bind, checkfirst=True)

    if not inspector.has_table("tooth_notes"):
        op.create_table(
            "tooth_notes",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("patient_id", sa.Integer(), nullable=False),
            sa.Column("tooth", sa.String(length=12), nullable=False),
            sa.Column("surface", sa.String(length=12), nullable=True),
            sa.Column("note", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("created_by_user_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        )
        op.create_index("ix_tooth_notes_patient_id", "tooth_notes", ["patient_id"])

    if not inspector.has_table("procedures"):
        op.create_table(
            "procedures",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("patient_id", sa.Integer(), nullable=False),
            sa.Column("appointment_id", sa.Integer(), nullable=True),
            sa.Column("tooth", sa.String(length=12), nullable=True),
            sa.Column("surface", sa.String(length=12), nullable=True),
            sa.Column("procedure_code", sa.String(length=50), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("fee_pence", sa.Integer(), nullable=True),
            sa.Column("status", procedure_status, nullable=False),
            sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
            sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"]),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        )
        op.create_index("ix_procedures_patient_id", "procedures", ["patient_id"])
        op.create_index("ix_procedures_appointment_id", "procedures", ["appointment_id"])

    if not inspector.has_table("treatment_plan_items"):
        op.create_table(
            "treatment_plan_items",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("patient_id", sa.Integer(), nullable=False),
            sa.Column("appointment_id", sa.Integer(), nullable=True),
            sa.Column("tooth", sa.String(length=12), nullable=True),
            sa.Column("surface", sa.String(length=12), nullable=True),
            sa.Column("procedure_code", sa.String(length=50), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("fee_pence", sa.Integer(), nullable=True),
            sa.Column("status", treatment_plan_status, nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("created_by_user_id", sa.Integer(), nullable=False),
            sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
            sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"]),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        )
        op.create_index(
            "ix_treatment_plan_items_patient_id",
            "treatment_plan_items",
            ["patient_id"],
        )
        op.create_index(
            "ix_treatment_plan_items_appointment_id",
            "treatment_plan_items",
            ["appointment_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_treatment_plan_items_appointment_id", table_name="treatment_plan_items")
    op.drop_index("ix_treatment_plan_items_patient_id", table_name="treatment_plan_items")
    op.drop_table("treatment_plan_items")
    op.drop_index("ix_procedures_appointment_id", table_name="procedures")
    op.drop_index("ix_procedures_patient_id", table_name="procedures")
    op.drop_table("procedures")
    op.drop_index("ix_tooth_notes_patient_id", table_name="tooth_notes")
    op.drop_table("tooth_notes")
    treatment_plan_status = postgresql.ENUM(
        "proposed",
        "accepted",
        "declined",
        "completed",
        "cancelled",
        name="treatment_plan_status",
        create_type=False,
    )
    treatment_plan_status.drop(op.get_bind(), checkfirst=True)
    procedure_status = postgresql.ENUM(
        "completed",
        name="procedure_status",
        create_type=False,
    )
    procedure_status.drop(op.get_bind(), checkfirst=True)
