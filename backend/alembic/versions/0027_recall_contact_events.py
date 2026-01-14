"""extend recall communication for contact logging

Revision ID: 0027_recall_contact_events
Revises: 0026_patient_recall_communications
Create Date: 2026-01-14 12:45:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0027_recall_contact_events"
down_revision = "0026_patient_recall_communications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("patient_recall_communications"):
        return

    op.execute(
        "ALTER TYPE patient_recall_comm_channel ADD VALUE IF NOT EXISTS 'other'"
    )

    columns = {col["name"] for col in inspector.get_columns("patient_recall_communications")}
    if "outcome" not in columns:
        op.add_column(
            "patient_recall_communications", sa.Column("outcome", sa.Text(), nullable=True)
        )
    if "contacted_at" not in columns:
        op.add_column(
            "patient_recall_communications",
            sa.Column("contacted_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            "ix_patient_recall_communications_contacted_at",
            "patient_recall_communications",
            ["contacted_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("patient_recall_communications"):
        return

    indexes = {idx["name"] for idx in inspector.get_indexes("patient_recall_communications")}
    if "ix_patient_recall_communications_contacted_at" in indexes:
        op.drop_index(
            "ix_patient_recall_communications_contacted_at",
            table_name="patient_recall_communications",
        )

    columns = {col["name"] for col in inspector.get_columns("patient_recall_communications")}
    if "contacted_at" in columns:
        op.drop_column("patient_recall_communications", "contacted_at")
    if "outcome" in columns:
        op.drop_column("patient_recall_communications", "outcome")
