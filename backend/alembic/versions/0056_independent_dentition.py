"""Preserve explicit native dentition independently from tooth status.

Revision ID: 0056_independent_dentition
Revises: 0055_surface_observations

Only the existing explicit native deciduous condition is copied. No age,
historical records or inferred biological facts are used. Revisions, actors and
audit history remain unchanged by this lossless representation migration.
"""

from alembic import op
import sqlalchemy as sa

revision = "0056_independent_dentition"
down_revision = "0055_surface_observations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tooth_conditions", sa.Column("dentition", sa.String(9), nullable=True))
    op.execute("UPDATE tooth_conditions SET dentition = 'deciduous' WHERE condition = 'deciduous'")
    op.create_check_constraint("ck_tooth_conditions_dentition", "tooth_conditions",
        "dentition IS NULL OR dentition IN ('permanent', 'deciduous')")
    op.create_check_constraint("ck_tooth_conditions_deciduous_position", "tooth_conditions",
        "dentition IS DISTINCT FROM 'deciduous' OR right(tooth, 1) IN ('1', '2', '3', '4', '5')")


def downgrade() -> None:
    # The old schema retains identity only in condition='deciduous'. Never drop
    # independent identity attached to another status, including explicit
    # permanent identity; a default permanent-shaped glyph is not equivalent.
    if op.get_bind().scalar(sa.text(
        "SELECT EXISTS (SELECT 1 FROM tooth_conditions WHERE dentition IS NOT NULL "
        "AND NOT (dentition = 'deciduous' AND condition IS NOT DISTINCT FROM 'deciduous'))"
    )):
        raise RuntimeError(
            "Cannot downgrade: independent native dentition exists. Keep this schema and "
            "compatible application code; no observations were changed."
        )
    op.drop_constraint("ck_tooth_conditions_deciduous_position", "tooth_conditions", type_="check")
    op.drop_constraint("ck_tooth_conditions_dentition", "tooth_conditions", type_="check")
    op.drop_column("tooth_conditions", "dentition")
