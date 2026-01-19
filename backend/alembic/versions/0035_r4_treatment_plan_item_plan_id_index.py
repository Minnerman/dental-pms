"""add plan id index for r4 treatment plan items

Revision ID: 0035_r4_treatment_plan_item_plan_id_index
Revises: 0034_r4_treatment_plan_import
Create Date: 2026-01-19 00:00:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "0035_r4_treatment_plan_item_plan_id_index"
down_revision = "0034_r4_treatment_plan_import"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_r4_treatment_plan_items_plan_id",
        "r4_treatment_plan_items",
        ["treatment_plan_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_r4_treatment_plan_items_plan_id", table_name="r4_treatment_plan_items")
