"""appointment cancellation fields

Revision ID: 0012_appt_cancel_fields
Revises: 0011_practice_schedule_settings
Create Date: 2026-01-07 18:25:00.000000
"""

from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "0012_appt_cancel_fields"
down_revision = "0011_practice_schedule_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "appointments" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("appointments")}
    if "cancel_reason" not in columns:
        op.add_column("appointments", sa.Column("cancel_reason", sa.Text(), nullable=True))
    if "cancelled_at" not in columns:
        op.add_column(
            "appointments", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True)
        )
    if "cancelled_by_user_id" not in columns:
        op.add_column(
            "appointments",
            sa.Column("cancelled_by_user_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_appointments_cancelled_by_user_id",
            "appointments",
            "users",
            ["cancelled_by_user_id"],
            ["id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "appointments" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("appointments")}
    if "cancelled_by_user_id" in columns:
        op.drop_constraint(
            "fk_appointments_cancelled_by_user_id", "appointments", type_="foreignkey"
        )
        op.drop_column("appointments", "cancelled_by_user_id")
    if "cancelled_at" in columns:
        op.drop_column("appointments", "cancelled_at")
    if "cancel_reason" in columns:
        op.drop_column("appointments", "cancel_reason")
