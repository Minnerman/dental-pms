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
    ToothBridgeGroup,
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
    CrownConditionUpdate,
    BridgeCreate,
    BridgeReset,
    ARCH_TEETH,
    MATERIAL_CROWN_KINDS,
    DENTURE_CROWN_KINDS,
    ProcedureCreate,
    ProcedureOut,
    RootConditionUpdate,
    SurfaceConditionUpdate,
    schematic_root_count,
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
from app.services.clinical_completion import complete_plan_item
from app.schemas.clinical_note import ToothNoteAmendment, NativeNoteHistoryOut
from app.services import native_notes

patient_router = APIRouter(prefix="/patients/{patient_id}", tags=["clinical"])
router = APIRouter(prefix="/treatment-plan", tags=["clinical"])

CLINICAL_VIEW = require_capability("clinical.view")
CLINICAL_WRITE = require_capability("clinical.write")
OBSERVATION_AUDIT_ACTIONS = [
    "clinical.tooth_conditions.recorded", "clinical.root_conditions.recorded", "clinical.crown_conditions.recorded",
    "clinical.bridge.created", "clinical.bridge.reset",
    "clinical.surface_conditions.recorded",
]
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


def _bridge_snapshot(group_id: int, members: list[ToothCondition]) -> dict:
    arch = "upper" if members[0].tooth.startswith("U") else "lower"
    ordered = sorted(members, key=lambda member: ARCH_TEETH[arch].index(member.tooth))
    return {"id": group_id, "arch": arch, "span_start": ordered[0].tooth, "span_end": ordered[-1].tooth,
            "members": [{"tooth": member.tooth, "role": member.bridge_role} for member in ordered]}


def _meaningful_roots(row: ToothCondition | None) -> bool:
    return bool(row and any(value.get("condition") is not None or value.get("apicectomy")
                            for value in row.root_observations.values()))


def _meaningful_surfaces(row: ToothCondition | None) -> bool:
    return bool(row and any(value.get("kind") is not None for value in row.surface_observations.values()))


def _artificial_site_allowed(row: ToothCondition | None) -> bool:
    return ((row is None or row.condition in {None, "missing", "unrecorded"})
            and not _meaningful_roots(row) and not _meaningful_surfaces(row))


def _has_anatomy_observations(row: ToothCondition) -> bool:
    return bool(row.root_observations or row.crown_observation is not None or row.surface_observations)


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
    bridge_members = {}
    for condition in conditions:
        if condition.bridge_group_id is not None:
            bridge_members.setdefault(condition.bridge_group_id, []).append(condition)
    return ToothConditionsOut(
        patient_id=patient_id,
        teeth={condition.tooth: condition for condition in conditions},
        note_teeth=note_teeth,
        bridges=[_bridge_snapshot(group_id, members) for group_id, members in sorted(bridge_members.items())],
    )


def _tooth_condition_snapshot(row: ToothCondition | None) -> dict:
    return {
        "condition": row.condition if row else None,
        "dentition": row.dentition if row else None,
        "movement": row.movement if row else None,
        "rotation": row.rotation if row else None,
        "root_observations": row.root_observations if row else {},
        "crown_observation": row.crown_observation if row else None,
        "surface_observations": row.surface_observations if row else {},
        "bridge_group_id": row.bridge_group_id if row else None,
        "bridge_role": row.bridge_role if row else None,
        "revision": row.revision if row else 0,
    }


def _tooth_observation_patch(row: ToothCondition | None, request_values: dict) -> dict:
    observations = {key: request_values[key] for key in ("condition", "dentition", "movement", "rotation")
                    if key in request_values}
    if observations.get("condition") == "deciduous":
        # Compatibility with older clients: primary/present shorthand.
        observations["dentition"] = "deciduous"
    elif observations.get("condition") in {"unrecorded", "implant"}:
        observations["dentition"] = None
    elif "dentition" in observations and "condition" not in observations and row and row.condition == "deciduous":
        # The legacy shorthand cannot coexist with a different identity.
        if observations["dentition"] != "deciduous":
            observations["condition"] = "present" if observations["dentition"] == "permanent" else None
    return observations


