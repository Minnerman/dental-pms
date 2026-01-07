from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.appointment import Appointment
from app.models.clinical import Procedure, ProcedureStatus, ToothNote, TreatmentPlanItem
from app.models.patient import Patient
from app.models.user import User
from app.schemas.clinical import (
    ClinicalSummaryOut,
    ProcedureCreate,
    ProcedureOut,
    ToothHistoryOut,
    ToothNoteCreate,
    ToothNoteOut,
    TreatmentPlanItemCreate,
    TreatmentPlanItemOut,
    TreatmentPlanItemUpdate,
)

patient_router = APIRouter(prefix="/patients/{patient_id}", tags=["clinical"])
router = APIRouter(prefix="/treatment-plan", tags=["clinical"])


def get_patient_or_404(db: Session, patient_id: int) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


def validate_appointment(db: Session, patient_id: int, appointment_id: int | None) -> None:
    if appointment_id is None:
        return
    appointment = db.get(Appointment, appointment_id)
    if not appointment or appointment.patient_id != patient_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment does not match patient",
        )


@patient_router.get("/clinical/summary", response_model=ClinicalSummaryOut)
def get_clinical_summary(
    patient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=200),
):
    get_patient_or_404(db, patient_id)
    notes = list(
        db.scalars(
            select(ToothNote)
            .where(ToothNote.patient_id == patient_id)
            .order_by(ToothNote.created_at.desc())
            .limit(limit)
        )
    )
    procedures = list(
        db.scalars(
            select(Procedure)
            .where(Procedure.patient_id == patient_id)
            .order_by(Procedure.performed_at.desc())
            .limit(limit)
        )
    )
    plan_items = list(
        db.scalars(
            select(TreatmentPlanItem)
            .where(TreatmentPlanItem.patient_id == patient_id)
            .order_by(TreatmentPlanItem.created_at.desc())
        )
    )
    return ClinicalSummaryOut(
        recent_tooth_notes=notes,
        recent_procedures=procedures,
        treatment_plan_items=plan_items,
    )


@patient_router.get("/tooth-history", response_model=ToothHistoryOut)
def get_tooth_history(
    patient_id: int,
    tooth: str = Query(min_length=1),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    get_patient_or_404(db, patient_id)
    notes = list(
        db.scalars(
            select(ToothNote)
            .where(ToothNote.patient_id == patient_id, ToothNote.tooth == tooth)
            .order_by(ToothNote.created_at.desc())
        )
    )
    procedures = list(
        db.scalars(
            select(Procedure)
            .where(Procedure.patient_id == patient_id, Procedure.tooth == tooth)
            .order_by(Procedure.performed_at.desc())
        )
    )
    return ToothHistoryOut(notes=notes, procedures=procedures)


@patient_router.post("/tooth-notes", response_model=ToothNoteOut, status_code=status.HTTP_201_CREATED)
def create_tooth_note(
    patient_id: int,
    payload: ToothNoteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_patient_or_404(db, patient_id)
    note = ToothNote(
        patient_id=patient_id,
        tooth=payload.tooth,
        surface=payload.surface,
        note=payload.note,
        created_by_user_id=user.id,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@patient_router.post("/procedures", response_model=ProcedureOut, status_code=status.HTTP_201_CREATED)
def create_procedure(
    patient_id: int,
    payload: ProcedureCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_patient_or_404(db, patient_id)
    validate_appointment(db, patient_id, payload.appointment_id)
    performed_at = payload.performed_at or datetime.now(timezone.utc)
    procedure = Procedure(
        patient_id=patient_id,
        appointment_id=payload.appointment_id,
        tooth=payload.tooth,
        surface=payload.surface,
        procedure_code=payload.procedure_code,
        description=payload.description,
        fee_pence=payload.fee_pence,
        status=ProcedureStatus.completed,
        performed_at=performed_at,
        created_by_user_id=user.id,
    )
    db.add(procedure)
    db.commit()
    db.refresh(procedure)
    return procedure


@patient_router.post(
    "/treatment-plan", response_model=TreatmentPlanItemOut, status_code=status.HTTP_201_CREATED
)
def create_treatment_plan_item(
    patient_id: int,
    payload: TreatmentPlanItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_patient_or_404(db, patient_id)
    validate_appointment(db, patient_id, payload.appointment_id)
    item = TreatmentPlanItem(
        patient_id=patient_id,
        appointment_id=payload.appointment_id,
        tooth=payload.tooth,
        surface=payload.surface,
        procedure_code=payload.procedure_code,
        description=payload.description,
        fee_pence=payload.fee_pence,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{item_id}", response_model=TreatmentPlanItemOut)
def update_treatment_plan_item(
    item_id: int,
    payload: TreatmentPlanItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.get(TreatmentPlanItem, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Treatment plan item not found"
        )
    if payload.appointment_id is not None:
        validate_appointment(db, item.patient_id, payload.appointment_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    item.updated_by_user_id = user.id
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
