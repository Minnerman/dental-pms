"""add recall contact other detail

Revision ID: 0028_recall_contact_other_detail
Revises: 0027_recall_contact_events
Create Date: 2026-01-14 13:05:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0028_recall_contact_other_detail"
down_revision = "0027_recall_contact_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("patient_recall_communications"):
        return

    columns = {col["name"] for col in inspector.get_columns("patient_recall_communications")}
    if "other_detail" not in columns:
        op.add_column(
            "patient_recall_communications",
            sa.Column("other_detail", sa.Text(), nullable=True),
        )

    op.execute(
        """
        UPDATE patient_recall_communications
        SET other_detail = notes
        WHERE channel = 'other'
          AND (other_detail IS NULL OR other_detail = '')
          AND notes IS NOT NULL
          AND notes <> ''
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("patient_recall_communications"):
        return

    columns = {col["name"] for col in inspector.get_columns("patient_recall_communications")}
    if "other_detail" in columns:
        op.drop_column("patient_recall_communications", "other_detail")
