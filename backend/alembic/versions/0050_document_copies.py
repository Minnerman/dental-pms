"""Preserve issued PDFs and link their clinical notes."""
from alembic import op
import sqlalchemy as sa

revision = "0050_document_copies"
down_revision = "0049_prescription_templates"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("prescription_templates", sa.Column("stock_key", sa.String(80)))
    op.create_unique_constraint("uq_prescription_stock_key", "prescription_templates", ["stock_key"])
    op.add_column("patient_documents", sa.Column("document_kind", sa.String(30), nullable=False, server_default="unknown"))
    op.add_column("patient_documents", sa.Column("frozen_pdf", sa.LargeBinary()))
    op.add_column("patient_documents", sa.Column("issue_blockers", sa.JSON()))
    # Historical documents require fresh preparation; never infer email eligibility from a mutable title.
    op.create_table("document_copies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("patient_documents.id", ondelete="SET NULL")),
        sa.Column("source_document_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("document_kind", sa.String(30), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("recipient", sa.String(320)),
        sa.Column("sender", sa.String(320)),
        sa.Column("pdf_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("request_id", sa.String(120), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("completed_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("created_by_user_id", "request_id", name="uq_document_copy_request"),
    )
    op.create_index("ix_document_copies_patient_id", "document_copies", ["patient_id"])
    op.add_column("notes", sa.Column("document_copy_id", sa.Integer(), sa.ForeignKey("document_copies.id")))
    op.create_unique_constraint("uq_note_document_copy", "notes", ["document_copy_id"])


def downgrade():
    op.drop_constraint("uq_prescription_stock_key", "prescription_templates", type_="unique")
    op.drop_column("prescription_templates", "stock_key")
    op.drop_constraint("uq_note_document_copy", "notes", type_="unique")
    op.drop_column("notes", "document_copy_id")
    op.drop_table("document_copies")
    for column in ("issue_blockers", "frozen_pdf", "document_kind"):
        op.drop_column("patient_documents", column)
