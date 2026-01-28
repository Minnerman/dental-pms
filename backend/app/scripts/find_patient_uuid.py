from __future__ import annotations

import argparse
from datetime import date

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.patient import Patient


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    year, month, day = map(int, value.split("-"))
    return date(year, month, day)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find patient UUIDs from demographics (case-insensitive)."
    )
    parser.add_argument("--first", required=True, help="First name (case-insensitive).")
    parser.add_argument("--last", required=True, help="Last name (case-insensitive).")
    parser.add_argument("--dob", help="Date of birth (YYYY-MM-DD).")
    parser.add_argument("--postcode", help="Postcode (substring match).")
    parser.add_argument("--email", help="Email (substring match).")
    parser.add_argument("--phone", help="Phone (substring match).")
    parser.add_argument("--limit", type=int, default=20, help="Max rows to return.")
    args = parser.parse_args()

    dob = _parse_date(args.dob)

    stmt = select(Patient).where(
        Patient.first_name.ilike(args.first),
        Patient.last_name.ilike(args.last),
    )
    if dob:
        stmt = stmt.where(Patient.date_of_birth == dob)
    if args.postcode:
        stmt = stmt.where(Patient.postcode.ilike(f"%{args.postcode}%"))
    if args.email:
        stmt = stmt.where(Patient.email.ilike(f"%{args.email}%"))
    if args.phone:
        stmt = stmt.where(Patient.phone.ilike(f"%{args.phone}%"))
    stmt = stmt.limit(args.limit)

    session = SessionLocal()
    try:
        rows = session.scalars(stmt).all()
    finally:
        session.close()

    print(f"Matches: {len(rows)}")
    for patient in rows:
        print(
            patient.id,
            patient.first_name,
            patient.last_name,
            patient.date_of_birth,
            patient.legacy_source,
            patient.legacy_id,
            patient.phone,
            patient.email,
            patient.postcode,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
