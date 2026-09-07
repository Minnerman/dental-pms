"""Add independent native root observations sharing the tooth revision.

Revision ID: 0052_root_observations
Revises: 0051_unrecorded_tooth_condition

Empty maps mean no native root observations, not healthy roots. Nonempty maps,
including explicit root resets, must never be discarded by a downgrade.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0052_root_observations"
down_revision = "0051_unrecorded_tooth_condition"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tooth_conditions", sa.Column(
        "root_observations", postgresql.JSONB(), nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    ))
    op.create_check_constraint(
        "ck_tooth_conditions_root_keys", "tooth_conditions",
        "jsonb_typeof(root_observations) = 'object' AND "
        "root_observations - '1' - '2' - '3' = '{}'::jsonb",
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text(
        "SELECT EXISTS (SELECT 1 FROM tooth_conditions WHERE root_observations <> '{}'::jsonb)"
    )):
        raise RuntimeError(
            "Cannot downgrade: native root observations exist, including explicit resets. "
            "Keep this schema and compatible application code; no observations were changed."
        )
    op.drop_constraint("ck_tooth_conditions_root_keys", "tooth_conditions", type_="check")
    op.drop_column("tooth_conditions", "root_observations")
