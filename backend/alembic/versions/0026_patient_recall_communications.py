"""add patient recall communications

Revision ID: 0026_patient_recall_communications
Revises: 0025_patient_recall_outcome
Create Date: 2026-01-14 12:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0026_patient_recall_communications"
down_revision = "0025_patient_recall_outcome"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("patient_recall_communications"):
        return

    channel_enum = postgresql.ENUM(
        "letter",
        "phone",
        "email",
        "sms",
        name="patient_recall_comm_channel",
        create_type=False,
    )
    direction_enum = postgresql.ENUM(
        "outbound",
        name="patient_recall_comm_direction",
        create_type=False,
    )
    status_enum = postgresql.ENUM(
        "draft",
        "sent",
        "failed",
        name="patient_recall_comm_status",
        create_type=False,
    )
    channel_enum.create(bind, checkfirst=True)
    direction_enum.create(bind, checkfirst=True)
    status_enum.create(bind, checkfirst=True)

    op.create_table(
        "patient_recall_communications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("recall_id", sa.Integer(), nullable=False),
        sa.Column("channel", channel_enum, nullable=False),
        sa.Column("direction", direction_enum, nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["recall_id"], ["patient_recalls.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
    )
    op.create_index(
        "ix_patient_recall_communications_patient_id",
        "patient_recall_communications",
        ["patient_id"],
    )
    op.create_index(
        "ix_patient_recall_communications_recall_id",
        "patient_recall_communications",
        ["recall_id"],
    )
    op.create_index(
        "ix_patient_recall_communications_created_at",
        "patient_recall_communications",
        ["created_at"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("patient_recall_communications"):
        op.drop_index(
            "ix_patient_recall_communications_created_at",
            table_name="patient_recall_communications",
        )
        op.drop_index(
            "ix_patient_recall_communications_recall_id",
            table_name="patient_recall_communications",
        )
        op.drop_index(
            "ix_patient_recall_communications_patient_id",
            table_name="patient_recall_communications",
        )
        op.drop_table("patient_recall_communications")

    channel_enum = postgresql.ENUM(
        "letter",
        "phone",
        "email",
        "sms",
        name="patient_recall_comm_channel",
        create_type=False,
    )
    direction_enum = postgresql.ENUM(
        "outbound",
        name="patient_recall_comm_direction",
        create_type=False,
    )
    status_enum = postgresql.ENUM(
        "draft",
        "sent",
        "failed",
        name="patient_recall_comm_status",
        create_type=False,
    )
    status_enum.drop(bind, checkfirst=True)
    direction_enum.drop(bind, checkfirst=True)
    channel_enum.drop(bind, checkfirst=True)
