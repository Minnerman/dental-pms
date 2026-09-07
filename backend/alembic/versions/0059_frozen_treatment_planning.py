"""Frozen native treatment planning; no historic rows are inferred or adopted."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0059_frozen_treatment_planning"
down_revision = "0058_clinical_note_revisions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "patient_treatment_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.UniqueConstraint("patient_id", name="uq_patient_treatment_plan_patient"),
        sa.UniqueConstraint("id", "patient_id", name="uq_patient_treatment_plan_identity"),
    )
    op.add_column("treatment_plan_items", sa.Column("plan_id", sa.Integer()))
    op.add_column("treatment_plan_items", sa.Column("treatment_id", sa.Integer()))
    op.add_column("treatment_plan_items", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("treatment_plan_items", sa.Column("planning_details", postgresql.JSONB()))
    op.add_column("treatment_plan_items", sa.Column("completed_procedure_id", sa.Integer()))
    op.create_index("ix_treatment_plan_items_plan_id", "treatment_plan_items", ["plan_id"])
    op.create_check_constraint("ck_plan_item_revision", "treatment_plan_items", "revision > 0")
    op.create_foreign_key("fk_plan_item_patient_workspace", "treatment_plan_items", "patient_treatment_plans", ["plan_id", "patient_id"], ["id", "patient_id"])
    op.create_foreign_key("fk_plan_item_catalogue", "treatment_plan_items", "treatments", ["treatment_id"], ["id"])
    op.create_foreign_key("fk_plan_item_completed_procedure", "treatment_plan_items", "procedures", ["completed_procedure_id"], ["id"])
    op.create_unique_constraint("uq_plan_item_completed_procedure", "treatment_plan_items", ["completed_procedure_id"])
    op.create_table(
        "treatment_plan_item_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("treatment_plan_items.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("recorded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("item_id", "revision", name="uq_planning_item_revision"),
    )
    op.create_table(
        "planning_mutation_receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.String(120), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("actor_user_id", "request_id", name="uq_planning_mutation_request"),
    )


def downgrade():
    connection = op.get_bind()
    for table in ("patient_treatment_plans", "treatment_plan_item_revisions", "planning_mutation_receipts"):
        if connection.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table})")).scalar():
            raise RuntimeError("Cannot downgrade: native planning snapshots, revisions or requests exist")
    if connection.execute(sa.text("SELECT EXISTS (SELECT 1 FROM treatment_plan_items WHERE plan_id IS NOT NULL OR treatment_id IS NOT NULL OR planning_details IS NOT NULL OR completed_procedure_id IS NOT NULL OR revision <> 1)")).scalar():
        raise RuntimeError("Cannot downgrade: native planning item data exists")
    op.drop_table("planning_mutation_receipts")
    op.drop_table("treatment_plan_item_revisions")
    op.drop_constraint("uq_plan_item_completed_procedure", "treatment_plan_items", type_="unique")
    for name in ("fk_plan_item_completed_procedure", "fk_plan_item_catalogue", "fk_plan_item_patient_workspace"):
        op.drop_constraint(name, "treatment_plan_items", type_="foreignkey")
    op.drop_constraint("ck_plan_item_revision", "treatment_plan_items", type_="check")
    op.drop_index("ix_treatment_plan_items_plan_id", table_name="treatment_plan_items")
    for column in ("completed_procedure_id", "planning_details", "revision", "treatment_id", "plan_id"):
        op.drop_column("treatment_plan_items", column)
    op.drop_table("patient_treatment_plans")
