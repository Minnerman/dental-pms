"""add r4 charting canonical records

Revision ID: 0047_r4_charting_canonical_records
Revises: 0046_r4_linkage_queue
Create Date: 2026-02-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0047_r4_charting_canonical_records"
down_revision = "0046_r4_linkage_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "r4_charting_canonical_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("unique_key", sa.String(length=300), nullable=False),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("r4_source", sa.String(length=120), nullable=False),
        sa.Column("r4_source_id", sa.String(length=200), nullable=False),
        sa.Column("legacy_patient_code", sa.Integer(), nullable=True),
        sa.Column("patient_id", sa.Integer(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "extracted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("tooth", sa.SmallInteger(), nullable=True),
        sa.Column("surface", sa.SmallInteger(), nullable=True),
        sa.Column("code_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=120), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("unique_key", name="uq_r4_charting_canonical_unique_key"),
    )
    op.create_index(
        "ix_r4_charting_canonical_patient",
        "r4_charting_canonical_records",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        "ix_r4_charting_canonical_domain",
        "r4_charting_canonical_records",
        ["domain"],
        unique=False,
    )
    op.create_index(
        "ix_r4_charting_canonical_source",
        "r4_charting_canonical_records",
        ["r4_source"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_r4_charting_canonical_source", table_name="r4_charting_canonical_records")
    op.drop_index("ix_r4_charting_canonical_domain", table_name="r4_charting_canonical_records")
    op.drop_index("ix_r4_charting_canonical_patient", table_name="r4_charting_canonical_records")
    op.drop_table("r4_charting_canonical_records")
