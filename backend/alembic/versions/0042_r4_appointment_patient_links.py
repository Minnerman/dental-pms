"""Add R4 appointment patient links

Revision ID: 0042_r4_appointment_patient_links
Revises: 0041_r4_appointments
Create Date: 2026-01-23 13:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0042_r4_appointment_patient_links"
down_revision = "0041_r4_appointments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "r4_appointment_patient_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("legacy_source", sa.String(length=120), nullable=False, server_default="r4"),
        sa.Column("legacy_appointment_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("linked_by_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "linked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["linked_by_user_id"], ["users.id"]),
        sa.UniqueConstraint(
            "legacy_source",
            "legacy_appointment_id",
            name="uq_r4_appointment_patient_links_legacy_key",
        ),
    )
    op.create_index(
        "ix_r4_appointment_patient_links_patient_id",
        "r4_appointment_patient_links",
        ["patient_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_r4_appointment_patient_links_patient_id",
        table_name="r4_appointment_patient_links",
    )
    op.drop_table("r4_appointment_patient_links")
