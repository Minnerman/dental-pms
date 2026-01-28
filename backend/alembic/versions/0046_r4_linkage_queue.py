"""R4 linkage remediation queue tables.

Revision ID: 0046_r4_linkage_queue
Revises: 0045_r4_charting_filter_indexes
Create Date: 2026-01-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0046_r4_linkage_queue"
down_revision = "0045_r4_charting_filter_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "r4_linkage_issues",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("legacy_source", sa.String(length=120), nullable=False),
        sa.Column("legacy_id", sa.String(length=255), nullable=False),
        sa.Column("patient_code", sa.Integer(), nullable=True),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        sa.Column("details_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'open'"), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "legacy_source",
            "entity_type",
            "legacy_id",
            name="uq_r4_linkage_issues_legacy_key",
        ),
    )
    op.create_index(
        "ix_r4_linkage_issues_status",
        "r4_linkage_issues",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_r4_linkage_issues_reason_code",
        "r4_linkage_issues",
        ["reason_code"],
        unique=False,
    )

    op.create_table(
        "r4_manual_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("legacy_source", sa.String(length=120), nullable=False),
        sa.Column("legacy_patient_code", sa.Integer(), nullable=True),
        sa.Column("legacy_person_key", sa.String(length=255), nullable=True),
        sa.Column("target_patient_id", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "legacy_patient_code IS NOT NULL OR legacy_person_key IS NOT NULL",
            name="r4_manual_mappings_has_legacy_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_r4_manual_mappings_source_patient_code",
        "r4_manual_mappings",
        ["legacy_source", "legacy_patient_code"],
        unique=True,
    )
    op.create_index(
        "ix_r4_manual_mappings_source_person_key",
        "r4_manual_mappings",
        ["legacy_source", "legacy_person_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_r4_manual_mappings_source_person_key", table_name="r4_manual_mappings")
    op.drop_index("ix_r4_manual_mappings_source_patient_code", table_name="r4_manual_mappings")
    op.drop_table("r4_manual_mappings")
    op.drop_index("ix_r4_linkage_issues_reason_code", table_name="r4_linkage_issues")
    op.drop_index("ix_r4_linkage_issues_status", table_name="r4_linkage_issues")
    op.drop_table("r4_linkage_issues")
