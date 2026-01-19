"""add r4 treatment plan import tables

Revision ID: 0034_r4_treatment_plan_import
Revises: 0033_legacy_resolution_events
Create Date: 2026-01-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0034_r4_treatment_plan_import"
down_revision = "0033_legacy_resolution_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "r4_treatments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "legacy_source",
            sa.String(length=120),
            server_default=sa.text("'r4'"),
            nullable=False,
        ),
        sa.Column("legacy_treatment_code", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("short_code", sa.String(length=50), nullable=True),
        sa.Column("default_time", sa.Integer(), nullable=True),
        sa.Column(
            "exam",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "patient_required",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
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
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint(
            "legacy_source",
            "legacy_treatment_code",
            name="uq_r4_treatments_legacy_source_code",
        ),
    )
    op.create_table(
        "r4_treatment_plans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=True),
        sa.Column(
            "legacy_source",
            sa.String(length=120),
            server_default=sa.text("'r4'"),
            nullable=False,
        ),
        sa.Column("legacy_patient_code", sa.Integer(), nullable=False),
        sa.Column("legacy_tp_number", sa.Integer(), nullable=False),
        sa.Column("plan_index", sa.SmallInteger(), nullable=True),
        sa.Column(
            "is_master",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_current",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_accepted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("creation_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acceptance_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completion_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("reason_id", sa.Integer(), nullable=True),
        sa.Column("tp_group", sa.Integer(), nullable=True),
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
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint(
            "legacy_source",
            "legacy_patient_code",
            "legacy_tp_number",
            name="uq_r4_treatment_plans_legacy_key",
        ),
    )
    op.create_table(
        "r4_treatment_plan_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "treatment_plan_id",
            sa.Integer(),
            sa.ForeignKey("r4_treatment_plans.id"),
            nullable=False,
        ),
        sa.Column(
            "legacy_source",
            sa.String(length=120),
            server_default=sa.text("'r4'"),
            nullable=False,
        ),
        sa.Column("legacy_tp_item", sa.SmallInteger(), nullable=False),
        sa.Column("legacy_tp_item_key", sa.Integer(), nullable=True),
        sa.Column("code_id", sa.Integer(), nullable=True),
        sa.Column("tooth", sa.SmallInteger(), nullable=True),
        sa.Column("surface", sa.SmallInteger(), nullable=True),
        sa.Column("appointment_need_id", sa.Integer(), nullable=True),
        sa.Column(
            "completed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("completed_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("patient_cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("dpb_cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("discretionary_cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("material", sa.String(length=1), nullable=True),
        sa.Column("arch_code", sa.SmallInteger(), nullable=True),
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
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint(
            "legacy_source",
            "legacy_tp_item_key",
            name="uq_r4_treatment_plan_items_legacy_key",
        ),
        sa.UniqueConstraint(
            "treatment_plan_id",
            "legacy_tp_item",
            name="uq_r4_treatment_plan_items_plan_item",
        ),
    )
    op.create_table(
        "r4_treatment_plan_reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "treatment_plan_id",
            sa.Integer(),
            sa.ForeignKey("r4_treatment_plans.id"),
            nullable=False,
        ),
        sa.Column("temporary_note", sa.Text(), nullable=True),
        sa.Column(
            "reviewed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("last_edit_user", sa.String(length=120), nullable=True),
        sa.Column("last_edit_date", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint(
            "treatment_plan_id",
            name="uq_r4_treatment_plan_reviews_plan",
        ),
    )


def downgrade() -> None:
    op.drop_table("r4_treatment_plan_reviews")
    op.drop_table("r4_treatment_plan_items")
    op.drop_table("r4_treatment_plans")
    op.drop_table("r4_treatments")
