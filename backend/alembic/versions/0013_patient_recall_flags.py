"""add patient recall and flags

Revision ID: 0013_patient_recall_flags
Revises: 0012_appt_cancel_fields
Create Date: 2026-01-07 20:42:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_patient_recall_flags"
down_revision = "0012_appt_cancel_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    recall_status = sa.Enum(
        "due",
        "contacted",
        "booked",
        "not_required",
        name="recall_status",
    )
    recall_status.create(op.get_bind(), checkfirst=True)
    op.add_column("patients", sa.Column("alerts_financial", sa.Text(), nullable=True))
    op.add_column("patients", sa.Column("alerts_access", sa.Text(), nullable=True))
    op.add_column(
        "patients",
        sa.Column("recall_interval_months", sa.Integer(), nullable=False, server_default="6"),
    )
    op.add_column("patients", sa.Column("recall_due_date", sa.Date(), nullable=True))
    op.add_column("patients", sa.Column("recall_status", recall_status, nullable=True))
    op.add_column(
        "patients", sa.Column("recall_last_set_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "patients",
        sa.Column("recall_last_set_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_patients_recall_last_set_by_user_id_users",
        "patients",
        "users",
        ["recall_last_set_by_user_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_patients_recall_last_set_by_user_id_users",
        "patients",
        type_="foreignkey",
    )
    op.drop_column("patients", "recall_last_set_by_user_id")
    op.drop_column("patients", "recall_last_set_at")
    op.drop_column("patients", "recall_status")
    op.drop_column("patients", "recall_due_date")
    op.drop_column("patients", "recall_interval_months")
    op.drop_column("patients", "alerts_access")
    op.drop_column("patients", "alerts_financial")
    recall_status = sa.Enum(
        "due",
        "contacted",
        "booked",
        "not_required",
        name="recall_status",
    )
    recall_status.drop(op.get_bind(), checkfirst=True)
