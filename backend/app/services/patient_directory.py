"""Bounded, read-only directory over native PMS records, never the R4 source.

Project only directory fields. Inaccessible domains are not queried and cannot
be used to filter or order otherwise visible patient identities.
"""

import re
from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import DateTime, Integer, func, literal, or_, select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.models.ledger import PatientLedgerEntry
from app.models.patient import Patient, PatientCategory
from app.schemas.patient_directory import (
    DirectoryDirection, DirectoryMetadata, DirectoryPatient, DirectorySort,
    DirectoryStatus, PatientDirectory,
)

DEFINITIONS = {
    "balance_pence": "GBP pence: sum of all native patient ledger entries, matching finance summary. Positive is debt, negative is credit; not an overdue-invoice calculation.",
    "last_visit_at": "Latest native completed, non-deleted appointment start at or before now, including clinic and home visits. Cancelled, future and other appointment statuses are excluded.",
    "status": "Active means not archived; archived means deleted_at is set. All includes both.",
    "joined": "Patient record creation date, not a historical registration date inferred from legacy data.",
    "sorting": "Names are case-insensitive with the other name as a secondary sort; remaining ties use ascending patient ID. Missing last visits always sort last.",
    "do_not_contact": "Unavailable: a general patient do-not-contact preference is not recorded. No inference from recalls or missing contact details.",
}


def _contains(value: str) -> str:
    # User searches are literal substrings, not SQL LIKE wildcard expressions.
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def build_patient_directory(
    db: Session,
    capabilities: set[str],
    *,
    query: str | None = None,
    email: str | None = None,
    dob: date | None = None,
    category: PatientCategory | None = None,
    status: DirectoryStatus = "active",
    sort: DirectorySort = "last_name",
    direction: DirectoryDirection = "asc",
    with_debt: bool = False,
    limit: int = 50,
    offset: int = 0,
    now: datetime | None = None,
) -> PatientDirectory:
    if "patients.view" not in capabilities:
        raise HTTPException(status_code=403, detail="Missing capability: patients.view")
    finance_allowed = "billing.view" in capabilities
    visits_allowed = "appointments.view" in capabilities
    if with_debt and not finance_allowed:
        raise HTTPException(status_code=403, detail="Debt filtering requires billing.view")
    if sort == "last_visit" and not visits_allowed:
        raise HTTPException(status_code=403, detail="Last-visit sorting requires appointments.view")

    balance = literal(None, type_=Integer)
    last_visit = literal(None, type_=DateTime(timezone=True))
    ledger = None
    visits = None
    ledger_totals = None
    visit_totals = None
    if finance_allowed:
        ledger_totals = select(
            PatientLedgerEntry.patient_id,
            func.sum(PatientLedgerEntry.amount_pence).label("balance_pence"),
        ).group_by(PatientLedgerEntry.patient_id)
        # Only a debt filter needs balances before pagination. Otherwise enrich
        # the selected IDs below instead of aggregating the entire ledger.
        if with_debt:
            ledger = ledger_totals.subquery()
            balance = func.coalesce(ledger.c.balance_pence, 0)
    if visits_allowed:
        visit_totals = select(
            Appointment.patient_id,
            func.max(Appointment.starts_at).label("last_visit_at"),
        ).where(
            Appointment.deleted_at.is_(None),
            Appointment.status == AppointmentStatus.completed,
            Appointment.starts_at <= (now or datetime.now(timezone.utc)),
            Appointment.patient_id.is_not(None),
        ).group_by(Appointment.patient_id)
        if sort == "last_visit":
            visits = visit_totals.subquery()
            last_visit = visits.c.last_visit_at

    statement = select(
        Patient.id, Patient.first_name, Patient.last_name, Patient.phone,
        Patient.date_of_birth, Patient.patient_category, Patient.created_at,
        Patient.updated_at, Patient.deleted_at,
        balance.label("balance_pence"), last_visit.label("last_visit_at"),
    ).select_from(Patient)
    if ledger is not None:
        statement = statement.outerjoin(ledger, ledger.c.patient_id == Patient.id)
    if visits is not None:
        statement = statement.outerjoin(visits, visits.c.patient_id == Patient.id)
    if status == "active":
        statement = statement.where(Patient.deleted_at.is_(None))
    elif status == "archived":
        statement = statement.where(Patient.deleted_at.is_not(None))

    search = " ".join((query or "").split())
    if search:
        like = _contains(search)
        # Collapse whitespace in both entered and stored full names, and accept
        # either name order without fetching all records for client-side search.
        forward = func.regexp_replace(Patient.first_name + " " + Patient.last_name, "[[:space:]]+", " ", "g")
        reverse = func.regexp_replace(Patient.last_name + " " + Patient.first_name, "[[:space:]]+", " ", "g")
        matches = [column.ilike(like, escape="\\") for column in (
            Patient.first_name, Patient.last_name, forward, reverse, Patient.email, Patient.phone,
        )]
        if re.fullmatch(r"[\d\s+().-]+", search):
            digits = re.sub(r"\D", "", search)
            if digits:
                normalized_phone = func.regexp_replace(func.coalesce(Patient.phone, ""), "[^0-9]", "", "g")
                matches.append(normalized_phone.like(_contains(digits), escape="\\"))
        statement = statement.where(or_(*matches))
    if email and email.strip():
        statement = statement.where(Patient.email.ilike(_contains(email.strip()), escape="\\"))
    if dob is not None:
        statement = statement.where(Patient.date_of_birth == dob)
    if category is not None:
        statement = statement.where(Patient.patient_category == category)
    if with_debt:
        statement = statement.where(balance > 0)

    sort_columns = {
        "last_name": (func.lower(Patient.last_name), func.lower(Patient.first_name)),
        "first_name": (func.lower(Patient.first_name), func.lower(Patient.last_name)),
        "joined": (Patient.created_at,),
        "recently_edited": (Patient.updated_at,),
        "last_visit": (last_visit,),
    }[sort]
    ordering = [
        (column.desc() if direction == "desc" else column.asc()).nullslast()
        for column in sort_columns
    ]
    total = int(db.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = [dict(row) for row in db.execute(
        statement.order_by(*ordering, Patient.id.asc()).limit(limit).offset(offset)
    ).mappings()]
    page_ids = [row["id"] for row in rows]
    if page_ids and ledger_totals is not None and not with_debt:
        page_balances = dict(db.execute(ledger_totals.where(
            PatientLedgerEntry.patient_id.in_(page_ids)
        )).all())
        for row in rows:
            row["balance_pence"] = int(page_balances.get(row["id"], 0))
    if page_ids and visit_totals is not None and sort != "last_visit":
        page_visits = dict(db.execute(visit_totals.where(
            Appointment.patient_id.in_(page_ids)
        )).all())
        for row in rows:
            row["last_visit_at"] = page_visits.get(row["id"])
    return PatientDirectory(
        items=[DirectoryPatient(**row) for row in rows], total=total, limit=limit, offset=offset,
        metadata=DirectoryMetadata(
            finance="available" if finance_allowed else "forbidden",
            last_visit="available" if visits_allowed else "forbidden",
        ), definitions=DEFINITIONS,
    )
