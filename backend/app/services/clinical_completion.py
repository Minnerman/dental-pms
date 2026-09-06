"""One atomic completion mechanism for old and frozen-workspace plan items.

The caller owns its transaction, status/revision/capability checks and audit.
Neither proposal nor completion changes the recorded diagnosis or makes an invoice.
"""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select

from app.models.clinical import Procedure, ProcedureStatus
from app.models.ledger import LedgerEntryType, PatientLedgerEntry


def complete_plan_item(db, item, user):
    procedure = Procedure(
        patient_id=item.patient_id, appointment_id=item.appointment_id,
        tooth=item.tooth, surface=item.surface, procedure_code=item.procedure_code,
        description=item.description, fee_pence=item.fee_pence,
        status=ProcedureStatus.completed, performed_at=datetime.now(timezone.utc),
        created_by_user_id=user.id,
    )
    db.add(procedure)
    db.flush()
    charge = None
    if item.fee_pence:
        reference = f"TREATMENT-PLAN:{item.id}"
        if db.scalar(select(PatientLedgerEntry.id).where(
            PatientLedgerEntry.patient_id == item.patient_id,
            PatientLedgerEntry.reference == reference,
        )) is not None:
            raise HTTPException(409, "Treatment plan charge already exists")
        charge = PatientLedgerEntry(
            patient_id=item.patient_id, entry_type=LedgerEntryType.charge,
            amount_pence=item.fee_pence, reference=reference,
            note=f"Completed treatment plan item {item.id}",
            created_by_user_id=user.id, updated_by_user_id=user.id,
        )
        db.add(charge)
        db.flush()
    return procedure, charge
