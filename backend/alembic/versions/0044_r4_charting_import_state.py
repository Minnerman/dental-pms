"""add r4 charting import state

Revision ID: 0044_r4_charting_import_state
Revises: 0043_r4_charting_tables
Create Date: 2026-01-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0044_r4_charting_import_state"
down_revision = "0043_r4_charting_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "r4_charting_import_state",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("legacy_patient_code", sa.Integer(), nullable=True),
        sa.Column("last_imported_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("patient_id", name="uq_r4_charting_import_state_patient"),
    )
    op.create_index(
        "ix_r4_charting_import_state_patient",
        "r4_charting_import_state",
        ["patient_id"],
    )
    op.create_index(
        "ix_r4_perio_probes_patient_date",
        "r4_perio_probes",
        ["legacy_source", "legacy_patient_code", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_r4_perio_probes_patient_date", table_name="r4_perio_probes")
    op.drop_index("ix_r4_charting_import_state_patient", table_name="r4_charting_import_state")
    op.drop_table("r4_charting_import_state")
