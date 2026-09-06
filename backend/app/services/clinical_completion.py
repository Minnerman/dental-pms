"""One atomic completion mechanism for old and frozen-workspace plan items.

The caller owns its transaction, status/revision/capability checks and audit.
Neither proposal nor completion changes the recorded diagnosis or makes an invoice.
"""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select

from app.models.clinical import Procedure, ProcedureStatus
from app.models.ledger import LedgerEntryType, PatientLedgerEntry
from app.models.treatment_planning import TreatmentPlanCompletion, TreatmentPlanCompletionReversal


def completion_reference(item_id, cycle):
    return f"TREATMENT-PLAN:{item_id}" + (f":C{cycle}" if cycle > 1 else "")


def complete_plan_item(db, item, user, *, previous_status=None):
    cycle = None
    if item.plan_id is not None:
        if previous_status is None or previous_status.value not in {"proposed", "accepted"}:
            raise HTTPException(409, "The earlier planning status needs review")
        previous = db.scalar(select(TreatmentPlanCompletion).where(
            TreatmentPlanCompletion.item_id == item.id).order_by(TreatmentPlanCompletion.cycle.desc()).limit(1))
        if previous is not None and db.scalar(select(TreatmentPlanCompletionReversal.id).where(
            TreatmentPlanCompletionReversal.completion_id == previous.id)) is None:
            raise HTTPException(409, "An earlier completion has not been reversed")
        cycle = (previous.cycle if previous is not None else 0) + 1
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
        reference = completion_reference(item.id, cycle or 1)
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
    if cycle is not None:
        db.add(TreatmentPlanCompletion(item_id=item.id, cycle=cycle,
            previous_status=previous_status.value, procedure_id=procedure.id,
            charge_id=charge.id if charge is not None else None))
        db.flush()
    return procedure, charge
