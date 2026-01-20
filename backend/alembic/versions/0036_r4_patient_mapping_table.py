"""add r4 patient mapping table

Revision ID: 0036_r4_patient_mapping_table
Revises: 0035_r4_treatment_plan_item_plan_id_index
Create Date: 2026-01-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0036_r4_patient_mapping_table"
down_revision = "0035_r4_treatment_plan_item_plan_id_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "r4_patient_mappings" not in inspector.get_table_names():
        op.create_table(
            "r4_patient_mappings",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "legacy_source",
                sa.String(length=120),
                server_default=sa.text("'r4'"),
                nullable=False,
            ),
            sa.Column("legacy_patient_code", sa.Integer(), nullable=False),
            sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
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
            sa.Column(
                "created_by_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id"),
                nullable=False,
            ),
            sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.UniqueConstraint(
                "legacy_source",
                "legacy_patient_code",
                name="uq_r4_patient_mappings_legacy_key",
            ),
            sa.UniqueConstraint(
                "legacy_source",
                "patient_id",
                name="uq_r4_patient_mappings_patient",
            ),
        )


def downgrade() -> None:
    op.drop_table("r4_patient_mappings")
