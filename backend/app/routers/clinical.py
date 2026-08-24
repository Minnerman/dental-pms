from datetime import datetime, timezone
from typing import Iterable, TypeVar

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import require_capability
from app.models.appointment import Appointment, AppointmentStatus
from app.models.audit_log import AuditLog
from app.models.clinical import (
    Procedure,
    ProcedureStatus,
    ToothNote,
    TreatmentPlanItem,
    TreatmentPlanStatus,
)
from app.models.patient import Patient
from app.models.user import User
from app.schemas.clinical import (
    BpeOut,
    BpeUpdate,
    ClinicalSummaryOut,
    ProcedureCreate,
    ProcedureOut,
    TOOTH_PATTERN,
    ToothHistoryOut,
    ToothNoteCreate,
    ToothNoteOut,
    TreatmentPlanItemCreate,
    TreatmentPlanItemOut,
    TreatmentPlanItemUpdate,
    validate_tooth_surface,
)
from app.services.audit import log_event

patient_router = APIRouter(prefix="/patients/{patient_id}", tags=["clinical"])
router = APIRouter(prefix="/treatment-plan", tags=["clinical"])

CLINICAL_VIEW = require_capability("clinical.view")
CLINICAL_WRITE = require_capability("clinical.write")
ACTIVE_APPOINTMENT_STATUSES = {
    AppointmentStatus.booked,
    AppointmentStatus.arrived,
    AppointmentStatus.in_progress,
}
PLAN_TRANSITIONS = {
    TreatmentPlanStatus.proposed: {
        TreatmentPlanStatus.accepted,
        TreatmentPlanStatus.declined,
        TreatmentPlanStatus.completed,
        TreatmentPlanStatus.cancelled,
    },
    TreatmentPlanStatus.accepted: {
        TreatmentPlanStatus.completed,
        TreatmentPlanStatus.cancelled,
    },
    TreatmentPlanStatus.declined: set(),
    TreatmentPlanStatus.completed: set(),
    TreatmentPlanStatus.cancelled: set(),
}
T = TypeVar("T", ToothNote, Procedure, TreatmentPlanItem)


def get_patient_or_404(db: Session, patient_id: int, *, for_update: bool = False) -> Patient:
    stmt = select(Patient).where(Patient.id == patient_id, Patient.deleted_at.is_(None))
    if for_update:
        stmt = stmt.with_for_update(of=Patient)
    patient = db.scalar(stmt)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


def validate_appointment(db: Session, patient_id: int, appointment_id: int | None) -> None:
    if appointment_id is None:
        return
    appointment = db.get(Appointment, appointment_id)
    if (
        not appointment
        or appointment.deleted_at is not None
        or appointment.patient_id != patient_id
        or appointment.status not in ACTIVE_APPOINTMENT_STATUSES
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment must be active and belong to the patient",
        )


def split_bpe_scores(scores: str | None) -> list[str] | None:
    if not scores:
        return None
    parts = [part.strip() for part in scores.split(",")]
    if len(parts) < 6:
        parts.extend([""] * (6 - len(parts)))
    return parts[:6]


def _duplicate_audit(
    db: Session,
    *,
    patient_id: int,
    request_id: str | None,
    actions: Iterable[str],
) -> AuditLog | None:
    if not request_id:
        return None
    return db.scalar(
        select(AuditLog)
        .where(
            AuditLog.entity_type == "patient",
            AuditLog.entity_id == str(patient_id),
            AuditLog.request_id == request_id,
            AuditLog.action.in_(list(actions)),
        )
        .order_by(AuditLog.id.desc())
    )


def _duplicate_created_entity(
    db: Session,
    *,
    patient_id: int,
    request_id: str | None,
    action: str,
    model: type[T],
    id_key: str,
) -> T | None:
    audit = _duplicate_audit(
        db, patient_id=patient_id, request_id=request_id, actions=[action]
    )
    entity_id = (audit.after_json or {}).get(id_key) if audit else None
    if not isinstance(entity_id, int):
        return None
    entity = db.get(model, entity_id)
    if entity is None or entity.patient_id != patient_id:
        return None
    return entity


