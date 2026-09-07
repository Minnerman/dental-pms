"""Explicit treatment grouping and immutable date-effective fees, no price backfill."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0061_treatment_index_effective_fees"
down_revision = "0060_treatment_completion_reversals"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("treatments", sa.Column("level", sa.String(12), nullable=True))
    op.add_column("treatments", sa.Column("display_order", sa.Integer(), server_default="0", nullable=False))
    op.add_column("treatments", sa.Column("routine_key", sa.String(80), nullable=True))
    op.create_unique_constraint("uq_treatments_routine_key", "treatments", ["routine_key"])
    op.create_check_constraint("ck_treatment_level", "treatments", "level IS NULL OR level IN ('tooth','root','crown','surface','general')")
    op.create_check_constraint("ck_treatment_display_order", "treatments", "display_order >= 0")
    op.create_table("treatment_fee_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("treatment_id", sa.Integer(), sa.ForeignKey("treatments.id"), nullable=False),
        sa.Column("patient_category", postgresql.ENUM(name="patient_category", create_type=False), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("fee_type", postgresql.ENUM(name="fee_type", create_type=False), nullable=True),
        sa.Column("amount_pence", sa.Integer(), nullable=True),
        sa.Column("min_amount_pence", sa.Integer(), nullable=True),
        sa.Column("max_amount_pence", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("recorded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.String(120), nullable=True),
        sa.Column("request_fingerprint", sa.String(64), nullable=True),
        sa.UniqueConstraint("treatment_id", "patient_category", "revision", name="uq_treatment_fee_revision"),
        sa.UniqueConstraint("recorded_by_user_id", "request_id", name="uq_treatment_fee_request"),
        sa.CheckConstraint("revision > 0", name="ck_treatment_fee_revision"),
    )
    op.create_index("ix_treatment_fee_effective", "treatment_fee_versions", ["treatment_id", "patient_category", "effective_from", "revision"])


def downgrade():
    db = op.get_bind()
    if db.execute(sa.text("SELECT EXISTS (SELECT 1 FROM treatment_fee_versions)")).scalar():
        raise RuntimeError("Cannot downgrade: effective treatment fee history exists")
    if db.execute(sa.text("SELECT EXISTS (SELECT 1 FROM treatments WHERE level IS NOT NULL OR display_order <> 0 OR routine_key IS NOT NULL)")).scalar():
        raise RuntimeError("Cannot downgrade: explicit treatment index metadata exists")
    op.drop_index("ix_treatment_fee_effective", table_name="treatment_fee_versions")
    op.drop_table("treatment_fee_versions")
    op.drop_constraint("ck_treatment_display_order", "treatments", type_="check")
    op.drop_constraint("ck_treatment_level", "treatments", type_="check")
    op.drop_constraint("uq_treatments_routine_key", "treatments", type_="unique")
    for name in ("routine_key", "display_order", "level"):
        op.drop_column("treatments", name)