def _whole_tooth_clears_anatomy_observations(row: ToothCondition | None, observations: dict) -> bool:
    if observations.get("condition") in {"unrecorded", "missing", "implant", "unerupted"}:
        return True
    return "dentition" in observations and observations["dentition"] != (row.dentition if row else None)


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
    # All observations for a patient share this lock, including multi-tooth writes
    # and retries. Validate every revision before changing any selected tooth.
    get_patient_or_404(db, patient_id, for_update=True)
    action = "clinical.tooth_conditions.recorded"
    # Omitted attributes are preserved, not reset. Excluding them also preserves
    # request-ID replay compatibility with old condition-only clients/audits.
    request_values = payload.model_dump(mode="json", exclude_unset=True)
    duplicate = _duplicate_audit(
        db, patient_id=patient_id, request_id=request_id, actions=OBSERVATION_AUDIT_ACTIONS
    )
    if duplicate:
        if duplicate.action != action or (duplicate.after_json or {}).get("request") != request_values:
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

    before = {tooth: _tooth_condition_snapshot(existing.get(tooth)) for tooth in payload.teeth}
    patches = {tooth: _tooth_observation_patch(existing.get(tooth), request_values) for tooth in payload.teeth}
    for tooth, row in existing.items():
        observations = patches[tooth]
        if (observations.get("dentition") is not None
                and observations.get("condition", row.condition) == "implant"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="An implant has no natural tooth dentition")
        if ((row.crown_observation or {}).get("kind") in DENTURE_CROWN_KINDS
                and "condition" in observations and observations["condition"] not in {None, "missing", "unrecorded"}
                and not _whole_tooth_clears_anatomy_observations(row, observations)):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Reset the denture crown before recording an incompatible tooth condition")
        if row.bridge_group_id is not None and {"condition", "dentition"}.intersection(observations):
            clears_recorded_anatomy = (_whole_tooth_clears_anatomy_observations(row, observations)
                                      and _has_anatomy_observations(row))
            if (any(observations[key] != getattr(row, key) for key in ("condition", "dentition") if key in observations)
                    or clears_recorded_anatomy):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Reset the complete bridge before changing a member's tooth condition")
    now = datetime.now(timezone.utc)
    changed_teeth = []
    for tooth in payload.teeth:
        row = existing.get(tooth)
        observations = patches[tooth]
        clear_anatomy = _whole_tooth_clears_anatomy_observations(row, observations)
        if (row is not None and all(getattr(row, key) == value for key, value in observations.items())
                and not (clear_anatomy and _has_anatomy_observations(row))):
            continue
        if row is None:
            row = ToothCondition(
                patient_id=patient_id,
                tooth=tooth,
                **observations,
                revision=1,
                created_by_user_id=user.id,
                updated_by_user_id=user.id,
                updated_at=now,
            )
            existing[tooth] = row
        else:
            for key, value in observations.items():
                setattr(row, key, value)
            if clear_anatomy:
                # Replacing the map preserves the pre-change audit snapshot.
                row.root_observations = {}
                row.crown_observation = None
                row.surface_observations = {}
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
                tooth: _tooth_condition_snapshot(existing[tooth])
                for tooth in payload.teeth
            },
        },
    )
    db.commit()
    return _tooth_conditions_out(db, patient_id)


