from datetime import date, datetime, time, timezone
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import require_admin
from app.models.appointment import Appointment
from app.models.legacy_resolution_event import LegacyResolutionEvent
from app.models.patient import Patient
from app.models.r4_manual_mapping import R4ManualMapping
from app.models.r4_patient_mapping import R4PatientMapping
from app.models.r4_treatment_plan import (
    R4TreatmentPlan,
    R4TreatmentPlanItem,
    R4TreatmentPlanReview,
)
from app.models.user import User
from app.schemas.legacy_admin import (
    LegacyResolveRequest,
    LegacyResolveResponse,
    UnmappedLegacyAppointmentList,
)
from app.schemas.r4_admin import (
    R4PatientMappingBackfillRequest,
    R4PatientMappingBackfillResponse,
    R4PatientMappingCreate,
    R4PatientMappingOut,
    R4TreatmentPlanDetail,
    R4TreatmentPlanSummary,
    R4UnmappedPlanPatientCode,
)
from app.schemas.r4_manual_mappings import (
    R4ManualMappingCreate,
    R4ManualMappingOut,
)
from app.services.r4_import.treatment_plan_importer import (
    backfill_r4_treatment_plan_patients_chunked,
)

router = APIRouter(prefix="/admin/legacy", tags=["legacy-admin"])
r4_router = APIRouter(prefix="/admin/r4", tags=["r4-admin"])
logger = logging.getLogger(__name__)


