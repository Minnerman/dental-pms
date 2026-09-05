"""Add independent native crown observations sharing the tooth revision.

Revision ID: 0053_crown_observation
Revises: 0052_root_observations

SQL NULL means no native crown override, not a healthy crown. Explicit neutral
resets are non-null objects and must be protected from destructive downgrade.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0053_crown_observation"
down_revision = "0052_root_observations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tooth_conditions", sa.Column(
        "crown_observation", postgresql.JSONB(none_as_null=True), nullable=True,
    ))
    op.create_check_constraint(
        "ck_tooth_conditions_crown_object", "tooth_conditions",
        "crown_observation IS NULL OR jsonb_typeof(crown_observation) = 'object'",
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text(
        "SELECT EXISTS (SELECT 1 FROM tooth_conditions WHERE crown_observation IS NOT NULL)"
    )):
        raise RuntimeError(
            "Cannot downgrade: native crown observations exist, including explicit resets. "
            "Keep this schema and compatible application code; no observations were changed."
        )
    op.drop_constraint("ck_tooth_conditions_crown_object", "tooth_conditions", type_="check")
    op.drop_column("tooth_conditions", "crown_observation")
