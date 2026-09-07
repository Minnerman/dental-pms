"""Add explicit current bridge groups without inferring historical membership.

Revision ID: 0054_tooth_bridge_groups
Revises: 0053_crown_observation
"""

from alembic import op
import sqlalchemy as sa

revision = "0054_tooth_bridge_groups"
down_revision = "0053_crown_observation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("tooth_bridge_groups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("id", "patient_id", name="uq_tooth_bridge_group_patient"),
    )
    op.create_index("ix_tooth_bridge_groups_patient_id", "tooth_bridge_groups", ["patient_id"])
    op.add_column("tooth_conditions", sa.Column("bridge_group_id", sa.Integer(), nullable=True))
    op.add_column("tooth_conditions", sa.Column("bridge_role", sa.String(12), nullable=True))
    op.create_index("ix_tooth_conditions_bridge_group_id", "tooth_conditions", ["bridge_group_id"])
    op.create_foreign_key("fk_tooth_condition_bridge_patient", "tooth_conditions", "tooth_bridge_groups",
        ["bridge_group_id", "patient_id"], ["id", "patient_id"])
    op.create_check_constraint("ck_tooth_conditions_bridge_role", "tooth_conditions",
        "(bridge_group_id IS NULL AND bridge_role IS NULL) OR "
        "(bridge_group_id IS NOT NULL AND bridge_role IS NOT NULL "
        "AND bridge_role IN ('abutment', 'pontic', 'wing'))")


def downgrade() -> None:
    if op.get_bind().scalar(sa.text(
        "SELECT EXISTS (SELECT 1 FROM tooth_bridge_groups) OR EXISTS "
        "(SELECT 1 FROM tooth_conditions WHERE crown_observation->>'kind' IN "
        "('porcelain_bonded', 'denture_cocr', 'denture_acrylic'))"
    )):
        raise RuntimeError("Cannot downgrade: native bridge groups or extended crown observations exist. No data was changed.")
    op.drop_constraint("ck_tooth_conditions_bridge_role", "tooth_conditions", type_="check")
    op.drop_constraint("fk_tooth_condition_bridge_patient", "tooth_conditions", type_="foreignkey")
    op.drop_index("ix_tooth_conditions_bridge_group_id", table_name="tooth_conditions")
    op.drop_column("tooth_conditions", "bridge_role")
    op.drop_column("tooth_conditions", "bridge_group_id")
    op.drop_index("ix_tooth_bridge_groups_patient_id", table_name="tooth_bridge_groups")
    op.drop_table("tooth_bridge_groups")
