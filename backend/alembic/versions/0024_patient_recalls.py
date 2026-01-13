"""add patient recalls

Revision ID: 0024_patient_recalls
Revises: 0023_patient_bpe
Create Date: 2026-01-14 09:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0024_patient_recalls"
down_revision = "0023_patient_bpe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("patient_recalls"):
        return

    recall_kind = postgresql.ENUM(
        "exam",
        "hygiene",
        "perio",
        "implant",
        "custom",
        name="patient_recall_kind",
        create_type=False,
    )
    recall_kind.create(bind, checkfirst=True)
    recall_status = postgresql.ENUM(
        "upcoming",
        "due",
        "overdue",
        "completed",
        "cancelled",
        name="patient_recall_status",
        create_type=False,
    )
    recall_status.create(bind, checkfirst=True)

    op.create_table(
        "patient_recalls",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("kind", recall_kind, nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", recall_status, nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
    )
    op.create_index("ix_patient_recalls_patient_id", "patient_recalls", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_patient_recalls_patient_id", table_name="patient_recalls")
    op.drop_table("patient_recalls")
    recall_status = postgresql.ENUM(
        "upcoming",
        "due",
        "overdue",
        "completed",
        "cancelled",
        name="patient_recall_status",
        create_type=False,
    )
    recall_status.drop(op.get_bind(), checkfirst=True)
    recall_kind = postgresql.ENUM(
        "exam",
        "hygiene",
        "perio",
        "implant",
        "custom",
        name="patient_recall_kind",
        create_type=False,
    )
    recall_kind.drop(op.get_bind(), checkfirst=True)
