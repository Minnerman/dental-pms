"""Explicit routine planning defaults; no clinical or catalogue inference."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0062_treatment_planning_defaults"
down_revision = "0061_treatment_index_effective_fees"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("treatments", sa.Column("planning_defaults", postgresql.JSONB(none_as_null=True), nullable=True))
    op.add_column("treatments", sa.Column("planning_defaults_revision", sa.Integer(), server_default="0", nullable=False))
    op.create_check_constraint("ck_treatment_planning_defaults", "treatments",
        "planning_defaults IS NULL OR jsonb_typeof(planning_defaults) = 'object'")
    op.create_check_constraint("ck_treatment_planning_defaults_revision", "treatments", "planning_defaults_revision >= 0")


def downgrade():
    db = op.get_bind()
    if db.execute(sa.text("SELECT EXISTS (SELECT 1 FROM treatments WHERE planning_defaults IS NOT NULL OR planning_defaults_revision <> 0)")).scalar():
        raise RuntimeError("Cannot downgrade: explicit treatment planning defaults or their revision history exist")
    if db.execute(sa.text("SELECT EXISTS (SELECT 1 FROM treatment_plan_items WHERE planning_details->'appliance' IS NOT NULL AND planning_details->'appliance' <> 'null'::jsonb)")).scalar():
        raise RuntimeError("Cannot downgrade: grouped treatment appliances require member-aware application code")
    op.drop_constraint("ck_treatment_planning_defaults_revision", "treatments", type_="check")
    op.drop_constraint("ck_treatment_planning_defaults", "treatments", type_="check")
    op.drop_column("treatments", "planning_defaults_revision")
    op.drop_column("treatments", "planning_defaults")
