"""add content_hash to r4 charting canonical records

Revision ID: 0048_r4_charting_canonical_content_hash
Revises: 0047_r4_charting_canonical_records
Create Date: 2026-02-01
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0048_r4_charting_canonical_content_hash"
down_revision = "0047_r4_charting_canonical_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "r4_charting_canonical_records",
        sa.Column("content_hash", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("r4_charting_canonical_records", "content_hash")
