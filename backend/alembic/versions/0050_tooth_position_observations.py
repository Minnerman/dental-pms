"""Add independent native tooth movement and rotation observations.

Revision ID: 0050_tooth_position_observations
Revises: 0049_native_tooth_conditions

Existing records retain null (not recorded) values. No inferred clinical state,
R4 data or treatment/finance records are changed. Downgrading loses only these
two new observation attributes; condition, revision and audit history remain.
"""

from alembic import op
import sqlalchemy as sa

revision = "0050_tooth_position_observations"
down_revision = "0049_native_tooth_conditions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tooth_conditions", sa.Column("movement", sa.String(20), nullable=True))
    op.add_column("tooth_conditions", sa.Column("rotation", sa.String(20), nullable=True))
    op.create_check_constraint("ck_tooth_conditions_movement", "tooth_conditions",
                               "movement IS NULL OR movement IN ('forward', 'backward')")
    op.create_check_constraint("ck_tooth_conditions_rotation", "tooth_conditions",
                               "rotation IS NULL OR rotation IN ('clockwise', 'anticlockwise')")


def downgrade() -> None:
    op.drop_constraint("ck_tooth_conditions_rotation", "tooth_conditions", type_="check")
    op.drop_constraint("ck_tooth_conditions_movement", "tooth_conditions", type_="check")
    op.drop_column("tooth_conditions", "rotation")
    op.drop_column("tooth_conditions", "movement")
