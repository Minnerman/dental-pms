from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import require_roles
from app.models.patient import PatientCategory
from app.models.treatment import Treatment
from app.models.user import User
from app.schemas.treatment import (
    TreatmentCreate,
    TreatmentFeeOut,
    TreatmentFeeUpsert,
    TreatmentFeeChange,
    TreatmentOut,
    TreatmentUpdate,
    RoutineDefaultsRequest,
)
from app.services import treatment_fees as service
from app.services.audit import log_event

router = APIRouter(prefix="/treatments", tags=["treatments"])


@router.get("/index")
def treatment_index(patient_category: PatientCategory = PatientCategory.clinic_private,
                    include_inactive: bool = False, db: Session = Depends(get_db),
                    _user: User = Depends(require_roles("superadmin"))):
    return service.treatment_index(db, patient_category, include_inactive)


@router.post("/routine-defaults")
def routine_defaults(payload: RoutineDefaultsRequest, db: Session = Depends(get_db),
                     user: User = Depends(require_roles("superadmin"))):
    return service.initialize_routines(db, user)


@router.get("", response_model=list[TreatmentOut])
def list_treatments(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("superadmin")),
    include_inactive: bool = Query(default=False),
):
    stmt = select(Treatment).order_by(*service.treatment_order())
    if not include_inactive:
        stmt = stmt.where(Treatment.is_active.is_(True))
    return list(db.scalars(stmt))


@router.post("", response_model=TreatmentOut, status_code=status.HTTP_201_CREATED)
def create_treatment(
    payload: TreatmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("superadmin")),
):
    treatment = Treatment(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active,
        default_duration_minutes=payload.default_duration_minutes,
        is_denplan_included_default=payload.is_denplan_included_default,
        level=payload.level,
        display_order=payload.display_order,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    db.add(treatment)
    db.flush()
    log_event(db, actor=user, action="treatment.created", entity_type="treatment", entity_id=str(treatment.id),
        after_data={"name": treatment.name, "level": treatment.level, "display_order": treatment.display_order})
    db.commit()
    db.refresh(treatment)
    return treatment


@router.get("/{treatment_id}", response_model=TreatmentOut)
def get_treatment(
    treatment_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("superadmin")),
):
    return service.get_treatment(db, treatment_id)


@router.patch("/{treatment_id}", response_model=TreatmentOut)
def update_treatment(
    treatment_id: int,
    payload: TreatmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("superadmin")),
):
    treatment = service.get_treatment(db, treatment_id, lock=True)
    values = payload.model_dump(exclude_unset=True)
    before = {field: getattr(treatment, field) for field in values}
    for field, value in values.items():
        setattr(treatment, field, value)
    treatment.updated_by_user_id = user.id
    db.add(treatment)
    if before != values:
        log_event(db, actor=user, action="treatment.updated", entity_type="treatment", entity_id=str(treatment.id),
            before_data=before, after_data=values)
    db.commit()
    db.refresh(treatment)
    return treatment


@router.get("/{treatment_id}/fees", response_model=list[TreatmentFeeOut])
def list_treatment_fees(
    treatment_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("superadmin")),
):
    return service.current_fees(db, treatment_id)


@router.put("/{treatment_id}/fees", response_model=list[TreatmentFeeOut])
def replace_treatment_fees(
    treatment_id: int,
    payload: list[TreatmentFeeUpsert],
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("superadmin")),
):
    return service.replace_current_fees(db, treatment_id, payload, user)


@router.post("/{treatment_id}/fee-changes")
def change_fee(treatment_id: int, payload: TreatmentFeeChange,
               request_id: str = Header(min_length=1, max_length=120), db: Session = Depends(get_db),
               user: User = Depends(require_roles("superadmin"))):
    return service.change_fee(db, treatment_id, payload, user, request_id)


@router.get("/{treatment_id}/fee-history")
def fee_history(treatment_id: int, patient_category: PatientCategory,
                limit: int = Query(default=50, ge=1, le=100), before_revision: int | None = Query(default=None, ge=1),
                db: Session = Depends(get_db), _user: User = Depends(require_roles("superadmin"))):
    return service.fee_history(db, treatment_id, patient_category, limit, before_revision)
