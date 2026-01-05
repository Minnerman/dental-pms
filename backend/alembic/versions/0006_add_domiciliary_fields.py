"""add domiciliary fields

Revision ID: 0006_add_domiciliary_fields
Revises: 0005_add_appointment_fields
Create Date: 2026-01-05 23:30:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_add_domiciliary_fields"
down_revision = "0005_add_appointment_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "appointments",
        sa.Column(
            "is_domiciliary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "appointments",
        sa.Column("visit_address", sa.Text(), nullable=True),
    )
    op.execute("UPDATE appointments SET is_domiciliary = false WHERE is_domiciliary IS NULL")


def downgrade() -> None:
    op.drop_column("appointments", "visit_address")
    op.drop_column("appointments", "is_domiciliary")
