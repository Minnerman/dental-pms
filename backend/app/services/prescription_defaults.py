"""Practice-requested favourites, not a prescribing guideline or dose calculator."""
from sqlalchemy import select
from app.models.prescription_template import PrescriptionTemplate

DEFAULTS = [
    ("amoxicillin-250", "Amoxicillin 250 mg capsules", "Take one capsule three times a day.", "21 capsules"),
    ("amoxicillin-500", "Amoxicillin 500 mg capsules", "Take one capsule three times a day.", "21 capsules"),
    ("amoxicillin-liquid-250", "Amoxicillin 250 mg/5 mL oral suspension (sugar free)", "Take 5 mL three times a day.", "100 mL"),
    ("amoxicillin-liquid-500", "Amoxicillin 500 mg/5 mL oral suspension", "Take 5 mL three times a day.", "100 mL"),
    ("metronidazole-200", "Metronidazole 200 mg tablets", "Take one tablet three times a day.", "21 tablets"),
    ("metronidazole-400", "Metronidazole 400 mg tablets", "Take one tablet three times a day.", "21 tablets"),
    ("erythromycin-250", "Erythromycin 250 mg tablets", "Take one tablet four times a day.", "28 tablets"),
    ("clindamycin-150", "Clindamycin 150 mg capsules", "Take one capsule every six hours.", ""),
    ("clindamycin-300", "Clindamycin 300 mg capsules", "Take one capsule every six hours.", ""),
]


def ensure_prescription_defaults(db, *, actor):
    for key, medicine, directions, quantity in DEFAULTS:
        existing = db.scalar(select(PrescriptionTemplate).where(PrescriptionTemplate.stock_key == key))
        if existing:
            # Upgrade only untouched initial liquid favourites. An explicit edit,
            # including choosing a blank supply, must survive future startups.
            if (
                key in {"amoxicillin-liquid-250", "amoxicillin-liquid-500"}
                and existing.updated_by_user_id is None
                and existing.is_active
                and existing.name == medicine
                and existing.medicine == medicine
                and existing.directions == directions
                and existing.quantity == ""
            ):
                existing.quantity = quantity
            continue
        db.add(PrescriptionTemplate(stock_key=key, name=medicine, medicine=medicine,
            directions=directions, quantity=quantity, is_active=True, created_by_user_id=actor.id))
    db.commit()
