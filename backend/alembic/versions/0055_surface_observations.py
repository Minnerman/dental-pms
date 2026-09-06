"""Add native current surface observations sharing the tooth revision.

Revision ID: 0055_surface_observations
Revises: 0054_tooth_bridge_groups

Empty maps mean unspecified surfaces. Explicit neutral entries are current
overrides, not healthy findings, and must also be protected from downgrade.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0055_surface_observations"
down_revision = "0054_tooth_bridge_groups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tooth_conditions", sa.Column(
        "surface_observations", postgresql.JSONB(), nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    ))
    op.create_check_constraint(
        "ck_tooth_conditions_surface_keys", "tooth_conditions",
        "jsonb_typeof(surface_observations) = 'object' AND "
        "surface_observations - 'M' - 'O' - 'I' - 'D' - 'B' - 'P' - 'L' = '{}'::jsonb",
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text(
        "SELECT EXISTS (SELECT 1 FROM tooth_conditions WHERE surface_observations <> '{}'::jsonb)"
    )):
        raise RuntimeError(
            "Cannot downgrade: native surface observations exist, including explicit resets. "
            "Keep this schema and compatible application code; no observations were changed."
        )
    op.drop_constraint("ck_tooth_conditions_surface_keys", "tooth_conditions", type_="check")
    op.drop_column("tooth_conditions", "surface_observations")
