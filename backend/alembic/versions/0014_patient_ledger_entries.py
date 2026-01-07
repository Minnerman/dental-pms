"""add patient ledger entries

Revision ID: 0014_patient_ledger_entries
Revises: 0013_patient_recall_flags
Create Date: 2026-01-07 21:05:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0014_patient_ledger_entries"
down_revision = "0013_patient_recall_flags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ledger_entry_type = sa.Enum(
        "charge",
        "payment",
        "adjustment",
        name="ledger_entry_type",
    )
    ledger_entry_type.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "patient_ledger_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("entry_type", ledger_entry_type, nullable=False),
        sa.Column("amount_pence", sa.Integer(), nullable=False),
        sa.Column(
            "method",
            sa.Enum("cash", "card", "bank_transfer", "other", name="payment_method"),
            nullable=True,
        ),
        sa.Column("reference", sa.String(length=120), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("related_invoice_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["related_invoice_id"], ["invoices.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
    )
    op.create_index(
        "ix_patient_ledger_entries_patient_id",
        "patient_ledger_entries",
        ["patient_id"],
    )
    op.create_index(
        "ix_patient_ledger_entries_related_invoice_id",
        "patient_ledger_entries",
        ["related_invoice_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_patient_ledger_entries_related_invoice_id", table_name="patient_ledger_entries")
    op.drop_index("ix_patient_ledger_entries_patient_id", table_name="patient_ledger_entries")
    op.drop_table("patient_ledger_entries")
    ledger_entry_type = sa.Enum(
        "charge",
        "payment",
        "adjustment",
        name="ledger_entry_type",
    )
    ledger_entry_type.drop(op.get_bind(), checkfirst=True)