@patient_router.post("/clinical/root-conditions", response_model=ToothConditionsOut)
def update_root_conditions(
    patient_id: int,
    payload: RootConditionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(CLINICAL_WRITE),
    _viewer: User = Depends(CLINICAL_VIEW),
    request_id: str | None = Header(default=None, min_length=1, max_length=120),
):
    # Whole-root-area edits and whole-tooth resets share the same patient lock.
    # Validate the entire selection before changing any tooth or root map.
    get_patient_or_404(db, patient_id, for_update=True)
    action = "clinical.root_conditions.recorded"
    request_values = payload.model_dump(mode="json", exclude_unset=True)
    duplicate = _duplicate_audit(
        db, patient_id=patient_id, request_id=request_id, actions=OBSERVATION_AUDIT_ACTIONS
    )
    if duplicate:
        if duplicate.action != action or (duplicate.after_json or {}).get("request") != request_values:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                detail="Request-Id was already used for a different tooth or root observation")
        return _tooth_conditions_out(db, patient_id)

    existing = {row.tooth: row for row in db.scalars(select(ToothCondition).where(
        ToothCondition.patient_id == patient_id, ToothCondition.tooth.in_(payload.teeth),
    ))}
    if any(payload.expected_revisions[tooth] != (existing[tooth].revision if tooth in existing else 0)
           for tooth in payload.teeth):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
            detail="Tooth conditions changed. Refresh the chart before trying again")
    root_counts = {}
    for tooth in payload.teeth:
        row = existing.get(tooth)
        condition = row.condition if row else None
        if row and (row.bridge_role == "pontic" or (row.crown_observation or {}).get("kind") in DENTURE_CROWN_KINDS):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Natural root observations cannot be recorded for a pontic or denture tooth")
        if condition in {"missing", "implant", "unerupted"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Roots cannot be recorded for a missing, implant or unerupted tooth")
        dentition = row.dentition if row and row.dentition else "deciduous" if condition == "deciduous" else "permanent"
        root_counts[tooth] = schematic_root_count(tooth, dentition)

    before = {tooth: _tooth_condition_snapshot(existing.get(tooth)) for tooth in payload.teeth}
    changed_roots = {}
    now = datetime.now(timezone.utc)
    for tooth in payload.teeth:
        row = existing.get(tooth)
        roots = dict(row.root_observations) if row else {}
        changed = []
        for root in range(1, root_counts[tooth] + 1):
            root_key = str(root)
            root_observation = {**roots.get(root_key, {"condition": None, "apicectomy": False})}
            for field in ("condition", "apicectomy"):
                if field in request_values:
                    root_observation[field] = request_values[field]
            if root_key not in roots or roots[root_key] != root_observation:
                roots[root_key] = root_observation
                changed.append(root_key)
        if not changed:
            continue
        changed_roots[tooth] = changed
        if row is None:
            row = ToothCondition(patient_id=patient_id, tooth=tooth, revision=1,
                root_observations=roots, created_by_user_id=user.id,
                updated_by_user_id=user.id, updated_at=now)
            existing[tooth] = row
        else:
            row.root_observations = roots
            row.revision += 1
            row.updated_by_user_id = user.id
            row.updated_at = now
        db.add(row)
    db.flush()
    log_event(db, actor=user, action=action,
        entity_type="patient", entity_id=str(patient_id), request_id=request_id,
        before_data={"teeth": before},
        after_data={"request": request_values, "changed_teeth": list(changed_roots),
                    "changed_roots": changed_roots,
                    "teeth": {tooth: _tooth_condition_snapshot(existing[tooth]) for tooth in payload.teeth}},
    )
    db.commit()
    return _tooth_conditions_out(db, patient_id)


@patient_router.post("/clinical/crown-conditions", response_model=ToothConditionsOut)
def update_crown_conditions(
    patient_id: int,
    payload: CrownConditionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(CLINICAL_WRITE),
    _viewer: User = Depends(CLINICAL_VIEW),
    request_id: str | None = Header(default=None, min_length=1, max_length=120),
):
    # Crown/root/tooth changes are one revision domain. Nothing is inferred from
    # treatment history, and every selected tooth validates before any write.
    get_patient_or_404(db, patient_id, for_update=True)
    action = "clinical.crown_conditions.recorded"
    request_values = payload.model_dump(mode="json")
    duplicate = _duplicate_audit(
        db, patient_id=patient_id, request_id=request_id, actions=OBSERVATION_AUDIT_ACTIONS,
    )
    if duplicate:
        if duplicate.action != action or (duplicate.after_json or {}).get("request") != request_values:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                detail="Request-Id was already used for a different tooth observation")
        return _tooth_conditions_out(db, patient_id)

    existing = {row.tooth: row for row in db.scalars(select(ToothCondition).where(
        ToothCondition.patient_id == patient_id, ToothCondition.tooth.in_(payload.teeth),
    ))}
    if any(payload.expected_revisions[tooth] != (existing[tooth].revision if tooth in existing else 0)
           for tooth in payload.teeth):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
            detail="Tooth conditions changed. Refresh the chart before trying again")
    for tooth in payload.teeth:
        row = existing.get(tooth)
        condition = row.condition if row else None
        old_crown = row.crown_observation if row else None
        if row and row.bridge_group_id is not None and payload.kind not in MATERIAL_CROWN_KINDS:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Reset the complete bridge before clearing or replacing a member's crown")
        if payload.kind in DENTURE_CROWN_KINDS:
            if not _artificial_site_allowed(row):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="A denture tooth requires a missing or unspecified tooth without current root or surface findings; reset incompatible findings first")
        elif condition == "unerupted" or (condition == "missing" and not (
                row and row.bridge_role == "pontic" and payload.kind in MATERIAL_CROWN_KINDS
                or payload.kind is None and old_crown is not None and old_crown.get("kind") in DENTURE_CROWN_KINDS | {None})):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A missing tooth requires an explicit pontic or denture observation")

    before = {tooth: _tooth_condition_snapshot(existing.get(tooth)) for tooth in payload.teeth}
    observation = {"kind": payload.kind, "issues": payload.issues}
    changed_teeth = []
    now = datetime.now(timezone.utc)
    for tooth in payload.teeth:
        row = existing.get(tooth)
        if row is not None and row.crown_observation == observation:
            continue
        # Each row receives a new value; neither other teeth nor before-audit
        # snapshots share a mutable object with this replacement.
        crown = {"kind": observation["kind"], "issues": list(observation["issues"])}
        if row is None:
            row = ToothCondition(patient_id=patient_id, tooth=tooth, revision=1,
                crown_observation=crown, created_by_user_id=user.id,
                updated_by_user_id=user.id, updated_at=now)
            existing[tooth] = row
        else:
            row.crown_observation = crown
            row.revision += 1
            row.updated_by_user_id = user.id
            row.updated_at = now
        db.add(row)
        changed_teeth.append(tooth)
    db.flush()
    log_event(db, actor=user, action=action,
        entity_type="patient", entity_id=str(patient_id), request_id=request_id,
        before_data={"teeth": before},
        after_data={"request": request_values, "changed_teeth": changed_teeth,
                    "teeth": {tooth: _tooth_condition_snapshot(existing[tooth]) for tooth in payload.teeth}},
    )
    db.commit()
    return _tooth_conditions_out(db, patient_id)


