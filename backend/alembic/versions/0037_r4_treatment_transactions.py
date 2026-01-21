"""Add R4 treatment transactions table

Revision ID: 0037_r4_treatment_transactions
Revises: 0036_r4_patient_mapping_table
Create Date: 2026-01-21 11:35:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0037_r4_treatment_transactions"
down_revision = "0036_r4_patient_mapping_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "r4_treatment_transactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("legacy_source", sa.String(length=120), nullable=False, server_default="r4"),
        sa.Column("legacy_transaction_id", sa.Integer(), nullable=False),
        sa.Column("patient_code", sa.Integer(), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("treatment_code", sa.Integer(), nullable=True),
        sa.Column("trans_code", sa.Integer(), nullable=True),
        sa.Column("patient_cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("dpb_cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("recorded_by", sa.Integer(), nullable=True),
        sa.Column("user_code", sa.Integer(), nullable=True),
        sa.Column("tp_number", sa.Integer(), nullable=True),
        sa.Column("tp_item", sa.Integer(), nullable=True),
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
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.UniqueConstraint(
            "legacy_source",
            "legacy_transaction_id",
            name="uq_r4_treatment_transactions_legacy_key",
        ),
    )
    op.create_index(
        "ix_r4_treatment_transactions_patient_code_performed_at",
        "r4_treatment_transactions",
        ["patient_code", "performed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_r4_treatment_transactions_patient_code_performed_at",
        table_name="r4_treatment_transactions",
    )
    op.drop_table("r4_treatment_transactions")
