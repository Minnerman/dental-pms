"""Add cursor-friendly index for r4 treatment transactions

Revision ID: 0040_r4_treatment_transactions_cursor_index
Revises: 0039_r4_users_role
Create Date: 2026-01-22 20:10:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "0040_r4_treatment_transactions_cursor_index"
down_revision = "0039_r4_users_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS "
        "ix_r4_treatment_transactions_patient_code_performed_at_tx "
        "ON r4_treatment_transactions "
        "(patient_code, performed_at DESC, legacy_transaction_id DESC)"
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS "
        "ix_r4_treatment_transactions_patient_code_performed_at_tx"
    )