@patient_router.post("/clinical/surface-conditions", response_model=ToothConditionsOut)
def update_surface_conditions(
    patient_id: int,
    payload: SurfaceConditionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(CLINICAL_WRITE),
    _viewer: User = Depends(CLINICAL_VIEW),
    request_id: str | None = Header(default=None, min_length=1, max_length=120),
):
    # These are current findings on natural surfaces, not procedures or charges.
    # The existing patient lock serializes every layer and whole-tooth reset.
    get_patient_or_404(db, patient_id, for_update=True)
    action = "clinical.surface_conditions.recorded"
    request_values = payload.model_dump(mode="json")
    duplicate = _duplicate_audit(db, patient_id=patient_id, request_id=request_id,
        actions=OBSERVATION_AUDIT_ACTIONS)
    if duplicate:
        if duplicate.action != action or (duplicate.after_json or {}).get("request") != request_values:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                detail="Request-Id was already used for a different tooth observation")
        return _tooth_conditions_out(db, patient_id)

    teeth = [target.tooth for target in payload.targets]
    existing = {row.tooth: row for row in db.scalars(select(ToothCondition).where(
        ToothCondition.patient_id == patient_id, ToothCondition.tooth.in_(teeth),
    ))}
    if any(payload.expected_revisions[tooth] != (existing[tooth].revision if tooth in existing else 0)
           for tooth in teeth):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
            detail="Tooth conditions changed. Refresh the chart before trying again")
    for row in existing.values():
        crown_kind = (row.crown_observation or {}).get("kind")
        if (row.condition in {"missing", "unerupted", "implant"} or row.bridge_role == "pontic"
                or crown_kind in DENTURE_CROWN_KINDS | {"fractured"}):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Surface findings require a natural tooth or a crowned natural support, not a missing, unerupted, implant, pontic, denture or absent crown")

    before = {tooth: _tooth_condition_snapshot(existing.get(tooth)) for tooth in teeth}
    changed_surfaces = {}
    now = datetime.now(timezone.utc)
    for target in payload.targets:
        row = existing.get(target.tooth)
        surfaces = dict(row.surface_observations) if row else {}
        changed = []
        for surface in target.surfaces:
            observation = payload.observation.model_dump(mode="json")
            if surface not in surfaces or surfaces[surface] != observation:
                # Replace entries and maps, preserving independent other surfaces
                # and the immutable before-audit snapshot.
                surfaces[surface] = observation
                changed.append(surface)
        if not changed:
            continue
        changed_surfaces[target.tooth] = changed
        if row is None:
            row = ToothCondition(patient_id=patient_id, tooth=target.tooth, revision=1,
                surface_observations=surfaces, created_by_user_id=user.id,
                updated_by_user_id=user.id, updated_at=now)
            existing[target.tooth] = row
        else:
            row.surface_observations = surfaces
            row.revision += 1
            row.updated_by_user_id = user.id
            row.updated_at = now
        db.add(row)
    db.flush()
    log_event(db, actor=user, action=action,
        entity_type="patient", entity_id=str(patient_id), request_id=request_id,
        before_data={"teeth": before},
        after_data={"request": request_values, "changed_teeth": list(changed_surfaces),
                    "changed_surfaces": changed_surfaces,
                    "teeth": {tooth: _tooth_condition_snapshot(existing[tooth]) for tooth in teeth}},
    )
    db.commit()
    return _tooth_conditions_out(db, patient_id)


