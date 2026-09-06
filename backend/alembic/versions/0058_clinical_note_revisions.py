"""Native note amendments and plain-text clinical templates.

Existing text, attribution and timestamps are not rewritten. Revision 1 on old
rows means the current known baseline, not a reconstruction of earlier edits.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0058_clinical_note_revisions"
down_revision = "0057_labelled_patient_phones"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "clinical_note_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("fields", postgresql.JSONB(), nullable=False),
        sa.Column("codes", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    for table in ("notes", "tooth_notes"):
        op.add_column(table, sa.Column("revision", sa.Integer(), server_default="1", nullable=False))
        op.add_column(table, sa.Column("clinical_date", sa.Date(), nullable=True))
        op.add_column(table, sa.Column("category", sa.String(24), nullable=True))
        op.add_column(table, sa.Column("template_id", sa.Integer(), nullable=True))
        op.create_foreign_key(f"fk_{table}_clinical_template", table, "clinical_note_templates", ["template_id"], ["id"])
        op.add_column(table, sa.Column("template_revision", sa.Integer(), nullable=True))
        op.add_column(table, sa.Column("codes", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False))
        op.create_index(f"ix_{table}_journal_patient", table, ["patient_id", "created_at", "id"])
    op.create_table(
        "native_note_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("note_id", sa.Integer(), sa.ForeignKey("notes.id"), nullable=True),
        sa.Column("tooth_note_id", sa.Integer(), sa.ForeignKey("tooth_notes.id"), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("recorded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("baseline", sa.Boolean(), nullable=False),
        sa.CheckConstraint("(note_id IS NULL) <> (tooth_note_id IS NULL)", name="ck_native_revision_one_source"),
        sa.UniqueConstraint("note_id", "revision", name="uq_native_note_revision"),
        sa.UniqueConstraint("tooth_note_id", "revision", name="uq_native_tooth_note_revision"),
    )
    op.create_table(
        "clinical_note_template_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("clinical_note_templates.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("recorded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("template_id", "revision", name="uq_clinical_template_revision"),
    )
    op.create_table(
        "note_mutation_receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.String(120), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("actor_user_id", "request_id", name="uq_note_mutation_request"),
    )


def downgrade():
    db = op.get_bind()
    tables = ("native_note_revisions", "clinical_note_template_revisions", "clinical_note_templates", "note_mutation_receipts")
    for table in tables:
        if db.scalar(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table})")):
            raise RuntimeError("Cannot downgrade: native note history or template data exists. No data was removed.")
    for table in ("notes", "tooth_notes"):
        if db.scalar(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table} WHERE revision <> 1 OR clinical_date IS NOT NULL OR category IS NOT NULL OR template_id IS NOT NULL OR template_revision IS NOT NULL OR codes <> '[]'::jsonb)")):
            raise RuntimeError("Cannot downgrade: native note metadata exists. No data was removed.")
    op.drop_table("note_mutation_receipts")
    op.drop_table("clinical_note_template_revisions")
    op.drop_table("native_note_revisions")
    for table in ("notes", "tooth_notes"):
        op.drop_index(f"ix_{table}_journal_patient", table_name=table)
        op.drop_constraint(f"fk_{table}_clinical_template", table, type_="foreignkey")
        for column in ("codes", "template_revision", "template_id", "category", "clinical_date", "revision"):
            op.drop_column(table, column)
    op.drop_table("clinical_note_templates")
