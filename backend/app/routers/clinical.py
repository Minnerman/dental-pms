from datetime import datetime, timezone
from typing import Iterable, TypeVar

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import require_capability
from app.models.appointment import Appointment, AppointmentStatus
from app.models.audit_log import AuditLog
from app.models.capability import Capability, UserCapability
from app.models.clinical import (
    Procedure,
    ProcedureStatus,
    ToothCondition,
    ToothNote,
    TreatmentPlanItem,
    TreatmentPlanStatus,
)
from app.models.ledger import LedgerEntryType, PatientLedgerEntry
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
    ToothConditionsOut,
    ToothConditionUpdate,
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


def _user_has_capability(db: Session, user_id: int, code: str) -> bool:
    return (
        db.scalar(
            select(Capability.id)
            .join(UserCapability, UserCapability.capability_id == Capability.id)
            .where(UserCapability.user_id == user_id, Capability.code == code)
        )
        is not None
    )


def _tooth_conditions_out(db: Session, patient_id: int) -> ToothConditionsOut:
    conditions = db.scalars(
        select(ToothCondition)
        .where(ToothCondition.patient_id == patient_id)
        .order_by(ToothCondition.tooth)
    ).all()
    note_teeth = list(
        db.scalars(
            select(ToothNote.tooth)
            .where(ToothNote.patient_id == patient_id)
            .distinct()
            .order_by(ToothNote.tooth)
        )
    )
    return ToothConditionsOut(
        patient_id=patient_id,
        teeth={condition.tooth: condition for condition in conditions},
        note_teeth=note_teeth,
    )


@patient_router.get("/clinical/tooth-conditions", response_model=ToothConditionsOut)
def get_tooth_conditions(
    patient_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(CLINICAL_VIEW),
):
    get_patient_or_404(db, patient_id)
    return _tooth_conditions_out(db, patient_id)


@patient_router.post("/clinical/tooth-conditions", response_model=ToothConditionsOut)
def update_tooth_conditions(
    patient_id: int,
    payload: ToothConditionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(CLINICAL_WRITE),
    _viewer: User = Depends(CLINICAL_VIEW),
    request_id: str | None = Header(default=None, min_length=1, max_length=120),
):
    # All observations for a patient share this lock, including whole-arch writes
    # and retries. Validate every revision before changing any selected tooth.
    get_patient_or_404(db, patient_id, for_update=True)
    action = "clinical.tooth_conditions.recorded"
    request_values = payload.model_dump(mode="json")
    duplicate = _duplicate_audit(
        db, patient_id=patient_id, request_id=request_id, actions=[action]
    )
    if duplicate:
        if (duplicate.after_json or {}).get("request") != request_values:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Request-Id was already used for a different tooth-condition update",
            )
        # Return the latest state, without replaying old values over newer edits.
        return _tooth_conditions_out(db, patient_id)

    existing = {
        row.tooth: row
        for row in db.scalars(
            select(ToothCondition).where(
                ToothCondition.patient_id == patient_id,
                ToothCondition.tooth.in_(payload.teeth),
            )
        )
    }
    if any(
        payload.expected_revisions[tooth]
        != (existing[tooth].revision if tooth in existing else 0)
        for tooth in payload.teeth
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tooth conditions changed. Refresh the chart before trying again",
        )

    before = {
        tooth: {
            "condition": existing[tooth].condition,
            "revision": existing[tooth].revision,
        }
        if tooth in existing else {"condition": None, "revision": 0}
        for tooth in payload.teeth
    }
    condition_value = payload.condition.value if payload.condition is not None else None
    now = datetime.now(timezone.utc)
    changed_teeth = []
    for tooth in payload.teeth:
        row = existing.get(tooth)
        if row is not None and row.condition == condition_value:
            continue
        if row is None:
            row = ToothCondition(
                patient_id=patient_id,
                tooth=tooth,
                condition=condition_value,
                revision=1,
                created_by_user_id=user.id,
                updated_by_user_id=user.id,
                updated_at=now,
            )
            existing[tooth] = row
        else:
            row.condition = condition_value
            row.revision += 1
            row.updated_by_user_id = user.id
            row.updated_at = now
        db.add(row)
        changed_teeth.append(tooth)
    db.flush()
    log_event(
        db,
        actor=user,
        action=action,
        entity_type="patient",
        entity_id=str(patient_id),
        request_id=request_id,
        before_data={"teeth": before},
        after_data={
            "request": request_values,
            "changed_teeth": changed_teeth,
            "teeth": {
                tooth: {"condition": existing[tooth].condition, "revision": existing[tooth].revision}
                for tooth in payload.teeth
            },
        },
    )
    db.commit()
    return _tooth_conditions_out(db, patient_id)


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
        if requested_status == TreatmentPlanStatus.completed and not _user_has_capability(
            db, user.id, "billing.payments.write"
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

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

    completed_procedure: Procedure | None = None
    completion_charge: PatientLedgerEntry | None = None
    if "status" in changed_fields and item.status == TreatmentPlanStatus.completed:
        completed_procedure = Procedure(
            patient_id=item.patient_id,
            appointment_id=item.appointment_id,
            tooth=item.tooth,
            surface=item.surface,
            procedure_code=item.procedure_code,
            description=item.description,
            fee_pence=item.fee_pence,
            status=ProcedureStatus.completed,
            performed_at=datetime.now(timezone.utc),
            created_by_user_id=user.id,
        )
        db.add(completed_procedure)
        db.flush()
        if item.fee_pence:
            ledger_reference = f"TREATMENT-PLAN:{item.id}"
            existing_charge_id = db.scalar(
                select(PatientLedgerEntry.id).where(
                    PatientLedgerEntry.patient_id == item.patient_id,
                    PatientLedgerEntry.reference == ledger_reference,
                )
            )
            if existing_charge_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Treatment plan charge already exists",
                )
            completion_charge = PatientLedgerEntry(
                patient_id=item.patient_id,
                entry_type=LedgerEntryType.charge,
                amount_pence=item.fee_pence,
                reference=ledger_reference,
                note=f"Completed treatment plan item {item.id}",
                created_by_user_id=user.id,
                updated_by_user_id=user.id,
            )
            db.add(completion_charge)
            db.flush()

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
    if completed_procedure is not None:
        log_event(
            db,
            actor=user,
            action="clinical.procedure.completed",
            entity_type="patient",
            entity_id=str(item.patient_id),
            request_id=request_id,
            after_data={
                "procedure_id": completed_procedure.id,
                "treatment_plan_item_id": item.id,
                "appointment_id": completed_procedure.appointment_id,
                "tooth": completed_procedure.tooth,
                "surface": completed_procedure.surface,
                "procedure_code": completed_procedure.procedure_code,
                "fee_pence": completed_procedure.fee_pence,
            },
        )
    if completion_charge is not None:
        log_event(
            db,
            actor=user,
            action="ledger.charge_recorded",
            entity_type="patient",
            entity_id=str(item.patient_id),
            request_id=request_id,
            after_data={
                "ledger_entry_id": completion_charge.id,
                "treatment_plan_item_id": item.id,
                "amount_pence": completion_charge.amount_pence,
            },
        )
    db.commit()
    db.refresh(item)
    return item
