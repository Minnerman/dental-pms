"""Allow an explicit neutral current-tooth observation without deleting history.

Revision ID: 0051_unrecorded_tooth_condition
Revises: 0050_tooth_position_observations

Null still means no native override, so legacy information may supply the display.
The explicit unrecorded value suppresses that fallback after a deliberate reset;
it does not assert the tooth is healthy/present. No records are backfilled.
"""

from alembic import op
import sqlalchemy as sa

revision = "0051_unrecorded_tooth_condition"
down_revision = "0050_tooth_position_observations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_tooth_conditions_value", "tooth_conditions", type_="check")
    op.create_check_constraint(
        "ck_tooth_conditions_value", "tooth_conditions",
        "condition IS NULL OR condition IN "
        "('present', 'missing', 'deciduous', 'implant', 'unerupted', 'impacted', 'unrecorded')",
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text(
        "SELECT EXISTS (SELECT 1 FROM tooth_conditions WHERE condition = 'unrecorded')"
    )):
        raise RuntimeError(
            "Cannot downgrade: explicit unrecorded tooth observations exist. "
            "Keep this schema and use compatible application code; no observations were changed."
        )
    op.drop_constraint("ck_tooth_conditions_value", "tooth_conditions", type_="check")
    op.create_check_constraint(
        "ck_tooth_conditions_value", "tooth_conditions",
        "condition IS NULL OR condition IN "
        "('present', 'missing', 'deciduous', 'implant', 'unerupted', 'impacted')",
    )
