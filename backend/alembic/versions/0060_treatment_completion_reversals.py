"""Auditable completion corrections; no source records or fees are backfilled."""
from alembic import op
import sqlalchemy as sa

revision = "0060_treatment_completion_reversals"
down_revision = "0059_frozen_treatment_planning"
branch_labels = None
depends_on = None


def upgrade():
    # No row uses the new enum value until this migration is committed.
    op.execute("ALTER TYPE procedure_status ADD VALUE IF NOT EXISTS 'voided'")
    op.create_table(
        "treatment_plan_completions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("treatment_plan_items.id"), nullable=False),
        sa.Column("cycle", sa.Integer(), nullable=False),
        sa.Column("previous_status", sa.String(12), nullable=False),
        sa.Column("procedure_id", sa.Integer(), sa.ForeignKey("procedures.id"), unique=True, nullable=False),
        sa.Column("charge_id", sa.Integer(), sa.ForeignKey("patient_ledger_entries.id"), unique=True, nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("item_id", "cycle", name="uq_plan_completion_cycle"),
        sa.CheckConstraint("cycle > 0", name="ck_plan_completion_cycle"),
        sa.CheckConstraint("previous_status IN ('proposed', 'accepted')", name="ck_plan_completion_previous_status"),
    )
    op.create_table(
        "treatment_plan_completion_reversals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("completion_id", sa.Integer(), sa.ForeignKey("treatment_plan_completions.id"), unique=True, nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("adjustment_id", sa.Integer(), sa.ForeignKey("patient_ledger_entries.id"), unique=True, nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("recorded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
    )


def downgrade():
    connection = op.get_bind()
    for table in ("treatment_plan_completions", "treatment_plan_completion_reversals"):
        if connection.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table})")).scalar():
            raise RuntimeError("Cannot downgrade: treatment completion cycles or reversals exist")
    if connection.execute(sa.text("SELECT EXISTS (SELECT 1 FROM procedures WHERE status::text = 'voided')")).scalar():
        raise RuntimeError("Cannot downgrade: voided procedures must retain their status")
    op.drop_table("treatment_plan_completion_reversals")
    op.drop_table("treatment_plan_completions")
    # PostgreSQL cannot DROP a single enum value. With no voided rows, restore
    # the original exact enum while retaining every procedure column value.
    op.execute("ALTER TYPE procedure_status RENAME TO procedure_status_with_voided")
    op.execute("CREATE TYPE procedure_status AS ENUM ('completed')")
    op.execute("ALTER TABLE procedures ALTER COLUMN status TYPE procedure_status USING status::text::procedure_status")
    op.execute("DROP TYPE procedure_status_with_voided")
