"""link patient documents to attachments

Revision ID: 0020_patient_docs_attach
Revises: 0019_patient_documents
Create Date: 2026-01-11 13:36:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0020_patient_docs_attach"
down_revision = "0019_patient_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patient_documents", sa.Column("attachment_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_patient_documents_attachment_id",
        "patient_documents",
        "attachments",
        ["attachment_id"],
        ["id"],
    )
    op.create_index(
        "ix_patient_documents_attachment_id",
        "patient_documents",
        ["attachment_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_patient_documents_attachment_id", table_name="patient_documents")
    op.drop_constraint("fk_patient_documents_attachment_id", "patient_documents", type_="foreignkey")
    op.drop_column("patient_documents", "attachment_id")
