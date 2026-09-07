"""Add optional labelled contact numbers without classifying legacy numbers.

Revision ID: 0057_labelled_patient_phones
Revises: 0056_independent_dentition

All new fields start NULL. Existing primary/contact/referral phone values,
patient metadata and audit history remain unchanged.
"""

from alembic import op
import sqlalchemy as sa

revision = "0057_labelled_patient_phones"
down_revision = "0056_independent_dentition"
branch_labels = None
depends_on = None

CONTACT_COLUMNS = {
    "phone_label": 120,
    "home_phone": 50,
    "home_phone_label": 120,
    "work_phone": 50,
    "work_phone_label": 120,
    "mobile_phone": 50,
    "mobile_phone_label": 120,
}


def upgrade() -> None:
    for name, length in CONTACT_COLUMNS.items():
        op.add_column("patients", sa.Column(name, sa.String(length), nullable=True))


def downgrade() -> None:
    populated = " OR ".join(f"{name} IS NOT NULL" for name in CONTACT_COLUMNS)
    if op.get_bind().scalar(sa.text(f"SELECT EXISTS (SELECT 1 FROM patients WHERE {populated})")):
        raise RuntimeError(
            "Cannot downgrade: labelled patient contact data exists. Keep this schema "
            "and compatible application code; no patient records were changed."
        )
    for name in reversed(CONTACT_COLUMNS):
        op.drop_column("patients", name)