@router.get("/unmapped-appointments", response_model=UnmappedLegacyAppointmentList)
def list_unmapped_appointments(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
    legacy_source: str | None = Query(default="r4"),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="starts_at"),
    direction: str = Query(default="asc", alias="dir"),
):
    filters = [
        Appointment.patient_id.is_(None),
        Appointment.legacy_source.is_not(None),
    ]
    if legacy_source:
        filters.append(Appointment.legacy_source == legacy_source)
    if from_date:
        start_dt = datetime.combine(from_date, time.min, tzinfo=timezone.utc)
        filters.append(Appointment.starts_at >= start_dt)
    if to_date:
        end_dt = datetime.combine(to_date, time.max, tzinfo=timezone.utc)
        filters.append(Appointment.starts_at <= end_dt)

    sort_fields = {
        "starts_at": Appointment.starts_at,
        "created_at": Appointment.created_at,
    }
    sort_col = sort_fields.get(sort, Appointment.starts_at)
    order_by = sort_col.asc() if direction.lower() == "asc" else desc(sort_col)

    total = db.scalar(select(func.count()).select_from(Appointment).where(*filters)) or 0
    stmt = (
        select(Appointment)
        .where(*filters)
        .order_by(order_by)
        .limit(limit)
        .offset(offset)
    )
    items = list(db.scalars(stmt))
    return UnmappedLegacyAppointmentList(
        items=items,
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.post(
    "/unmapped-appointments/{appointment_id}/resolve",
    response_model=LegacyResolveResponse,
)
def resolve_unmapped_appointment(
    appointment_id: int,
    payload: LegacyResolveRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    appt = db.get(Appointment, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appt.patient_id is not None:
        raise HTTPException(
            status_code=409, detail="Appointment already linked to a patient"
        )
    patient = db.get(Patient, payload.patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Patient not found")

    from_patient_id = appt.patient_id
    appt.patient_id = patient.id
    appt.updated_by_user_id = admin.id
    db.add(appt)

    event = LegacyResolutionEvent(
        actor_user_id=admin.id,
        entity_type="appointment",
        entity_id=str(appt.id),
        legacy_source=appt.legacy_source,
        legacy_id=appt.legacy_id,
        action="link_patient",
        from_patient_id=from_patient_id,
        to_patient_id=patient.id,
        notes=payload.notes,
    )
    db.add(event)
    db.commit()
    db.refresh(appt)
    return LegacyResolveResponse(
        id=appt.id,
        patient_id=appt.patient_id,
        legacy_source=appt.legacy_source,
        legacy_id=appt.legacy_id,
    )


@r4_router.get("/treatment-plans", response_model=list[R4TreatmentPlanSummary])
def list_r4_treatment_plans(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
    legacy_patient_code: int = Query(..., ge=1),
    limit: int = Query(default=50, ge=1, le=200),
):
    item_counts = (
        select(
            R4TreatmentPlanItem.treatment_plan_id.label("plan_id"),
            func.count().label("item_count"),
        )
        .group_by(R4TreatmentPlanItem.treatment_plan_id)
        .subquery()
    )
    stmt = (
        select(
            R4TreatmentPlan,
            func.coalesce(item_counts.c.item_count, 0).label("item_count"),
        )
        .outerjoin(item_counts, item_counts.c.plan_id == R4TreatmentPlan.id)
        .where(R4TreatmentPlan.legacy_patient_code == legacy_patient_code)
        .order_by(desc(R4TreatmentPlan.creation_date).nullslast(), desc(R4TreatmentPlan.id))
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    summaries: list[R4TreatmentPlanSummary] = []
    for plan, item_count in rows:
        summaries.append(
            R4TreatmentPlanSummary(
                id=plan.id,
                legacy_patient_code=plan.legacy_patient_code,
                legacy_tp_number=plan.legacy_tp_number,
                plan_index=plan.plan_index,
                is_master=plan.is_master,
                is_current=plan.is_current,
                is_accepted=plan.is_accepted,
                creation_date=plan.creation_date,
                acceptance_date=plan.acceptance_date,
                completion_date=plan.completion_date,
                status_code=plan.status_code,
                reason_id=plan.reason_id,
                tp_group=plan.tp_group,
                item_count=int(item_count or 0),
            )
        )
    return summaries


@r4_router.get("/treatment-plans/{plan_id}", response_model=R4TreatmentPlanDetail)
def get_r4_treatment_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    plan = db.get(R4TreatmentPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Treatment plan not found")

    items = list(
        db.scalars(
            select(R4TreatmentPlanItem)
            .where(R4TreatmentPlanItem.treatment_plan_id == plan.id)
            .order_by(R4TreatmentPlanItem.legacy_tp_item.asc())
        )
    )
    reviews = list(
        db.scalars(
            select(R4TreatmentPlanReview).where(
                R4TreatmentPlanReview.treatment_plan_id == plan.id
            )
        )
    )
    return R4TreatmentPlanDetail(
        plan=plan,
        items=items,
        reviews=reviews,
    )


@r4_router.get(
    "/patient-mappings/unmapped-plans", response_model=list[R4UnmappedPlanPatientCode]
)
def list_r4_unmapped_plan_patient_codes(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
    legacy_source: str | None = Query(default="r4"),
    legacy_patient_code: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=500),
):
    stmt = (
        select(
            R4TreatmentPlan.legacy_patient_code,
            func.count().label("plan_count"),
        )
        .where(R4TreatmentPlan.patient_id.is_(None))
        .group_by(R4TreatmentPlan.legacy_patient_code)
        .order_by(desc(func.count()), R4TreatmentPlan.legacy_patient_code.asc())
        .limit(limit)
    )
    if legacy_source:
        stmt = stmt.where(R4TreatmentPlan.legacy_source == legacy_source)
    if legacy_patient_code is not None:
        stmt = stmt.where(R4TreatmentPlan.legacy_patient_code == legacy_patient_code)
    rows = db.execute(stmt).all()
    return [
        R4UnmappedPlanPatientCode(
            legacy_patient_code=int(code),
            plan_count=int(count),
        )
        for code, count in rows
    ]


@r4_router.post("/patient-mappings", response_model=R4PatientMappingOut)
def create_r4_patient_mapping(
    payload: R4PatientMappingCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    patient = db.get(Patient, payload.patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Patient not found")

    existing = db.scalar(
        select(R4PatientMapping).where(
            R4PatientMapping.legacy_source == "r4",
            R4PatientMapping.legacy_patient_code == payload.legacy_patient_code,
        )
    )
    if existing:
        raise HTTPException(
            status_code=409, detail="Mapping already exists for legacy patient code"
        )
    existing_by_patient = db.scalar(
        select(R4PatientMapping).where(
            R4PatientMapping.legacy_source == "r4",
            R4PatientMapping.patient_id == payload.patient_id,
        )
    )
    if existing_by_patient:
        raise HTTPException(
            status_code=409, detail="Mapping already exists for patient"
        )

    mapping = R4PatientMapping(
        legacy_source="r4",
        legacy_patient_code=payload.legacy_patient_code,
        patient_id=payload.patient_id,
        created_by_user_id=admin.id,
        updated_by_user_id=admin.id,
    )
    db.add(mapping)
    db.flush()

    event = LegacyResolutionEvent(
        actor_user_id=admin.id,
        entity_type="r4_patient_mapping",
        entity_id=str(mapping.id),
        legacy_source="r4",
        legacy_id=str(payload.legacy_patient_code),
        action="link_patient",
        from_patient_id=None,
        to_patient_id=payload.patient_id,
        notes=payload.notes,
    )
    db.add(event)
    db.commit()
    db.refresh(mapping)
    return mapping


@r4_router.get("/manual-mappings", response_model=list[R4ManualMappingOut])
def list_r4_manual_mappings(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
    legacy_patient_code: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=500),
):
    stmt = select(R4ManualMapping).where(R4ManualMapping.legacy_source == "r4")
    if legacy_patient_code is not None:
        stmt = stmt.where(R4ManualMapping.legacy_patient_code == legacy_patient_code)
    stmt = stmt.order_by(R4ManualMapping.created_at.desc()).limit(limit)
    return list(db.scalars(stmt))


@r4_router.post("/manual-mappings", response_model=R4ManualMappingOut)
def create_r4_manual_mapping(
    payload: R4ManualMappingCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    patient = db.get(Patient, payload.target_patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Patient not found")

    existing = db.scalar(
        select(R4ManualMapping).where(
            R4ManualMapping.legacy_source == "r4",
            R4ManualMapping.legacy_patient_code == payload.legacy_patient_code,
        )
    )
    if existing:
        raise HTTPException(
            status_code=409, detail="Manual mapping already exists for legacy patient code"
        )

    mapping = R4ManualMapping(
        legacy_source="r4",
        legacy_patient_code=payload.legacy_patient_code,
        target_patient_id=payload.target_patient_id,
        note=payload.note,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)

    logger.info(
        "R4 manual mapping created",
        extra={
            "actor_id": admin.id,
            "legacy_patient_code": payload.legacy_patient_code,
            "target_patient_id": payload.target_patient_id,
        },
    )
    return mapping


@r4_router.delete("/manual-mappings/{mapping_id}", status_code=204)
def delete_r4_manual_mapping(
    mapping_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    mapping = db.get(R4ManualMapping, mapping_id)
    if not mapping or mapping.legacy_source != "r4":
        raise HTTPException(status_code=404, detail="Manual mapping not found")

    db.delete(mapping)
    db.commit()
    logger.info(
        "R4 manual mapping deleted",
        extra={
            "actor_id": admin.id,
            "legacy_patient_code": mapping.legacy_patient_code,
            "target_patient_id": mapping.target_patient_id,
        },
    )
    return None


@r4_router.post(
    "/patient-mappings/backfill-patient-ids",
    response_model=R4PatientMappingBackfillResponse,
)
def backfill_r4_patient_mapping_ids(
    payload: R4PatientMappingBackfillRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    stats = backfill_r4_treatment_plan_patients_chunked(
        db,
        admin.id,
        legacy_source="r4",
        limit=payload.limit,
        dry_run=payload.dry_run,
        only_unmapped=payload.only_unmapped,
    )
    if not payload.dry_run:
        db.commit()
    logger.info(
        "R4 patient backfill executed",
        extra={
            "actor_id": admin.id,
            "limit": payload.limit,
            "dry_run": payload.dry_run,
            "only_unmapped": payload.only_unmapped,
            "processed": stats.processed,
            "updated": stats.updated,
            "remaining_estimate": stats.remaining_estimate,
        },
    )
    return R4PatientMappingBackfillResponse(
        processed=stats.processed,
        updated=stats.updated,
        remaining_estimate=stats.remaining_estimate,
        dry_run=payload.dry_run,
    )
