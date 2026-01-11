from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.practice_profile import PracticeProfile
from app.services.pdf import CLINIC_ADDRESS_LINES, CLINIC_NAME, CLINIC_PHONE


def default_profile() -> dict[str, str | None]:
    address_line1 = CLINIC_ADDRESS_LINES[0] if CLINIC_ADDRESS_LINES else ""
    address_line2 = CLINIC_ADDRESS_LINES[1] if len(CLINIC_ADDRESS_LINES) > 1 else ""
    website = CLINIC_ADDRESS_LINES[1] if len(CLINIC_ADDRESS_LINES) > 1 else ""
    return {
        "name": CLINIC_NAME,
        "address_line1": address_line1,
        "address_line2": address_line2,
        "city": "",
        "postcode": "",
        "phone": CLINIC_PHONE.replace("Tel: ", ""),
        "website": website,
        "email": "",
    }


def load_profile(db: Session) -> dict[str, str | None]:
    profile = db.scalar(select(PracticeProfile).limit(1))
    defaults = default_profile()
    if not profile:
        return defaults
    return {
        "name": profile.name or defaults["name"],
        "address_line1": profile.address_line1 or defaults["address_line1"],
        "address_line2": profile.address_line2 or defaults["address_line2"],
        "city": profile.city or defaults["city"],
        "postcode": profile.postcode or defaults["postcode"],
        "phone": profile.phone or defaults["phone"],
        "website": profile.website or defaults["website"],
        "email": profile.email or defaults["email"],
    }
