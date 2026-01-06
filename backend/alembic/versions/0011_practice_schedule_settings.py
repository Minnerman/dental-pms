"""practice schedule settings

Revision ID: 0011_practice_schedule_settings
Revises: 0010_domiciliary_patient_fields
Create Date: 2026-01-06 23:30:00.000000
"""

from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "0011_practice_schedule_settings"
down_revision = "0010_domiciliary_patient_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "practice_hours" not in tables:
        op.create_table(
            "practice_hours",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("day_of_week", sa.Integer(), nullable=False),
            sa.Column("start_time", sa.Time(), nullable=True),
            sa.Column("end_time", sa.Time(), nullable=True),
            sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
        op.create_index(
            "ix_practice_hours_day_of_week", "practice_hours", ["day_of_week"]
        )

    if "practice_closures" not in tables:
        op.create_table(
            "practice_closures",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=False),
            sa.Column("reason", sa.String(length=255), nullable=True),
        )

    if "practice_overrides" not in tables:
        op.create_table(
            "practice_overrides",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("start_time", sa.Time(), nullable=True),
            sa.Column("end_time", sa.Time(), nullable=True),
            sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("reason", sa.String(length=255), nullable=True),
        )
        op.create_index(
            "ix_practice_overrides_date", "practice_overrides", ["date"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "practice_overrides" in tables:
        op.drop_index("ix_practice_overrides_date", table_name="practice_overrides")
        op.drop_table("practice_overrides")
    if "practice_closures" in tables:
        op.drop_table("practice_closures")
    if "practice_hours" in tables:
        op.drop_index("ix_practice_hours_day_of_week", table_name="practice_hours")
        op.drop_table("practice_hours")
