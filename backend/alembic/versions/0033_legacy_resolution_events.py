"""add legacy resolution events

Revision ID: 0033_legacy_resolution_events
Revises: 0032_legacy_appointment_patient_code
Create Date: 2026-01-18 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0033_legacy_resolution_events"
down_revision = "0032_legacy_appointment_patient_code"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legacy_resolution_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("legacy_source", sa.String(length=120), nullable=True),
        sa.Column("legacy_id", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("from_patient_id", sa.Integer(), nullable=True),
        sa.Column("to_patient_id", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("legacy_resolution_events")
