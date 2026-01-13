"""add patient recall outcome and linked appointment

Revision ID: 0025_patient_recall_outcome
Revises: 0024_patient_recalls
Create Date: 2026-01-14 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0025_patient_recall_outcome"
down_revision = "0024_patient_recalls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("patient_recalls"):
        return

    outcome_enum = postgresql.ENUM(
        "attended",
        "dna",
        "cancelled",
        "rebooked",
        name="patient_recall_outcome",
        create_type=False,
    )
    outcome_enum.create(bind, checkfirst=True)

    columns = {column["name"] for column in inspector.get_columns("patient_recalls")}
    if "outcome" not in columns:
        op.add_column(
            "patient_recalls",
            sa.Column("outcome", outcome_enum, nullable=True),
        )
    if "linked_appointment_id" not in columns:
        op.add_column(
            "patient_recalls",
            sa.Column("linked_appointment_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_patient_recalls_linked_appointment_id",
            "patient_recalls",
            "appointments",
            ["linked_appointment_id"],
            ["id"],
        )
        op.create_index(
            "ix_patient_recalls_linked_appointment_id",
            "patient_recalls",
            ["linked_appointment_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("patient_recalls"):
        return
    columns = {column["name"] for column in inspector.get_columns("patient_recalls")}
    if "linked_appointment_id" in columns:
        op.drop_index(
            "ix_patient_recalls_linked_appointment_id", table_name="patient_recalls"
        )
        op.drop_constraint(
            "fk_patient_recalls_linked_appointment_id",
            "patient_recalls",
            type_="foreignkey",
        )
        op.drop_column("patient_recalls", "linked_appointment_id")
    if "outcome" in columns:
        op.drop_column("patient_recalls", "outcome")
    outcome_enum = postgresql.ENUM(
        "attended",
        "dna",
        "cancelled",
        "rebooked",
        name="patient_recall_outcome",
        create_type=False,
    )
    outcome_enum.drop(bind, checkfirst=True)
