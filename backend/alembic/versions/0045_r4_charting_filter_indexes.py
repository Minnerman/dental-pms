"""add charting filter indexes

Revision ID: 0045_r4_charting_filter_indexes
Revises: 0044_r4_charting_import_state
Create Date: 2026-01-24 00:00:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "0045_r4_charting_filter_indexes"
down_revision = "0044_r4_charting_import_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_r4_perio_probes_patient_tooth_site",
        "r4_perio_probes",
        ["legacy_source", "legacy_patient_code", "tooth", "probing_point"],
    )
    op.create_index(
        "ix_r4_bpe_furcations_patient_date",
        "r4_bpe_furcations",
        ["legacy_source", "legacy_patient_code", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_r4_bpe_furcations_patient_date", table_name="r4_bpe_furcations")
    op.drop_index("ix_r4_perio_probes_patient_tooth_site", table_name="r4_perio_probes")
