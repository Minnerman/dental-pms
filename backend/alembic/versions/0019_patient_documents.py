"""add patient documents

Revision ID: 0019_patient_documents
Revises: 0018_attachments
Create Date: 2026-01-11 13:14:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0019_patient_documents"
down_revision = "0018_attachments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("rendered_content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["document_templates.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
    )
    op.create_index("ix_patient_documents_patient_id", "patient_documents", ["patient_id"])
    op.create_index("ix_patient_documents_created_at", "patient_documents", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_patient_documents_created_at", table_name="patient_documents")
    op.drop_index("ix_patient_documents_patient_id", table_name="patient_documents")
    op.drop_table("patient_documents")
