"""Add reusable prescription choices owned by the practice."""
from alembic import op
import sqlalchemy as sa

revision = "0049_prescription_templates"
down_revision = "0048_r4_charting_canonical_content_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prescription_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("medicine", sa.String(500), nullable=False),
        sa.Column("directions", sa.Text(), nullable=False),
        sa.Column("quantity", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
    )


def downgrade() -> None:
    op.drop_table("prescription_templates")
