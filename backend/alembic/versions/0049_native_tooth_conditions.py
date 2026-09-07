"""add native current tooth observations, without changing historical data

Revision ID: 0049_native_tooth_conditions
Revises: 0048_r4_charting_canonical_content_hash
"""

from alembic import op
import sqlalchemy as sa

revision = "0049_native_tooth_conditions"
down_revision = "0048_r4_charting_canonical_content_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tooth_conditions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("tooth", sa.String(length=3), nullable=False),
        sa.Column("condition", sa.String(length=20), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("patient_id", "tooth", name="uq_tooth_conditions_patient_tooth"),
        sa.CheckConstraint("revision > 0", name="ck_tooth_conditions_revision"),
        sa.CheckConstraint(
            "condition IS NULL OR condition IN "
            "('present', 'missing', 'deciduous', 'implant', 'unerupted', 'impacted')",
            name="ck_tooth_conditions_value",
        ),
    )


def downgrade() -> None:
    op.drop_table("tooth_conditions")
