"""add attachments

Revision ID: 0018_attachments
Revises: 0017_document_templates
Create Date: 2026-01-11 13:02:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_attachments"
down_revision = "0017_document_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_attachments_patient_id", "attachments", ["patient_id"])
    op.create_index("ix_attachments_created_at", "attachments", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_attachments_created_at", table_name="attachments")
    op.drop_index("ix_attachments_patient_id", table_name="attachments")
    op.drop_table("attachments")