@patient_router.post("/clinical/bridges", response_model=ToothConditionsOut)
def create_bridge(
    patient_id: int,
    payload: BridgeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(CLINICAL_WRITE),
    _viewer: User = Depends(CLINICAL_VIEW),
    request_id: str | None = Header(default=None, min_length=1, max_length=120),
):
    get_patient_or_404(db, patient_id, for_update=True)
    action = "clinical.bridge.created"
    request_values = payload.model_dump(mode="json", exclude_unset=True)
    duplicate = _duplicate_audit(db, patient_id=patient_id, request_id=request_id, actions=OBSERVATION_AUDIT_ACTIONS)
    if duplicate:
        if duplicate.action != action or (duplicate.after_json or {}).get("request") != request_values:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request-Id was already used for a different observation")
        return _tooth_conditions_out(db, patient_id)
    teeth = [member.tooth for member in payload.members]
    existing = {row.tooth: row for row in db.scalars(select(ToothCondition).where(
        ToothCondition.patient_id == patient_id, ToothCondition.tooth.in_(teeth)))}
    if any(payload.expected_revisions[tooth] != (existing[tooth].revision if tooth in existing else 0) for tooth in teeth):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tooth conditions changed. Refresh before creating the bridge")
    for member in payload.members:
        row = existing.get(member.tooth)
        if row and row.bridge_group_id is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A selected tooth already belongs to a bridge")
        crown_kind = payload.crown.kind if payload.crown else (row.crown_observation or {}).get("kind") if row else None
        if crown_kind is not None and crown_kind not in MATERIAL_CROWN_KINDS:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Provide an explicit bridge material to replace incompatible crown observations")
        if member.role == "pontic":
            if not _artificial_site_allowed(row):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="A pontic requires a missing or unspecified tooth without current root or surface findings; reset incompatible findings first")
        elif row and (row.condition in {"missing", "unerupted"} or
                      member.role == "wing" and row.condition == "implant"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A support requires an available tooth; an implant cannot be a wing")

    before = {tooth: _tooth_condition_snapshot(existing.get(tooth)) for tooth in teeth}
    now = datetime.now(timezone.utc)
    group = ToothBridgeGroup(patient_id=patient_id, created_by_user_id=user.id,
        updated_by_user_id=user.id, updated_at=now)
    db.add(group)
    db.flush()
    for member in payload.members:
        row = existing.get(member.tooth)
        if row is None:
            row = ToothCondition(patient_id=patient_id, tooth=member.tooth, revision=1,
                created_by_user_id=user.id, updated_by_user_id=user.id, updated_at=now)
            existing[member.tooth] = row
        else:
            row.revision += 1
            row.updated_by_user_id = user.id
            row.updated_at = now
        row.bridge_group_id, row.bridge_role = group.id, member.role
        if payload.crown:
            row.crown_observation = payload.crown.model_dump(mode="json")
        db.add(row)
    db.flush()
    log_event(db, actor=user, action=action, entity_type="patient", entity_id=str(patient_id), request_id=request_id,
        before_data={"bridge": None, "teeth": before},
        after_data={"request": request_values, "bridge": _bridge_snapshot(group.id, list(existing.values())),
                    "changed_teeth": teeth, "teeth": {tooth: _tooth_condition_snapshot(existing[tooth]) for tooth in teeth}})
    db.commit()
    return _tooth_conditions_out(db, patient_id)


@patient_router.post("/clinical/bridges/{bridge_id}/reset", response_model=ToothConditionsOut)
def reset_bridge(
    patient_id: int,
    bridge_id: int,
    payload: BridgeReset,
    db: Session = Depends(get_db),
    user: User = Depends(CLINICAL_WRITE),
    _viewer: User = Depends(CLINICAL_VIEW),
    request_id: str | None = Header(default=None, min_length=1, max_length=120),
):
    get_patient_or_404(db, patient_id, for_update=True)
    action = "clinical.bridge.reset"
    request_values = {"bridge_id": bridge_id, **payload.model_dump(mode="json")}
    duplicate = _duplicate_audit(db, patient_id=patient_id, request_id=request_id, actions=OBSERVATION_AUDIT_ACTIONS)
    if duplicate:
        if duplicate.action != action or (duplicate.after_json or {}).get("request") != request_values:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request-Id was already used for a different observation")
        return _tooth_conditions_out(db, patient_id)
    group = db.scalar(select(ToothBridgeGroup).where(ToothBridgeGroup.id == bridge_id, ToothBridgeGroup.patient_id == patient_id))
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bridge not found")
    members = list(db.scalars(select(ToothCondition).where(ToothCondition.patient_id == patient_id,
                                                         ToothCondition.bridge_group_id == bridge_id)))
    if set(payload.expected_revisions) != {row.tooth for row in members}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Reset requires exactly every current bridge member")
    if any(payload.expected_revisions[row.tooth] != row.revision for row in members):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bridge member conditions changed. Refresh before resetting")
    before_bridge = _bridge_snapshot(group.id, members)
    before = {row.tooth: _tooth_condition_snapshot(row) for row in members}
    now = datetime.now(timezone.utc)
    for row in members:
        row.bridge_group_id = None
        row.bridge_role = None
        row.crown_observation = {"kind": None, "issues": []}
        row.revision += 1
        row.updated_by_user_id = user.id
        row.updated_at = now
    db.flush()
    db.delete(group)
    log_event(db, actor=user, action=action, entity_type="patient", entity_id=str(patient_id), request_id=request_id,
        before_data={"bridge": before_bridge, "teeth": before},
        after_data={"request": request_values, "bridge": None,
                    "changed_teeth": [member["tooth"] for member in before_bridge["members"]],
                    "teeth": {row.tooth: _tooth_condition_snapshot(row) for row in members}})
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
    fingerprint_payload = {"patient_id": patient_id, **payload.model_dump(mode="json")}
    duplicate_id = native_notes.replay_target(db, user.id, request_id, "clinical.tooth_note.created", fingerprint_payload)
    if duplicate_id is not None:
        return _tooth_note_or_404(db, patient_id, duplicate_id)
    metadata = native_notes.creation_metadata(db, payload, user)
    note = ToothNote(
        patient_id=patient_id,
        tooth=payload.tooth,
        surface=payload.surface,
        note=payload.note,
        created_by_user_id=user.id,
        **metadata,
    )
    db.add(note)
    db.flush()
    native_notes.save_snapshot(db, note, user.id)
    native_notes.record_receipt(db, user.id, request_id, "clinical.tooth_note.created", fingerprint_payload, note.id)
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


def _tooth_note_or_404(db: Session, patient_id: int, note_id: int, *, for_update=False):
    get_patient_or_404(db, patient_id)
    stmt = select(ToothNote).where(ToothNote.id == note_id, ToothNote.patient_id == patient_id)
    if for_update:
        stmt = stmt.with_for_update(of=ToothNote)
    note = db.scalar(stmt)
    if note is None:
        raise HTTPException(404, "Tooth note not found")
    return note


@patient_router.patch("/tooth-notes/{note_id}", response_model=ToothNoteOut)
def amend_tooth_note(
    patient_id: int, note_id: int, payload: ToothNoteAmendment,
    db: Session = Depends(get_db), user: User = Depends(CLINICAL_WRITE),
    _viewer: User = Depends(CLINICAL_VIEW),
    request_id: str | None = Header(default=None, max_length=120),
):
    get_patient_or_404(db, patient_id, for_update=True)
    note = _tooth_note_or_404(db, patient_id, note_id, for_update=True)
    fingerprint_payload = {"patient_id": patient_id, "note_id": note_id, **payload.model_dump(mode="json", exclude_unset=True)}
    action = "clinical.tooth_note.updated"
    if native_notes.replay_target(db, user.id, request_id, action, fingerprint_payload) is not None:
        return note
    native_notes.check_revision(note, payload.expected_revision)
    updates = payload.model_dump(exclude_unset=True, exclude={"expected_revision", "reason"})
    changed = {key for key, value in updates.items() if getattr(note, key) != value}
    if changed:
        native_notes.ensure_baseline(db, note)
        before = {"tooth_note_id": note.id, "revision": note.revision}
        for field in changed:
            setattr(note, field, updates[field])
        note.revision += 1
        native_notes.save_snapshot(db, note, user.id, reason=payload.reason)
        log_event(db, actor=user, action=action, entity_type="patient", entity_id=str(patient_id), request_id=request_id,
                  before_data=before, after_data={"tooth_note_id": note.id, "tooth": note.tooth, "surface": note.surface,
                                                  "revision": note.revision, "changed_fields": sorted(changed)})
    native_notes.record_receipt(db, user.id, request_id, action, fingerprint_payload, note.id)
    db.commit()
    db.refresh(note)
    return note


@patient_router.get("/tooth-notes/{note_id}/revisions", response_model=NativeNoteHistoryOut)
def tooth_note_revisions(
    patient_id: int, note_id: int, db: Session = Depends(get_db), _user: User = Depends(CLINICAL_VIEW),
    limit: int = Query(default=100, ge=1, le=200), before_revision: int | None = Query(default=None, ge=1),
):
    return native_notes.history(db, _tooth_note_or_404(db, patient_id, note_id), limit=limit, before_revision=before_revision)


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
    if item.plan_id is not None:
        raise HTTPException(409, "Use the revision-aware planning workspace to change this item")
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
        completed_procedure, completion_charge = complete_plan_item(db, item, user)

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