def _safe_plan_values(item: TreatmentPlanItem, fields: set[str]) -> dict:
    values: dict[str, object] = {"treatment_plan_item_id": item.id}
    for field in sorted(fields - {"description"}):
        value = getattr(item, field)
        values[field] = value.value if isinstance(value, TreatmentPlanStatus) else value
    if "description" in fields:
        values["description_changed"] = True
    values["changed_fields"] = sorted(fields)
    return values


@patient_router.get("/clinical/summary", response_model=ClinicalSummaryOut)
def get_clinical_summary(
    patient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(CLINICAL_VIEW),
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
    user: User = Depends(CLINICAL_WRITE),
    request_id: str | None = Header(default=None, max_length=120),
):
    patient = get_patient_or_404(db, patient_id, for_update=True)
    duplicate = _duplicate_audit(
        db,
        patient_id=patient_id,
        request_id=request_id,
        actions=["clinical.bpe.recorded", "clinical.bpe.cleared"],
    )
    if duplicate:
        return BpeOut(
            bpe_scores=split_bpe_scores(patient.bpe_scores),
            bpe_recorded_at=patient.bpe_recorded_at,
        )

    scores = payload.scores
    current_scores = split_bpe_scores(patient.bpe_scores) or [""] * 6
    has_scores = any(scores)
    if scores == current_scores and (
        payload.recorded_at is None or payload.recorded_at == patient.bpe_recorded_at
    ):
        return BpeOut(
            bpe_scores=split_bpe_scores(patient.bpe_scores),
            bpe_recorded_at=patient.bpe_recorded_at,
        )

    before_data = {
        "scores": current_scores if any(current_scores) else None,
        "recorded_at": patient.bpe_recorded_at.isoformat()
        if patient.bpe_recorded_at
        else None,
    }
    if has_scores:
        patient.bpe_scores = ",".join(scores)
        patient.bpe_recorded_at = payload.recorded_at or datetime.now(timezone.utc)
        action = "clinical.bpe.recorded"
    else:
        patient.bpe_scores = None
        patient.bpe_recorded_at = None
        action = "clinical.bpe.cleared"
    after_data = {
        "scores": scores if has_scores else None,
        "recorded_at": patient.bpe_recorded_at.isoformat()
        if patient.bpe_recorded_at
        else None,
    }
    db.add(patient)
    log_event(
        db,
        actor=user,
        action=action,
        entity_type="patient",
        entity_id=str(patient.id),
        request_id=request_id,
        before_data=before_data,
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
    tooth: str = Query(min_length=3, max_length=3, pattern=TOOTH_PATTERN.pattern),
    db: Session = Depends(get_db),
    _user: User = Depends(CLINICAL_VIEW),
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
    user: User = Depends(CLINICAL_WRITE),
    request_id: str | None = Header(default=None, max_length=120),
):
    get_patient_or_404(db, patient_id, for_update=True)
    duplicate = _duplicate_created_entity(
        db,
        patient_id=patient_id,
        request_id=request_id,
        action="clinical.tooth_note.created",
        model=ToothNote,
        id_key="tooth_note_id",
    )
    if duplicate:
        return duplicate
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
        request_id=request_id,
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
    user: User = Depends(CLINICAL_WRITE),
    request_id: str | None = Header(default=None, max_length=120),
):
    get_patient_or_404(db, patient_id, for_update=True)
    duplicate = _duplicate_created_entity(
        db,
        patient_id=patient_id,
        request_id=request_id,
        action="clinical.procedure.completed",
        model=Procedure,
        id_key="procedure_id",
    )
    if duplicate:
        return duplicate
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
    db.flush()
    log_event(
        db,
        actor=user,
        action="clinical.procedure.completed",
        entity_type="patient",
        entity_id=str(patient_id),
        request_id=request_id,
        after_data={
            "procedure_id": procedure.id,
            "appointment_id": procedure.appointment_id,
            "tooth": procedure.tooth,
            "surface": procedure.surface,
            "procedure_code": procedure.procedure_code,
            "fee_pence": procedure.fee_pence,
        },
    )
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
    user: User = Depends(CLINICAL_WRITE),
    request_id: str | None = Header(default=None, max_length=120),
):
    get_patient_or_404(db, patient_id, for_update=True)
    duplicate = _duplicate_created_entity(
        db,
        patient_id=patient_id,
        request_id=request_id,
        action="clinical.treatment_plan.item.created",
        model=TreatmentPlanItem,
        id_key="treatment_plan_item_id",
    )
    if duplicate:
        return duplicate
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
        action="clinical.treatment_plan.item.created",
        entity_type="patient",
        entity_id=str(patient_id),
        request_id=request_id,
        after_data={
            "treatment_plan_item_id": item.id,
            "appointment_id": item.appointment_id,
            "tooth": item.tooth,
            "surface": item.surface,
            "procedure_code": item.procedure_code,
            "fee_pence": item.fee_pence,
            "status": item.status.value,
        },
    )
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{item_id}", response_model=TreatmentPlanItemOut)
def update_treatment_plan_item(
    item_id: int,
    payload: TreatmentPlanItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(CLINICAL_WRITE),
    request_id: str | None = Header(default=None, max_length=120),
):
    item = db.scalar(
        select(TreatmentPlanItem)
        .where(TreatmentPlanItem.id == item_id)
        .with_for_update(of=TreatmentPlanItem)
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Treatment plan item not found"
        )
    get_patient_or_404(db, item.patient_id)
    duplicate = _duplicate_audit(
        db,
        patient_id=item.patient_id,
        request_id=request_id,
        actions=[
            "clinical.treatment_plan.item.updated",
            "clinical.treatment_plan.status.changed",
        ],
    )
    if duplicate and (duplicate.after_json or {}).get("treatment_plan_item_id") == item.id:
        return item

    updates = payload.model_dump(exclude_unset=True)
    merged_tooth = updates.get("tooth", item.tooth)
    merged_surface = updates.get("surface", item.surface)
    try:
        validate_tooth_surface(merged_tooth, merged_surface)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    if "appointment_id" in updates:
        validate_appointment(db, item.patient_id, updates["appointment_id"])

    before_status = item.status
    requested_status = updates.get("status")
    if requested_status is not None and requested_status != before_status:
        if requested_status not in PLAN_TRANSITIONS[before_status]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Treatment plan status transition is not permitted",
            )

    changed_fields = {
        field for field, value in updates.items() if getattr(item, field) != value
    }
    if not changed_fields:
        return item
    non_status_fields = changed_fields - {"status"}
    if non_status_fields and before_status in {
        TreatmentPlanStatus.declined,
        TreatmentPlanStatus.completed,
        TreatmentPlanStatus.cancelled,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Final treatment plan items cannot be edited",
        )

    before_values = _safe_plan_values(item, non_status_fields)
    for field in changed_fields:
        setattr(item, field, updates[field])
    item.updated_by_user_id = user.id
    db.add(item)

    if non_status_fields:
        log_event(
            db,
            actor=user,
            action="clinical.treatment_plan.item.updated",
            entity_type="patient",
            entity_id=str(item.patient_id),
            request_id=request_id,
            before_data=before_values,
            after_data=_safe_plan_values(item, non_status_fields),
        )
    if "status" in changed_fields:
        log_event(
            db,
            actor=user,
            action="clinical.treatment_plan.status.changed",
            entity_type="patient",
            entity_id=str(item.patient_id),
            request_id=request_id,
            before_data={
                "treatment_plan_item_id": item.id,
                "status": before_status.value,
            },
            after_data={
                "treatment_plan_item_id": item.id,
                "status": item.status.value,
            },
        )
    db.commit()
    db.refresh(item)
    return item
