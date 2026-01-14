"""add recall communication last contact index

Revision ID: 0029_recall_comm_last_contact_index
Revises: 0028_recall_contact_other_detail
Create Date: 2026-01-14 18:40:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "0029_recall_comm_last_contact_index"
down_revision = "0028_recall_contact_other_detail"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_prc_recall_contact_ts "
        "ON patient_recall_communications "
        "(recall_id, COALESCE(contacted_at, created_at) DESC, id DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_prc_recall_contact_ts")
