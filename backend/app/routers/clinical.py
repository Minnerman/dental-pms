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
    BpeOut,
    BpeUpdate,
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
from app.services.audit import log_event

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


def split_bpe_scores(scores: str | None) -> list[str] | None:
    if not scores:
        return None
    parts = [part.strip() for part in scores.split(",")]
    if len(parts) < 6:
        parts.extend([""] * (6 - len(parts)))
    return parts[:6]


def normalize_bpe_scores(scores: list[str]) -> list[str]:
    if len(scores) != 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="BPE scores must have 6 values",
        )
    return [score.strip() for score in scores]


@patient_router.get("/clinical/summary", response_model=ClinicalSummaryOut)
def get_clinical_summary(
    patient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=200),
):
    patient = get_patient_or_404(db, patient_id)
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
        bpe_scores=split_bpe_scores(patient.bpe_scores),
        bpe_recorded_at=patient.bpe_recorded_at,
    )


@patient_router.post("/clinical/bpe", response_model=BpeOut)
def update_bpe(
    patient_id: int,
    payload: BpeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    patient = get_patient_or_404(db, patient_id)
    scores = normalize_bpe_scores(payload.scores)
    has_scores = any(score for score in scores)
    if has_scores:
        patient.bpe_scores = ",".join(scores)
        patient.bpe_recorded_at = payload.recorded_at or datetime.now(timezone.utc)
        action = "clinical.bpe.recorded"
        after_data = {"bpe_recorded": True}
    else:
        patient.bpe_scores = None
        patient.bpe_recorded_at = None
        action = "clinical.bpe.cleared"
        after_data = {"bpe_cleared": True}
    db.add(patient)
    log_event(
        db,
        actor=user,
        action=action,
        entity_type="patient",
        entity_id=str(patient.id),
        after_data=after_data,
    )
    db.commit()
    return BpeOut(
        bpe_scores=split_bpe_scores(patient.bpe_scores),
        bpe_recorded_at=patient.bpe_recorded_at,
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
    db.flush()
    log_event(
        db,
        actor=user,
        action="clinical.tooth_note.created",
        entity_type="patient",
        entity_id=str(patient_id),
        after_data={"tooth_note_id": note.id, "tooth": note.tooth, "surface": note.surface},
    )
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
    db.flush()
    log_event(
        db,
        actor=user,
        action="clinical.treatment_plan.added",
        entity_type="patient",
        entity_id=str(patient_id),
        after_data={"treatment_plan_item_id": item.id, "tooth": item.tooth},
    )
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
    before_status = item.status
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    item.updated_by_user_id = user.id
    db.add(item)
    if payload.status is not None and payload.status != before_status:
        log_event(
            db,
            actor=user,
            action=f"clinical.treatment_plan.status: {before_status.value} -> {payload.status.value}",
            entity_type="patient",
            entity_id=str(item.patient_id),
            after_data={"treatment_plan_item_id": item.id, "status": payload.status.value},
        )
    db.commit()
    db.refresh(item)
    return item
