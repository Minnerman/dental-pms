"""add document templates

Revision ID: 0017_document_templates
Revises: 0016_patient_referral_fields
Create Date: 2026-01-11 12:28:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0017_document_templates"
down_revision = "0016_patient_referral_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("document_templates"):
        return

    kind_enum = postgresql.ENUM(
        "letter",
        "prescription",
        name="document_template_kind",
        create_type=False,
    )
    kind_enum.create(bind, checkfirst=True)

    op.create_table(
        "document_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("kind", kind_enum, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["deleted_by_user_id"], ["users.id"]),
    )
    op.create_index("ix_document_templates_kind", "document_templates", ["kind"])
    op.create_index("ix_document_templates_is_active", "document_templates", ["is_active"])
    op.create_index("ix_document_templates_deleted_at", "document_templates", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_document_templates_deleted_at", table_name="document_templates")
    op.drop_index("ix_document_templates_is_active", table_name="document_templates")
    op.drop_index("ix_document_templates_kind", table_name="document_templates")
    op.drop_table("document_templates")
    kind_enum = postgresql.ENUM(
        "letter",
        "prescription",
        name="document_template_kind",
        create_type=False,
    )
    kind_enum.drop(op.get_bind(), checkfirst=True)
