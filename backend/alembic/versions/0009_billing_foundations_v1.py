"""billing foundations v1

Revision ID: 0009_billing_foundations_v1
Revises: 0008_add_invoices
Create Date: 2026-01-06 21:10:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_billing_foundations_v1"
down_revision = "0008_add_invoices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    patient_category = sa.Enum(
        "CLINIC_PRIVATE",
        "DOMICILIARY_PRIVATE",
        "DENPLAN",
        name="patient_category",
    )
    fee_type = sa.Enum("FIXED", "RANGE", "N_A", name="fee_type")
    estimate_status = sa.Enum(
        "DRAFT",
        "ISSUED",
        "ACCEPTED",
        "DECLINED",
        "SUPERSEDED",
        name="estimate_status",
    )
    estimate_fee_type = sa.Enum("FIXED", "RANGE", name="estimate_fee_type")

    patient_category.create(op.get_bind(), checkfirst=True)
    fee_type.create(op.get_bind(), checkfirst=True)
    estimate_status.create(op.get_bind(), checkfirst=True)
    estimate_fee_type.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "patients",
        sa.Column(
            "patient_category",
            patient_category,
            nullable=False,
            server_default="CLINIC_PRIVATE",
        ),
    )
    op.add_column("patients", sa.Column("denplan_member_no", sa.String(length=64), nullable=True))
    op.add_column("patients", sa.Column("denplan_plan_name", sa.String(length=120), nullable=True))

    op.create_table(
        "treatments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("default_duration_minutes", sa.Integer(), nullable=True),
        sa.Column(
            "is_denplan_included_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
    )

    op.create_table(
        "treatment_fees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("treatment_id", sa.Integer(), nullable=False),
        sa.Column("patient_category", patient_category, nullable=False),
        sa.Column("fee_type", fee_type, nullable=False),
        sa.Column("amount_pence", sa.Integer(), nullable=True),
        sa.Column("min_amount_pence", sa.Integer(), nullable=True),
        sa.Column("max_amount_pence", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["treatment_id"], ["treatments.id"]),
        sa.UniqueConstraint("treatment_id", "patient_category"),
    )
    op.create_index("ix_treatment_fees_treatment_id", "treatment_fees", ["treatment_id"])

    op.create_table(
        "estimates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("appointment_id", sa.Integer(), nullable=True),
        sa.Column("category_snapshot", patient_category, nullable=False),
        sa.Column("status", estimate_status, nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
    )
    op.create_index("ix_estimates_patient_id", "estimates", ["patient_id"])
    op.create_index("ix_estimates_appointment_id", "estimates", ["appointment_id"])

    op.create_table(
        "estimate_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("estimate_id", sa.Integer(), nullable=False),
        sa.Column("treatment_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_amount_pence", sa.Integer(), nullable=True),
        sa.Column("min_unit_amount_pence", sa.Integer(), nullable=True),
        sa.Column("max_unit_amount_pence", sa.Integer(), nullable=True),
        sa.Column("fee_type", estimate_fee_type, nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["estimate_id"], ["estimates.id"]),
        sa.ForeignKeyConstraint(["treatment_id"], ["treatments.id"]),
    )
    op.create_index("ix_estimate_items_estimate_id", "estimate_items", ["estimate_id"])


def downgrade() -> None:
    op.drop_index("ix_estimate_items_estimate_id", table_name="estimate_items")
    op.drop_table("estimate_items")

    op.drop_index("ix_estimates_appointment_id", table_name="estimates")
    op.drop_index("ix_estimates_patient_id", table_name="estimates")
    op.drop_table("estimates")

    op.drop_index("ix_treatment_fees_treatment_id", table_name="treatment_fees")
    op.drop_table("treatment_fees")
    op.drop_table("treatments")

    op.drop_column("patients", "denplan_plan_name")
    op.drop_column("patients", "denplan_member_no")
    op.drop_column("patients", "patient_category")

    op.execute("DROP TYPE IF EXISTS estimate_fee_type")
    op.execute("DROP TYPE IF EXISTS estimate_status")
    op.execute("DROP TYPE IF EXISTS fee_type")
    op.execute("DROP TYPE IF EXISTS patient_category")
