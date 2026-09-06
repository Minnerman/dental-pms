"""Native planning with frozen diagnosis/fees and an explicit completion boundary."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib

from fastapi import HTTPException
from sqlalchemy import and_, func, nullslast, or_, select, text
from sqlalchemy.orm import lazyload

from app.core.settings import settings
from app.models.audit_log import AuditLog
from app.models.clinical import TreatmentPlanItem, TreatmentPlanStatus
from app.models.patient import Patient
from app.models.r4_charting_canonical import R4ChartingCanonicalRecord
from app.models.r4_patient_mapping import R4PatientMapping
from app.models.r4_treatment_plan import R4Treatment
from app.models.treatment import Treatment, TreatmentFee, FeeType
from app.models.treatment_planning import PatientTreatmentPlan, TreatmentPlanItemRevision, PlanningMutationReceipt
from app.models.user import Role
from app.routers.clinical import PLAN_TRANSITIONS, _tooth_conditions_out, _user_has_capability
from app.schemas.clinical import TreatmentPlanItemOut, schematic_root_count
from app.schemas.treatment_planning import PlanningItemOut
from app.schemas.r4_charting import R4ToothStateOut, R4ToothStateEntryOut, R4ToothStateRestorationOut
from app.services.audit import log_event
from app.services.clinical_completion import complete_plan_item
from app.services.native_notes import request_fingerprint
from app.services.r4_charting.tooth_state_engine import build_tooth_state_engine_row, project_tooth_state_rows


def patient(db, patient_id, *, lock=False):
    query = select(Patient).where(Patient.id == patient_id, Patient.deleted_at.is_(None))
    if lock:
        query = query.with_for_update(of=Patient)
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "Patient not found")
    return row


def replay(db, user, request_id, action, payload):
    if not request_id.strip():
        raise HTTPException(422, "Request-Id must not be blank")
    key = int.from_bytes(hashlib.sha256(f"planning:{user.id}:{request_id}".encode()).digest()[:8], "big", signed=True)
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
    receipt = db.scalar(select(PlanningMutationReceipt).where(
        PlanningMutationReceipt.actor_user_id == user.id, PlanningMutationReceipt.request_id == request_id,
    ))
    if receipt is not None:
        if receipt.action != action or receipt.fingerprint != request_fingerprint(payload):
            raise HTTPException(409, "Request-Id was already used for a different planning operation")
        return receipt.target_id
    if db.scalar(select(AuditLog.id).where(AuditLog.actor_user_id == user.id, AuditLog.request_id == request_id).limit(1)) is not None:
        raise HTTPException(409, "Request-Id was already used; review the earlier operation")
    return None


def receipt(db, user, request_id, action, payload, target_id):
    db.add(PlanningMutationReceipt(actor_user_id=user.id, request_id=request_id,
        action=action, fingerprint=request_fingerprint(payload), target_id=target_id))


def legacy_snapshot(db, row, user):
    # This only queries already-imported PostgreSQL tables. No SQL Server client.
    if user.role == Role.external or not settings.feature_charting_viewer:
        return None, "unavailable", "Cached legacy chart access is unavailable"
    if row.legacy_source != "r4" or not (row.legacy_id or "").isdigit():
        return None, "unavailable", "No explicit legacy patient mapping"
    code = int(row.legacy_id)
    # Retain the viewer's literal source/code mapping, but never freeze records
    # whose independently stored identity contradicts it. No name matching or
    # remapping is attempted; original imported rows remain untouched.
    conflicting_mapping = db.scalar(select(R4PatientMapping.id).where(
        R4PatientMapping.legacy_source == "r4", or_(
            and_(R4PatientMapping.legacy_patient_code == code, R4PatientMapping.patient_id != row.id),
            and_(R4PatientMapping.patient_id == row.id, R4PatientMapping.legacy_patient_code != code),
        )).limit(1))
    conflicting_record = db.scalar(select(R4ChartingCanonicalRecord.id).where(
        R4ChartingCanonicalRecord.legacy_patient_code == code,
        R4ChartingCanonicalRecord.patient_id.is_not(None), R4ChartingCanonicalRecord.patient_id != row.id,
        R4ChartingCanonicalRecord.domain.in_(("restorative_treatment", "restorative_treatments", "treatment_plan_item", "treatment_plan_items")),
    ).limit(1))
    if conflicting_mapping is not None or conflicting_record is not None:
        return None, "unavailable", "Cached legacy patient linkage needs review"
    query = (
        select(R4ChartingCanonicalRecord, R4Treatment.description.label("code_label"))
        .outerjoin(R4Treatment, and_(R4Treatment.legacy_source == "r4", R4Treatment.legacy_treatment_code == R4ChartingCanonicalRecord.code_id))
        .where(R4ChartingCanonicalRecord.legacy_patient_code == code,
               or_(R4ChartingCanonicalRecord.patient_id.is_(None), R4ChartingCanonicalRecord.patient_id == row.id),
               R4ChartingCanonicalRecord.domain.in_(("restorative_treatment", "restorative_treatments", "treatment_plan_item", "treatment_plan_items")))
        .order_by(nullslast(R4ChartingCanonicalRecord.recorded_at.desc()), R4ChartingCanonicalRecord.r4_source_id.desc(), R4ChartingCanonicalRecord.id.desc())
        .limit(5001)
    )
    rows = db.execute(query).all()
    engine_rows = [engine for record, label in rows[:5000] if (engine := build_tooth_state_engine_row(record, label)) is not None]
    projected = project_tooth_state_rows(engine_rows)
    value = R4ToothStateOut(patient_id=row.id, legacy_patient_code=code, teeth={
        tooth: R4ToothStateEntryOut(missing=state.missing, extracted=state.extracted,
            restorations=[R4ToothStateRestorationOut(type=value.type, surfaces=list(value.surfaces), meta=value.meta) for value in state.restorations])
        for tooth, state in projected.items()
    }).model_dump(mode="json")
    partial = len(rows) > 5000
    return value, "partial" if partial else "captured", "Latest 5000 cached source rows; older rows not captured" if partial else None


def capture(db, row, user):
    legacy, coverage, reason = legacy_snapshot(db, row, user)
    return {"version": 1, "captured_at": datetime.now(timezone.utc).isoformat(),
            "native": _tooth_conditions_out(db, row.id).model_dump(mode="json"), "legacy": legacy,
            "coverage": {"native": "captured", "legacy": coverage, "legacy_reason": reason}}


def item_out(item):
    return PlanningItemOut(**TreatmentPlanItemOut.model_validate(item).model_dump(),
        treatment_id=item.treatment_id, revision=item.revision,
        completed_procedure_id=item.completed_procedure_id, **item.planning_details)


def get_workspace(db, patient_id, user):
    patient(db, patient_id)
    plan = db.scalar(select(PatientTreatmentPlan).where(PatientTreatmentPlan.patient_id == patient_id))
    earlier = select(TreatmentPlanItem).where(TreatmentPlanItem.patient_id == patient_id, TreatmentPlanItem.plan_id.is_(None))
    earlier_total = db.scalar(select(func.count()).select_from(earlier.subquery()))
    result = {"patient_id": patient_id, "plan": None,
              "earlier_items": list(db.scalars(earlier.order_by(TreatmentPlanItem.created_at.desc(), TreatmentPlanItem.id.desc()).limit(100))),
              "earlier_items_total": earlier_total}
    if plan is not None:
        frozen = deepcopy(plan.snapshot)
        if user.role == Role.external or not settings.feature_charting_viewer:
            frozen["legacy"] = None
            frozen["coverage"].update(legacy="unavailable", legacy_reason="Cached legacy chart access is unavailable")
        result["plan"] = {"id": plan.id, "created_at": plan.created_at, "created_by": plan.created_by,
            "snapshot": frozen, "items": [item_out(item) for item in db.scalars(select(TreatmentPlanItem)
                .where(TreatmentPlanItem.plan_id == plan.id).order_by(TreatmentPlanItem.created_at, TreatmentPlanItem.id))]}
    return result


def catalogue_row(treatment, category, fee):
    values = {"id": treatment.id, "code": treatment.code, "name": treatment.name,
        "description": treatment.description, "default_duration_minutes": treatment.default_duration_minutes,
        "patient_category": category.value,
        "fee": {"type": fee.fee_type.value if fee else "UNAVAILABLE",
                "amount_pence": fee.amount_pence if fee else None,
                "min_amount_pence": fee.min_amount_pence if fee else None,
                "max_amount_pence": fee.max_amount_pence if fee else None,
                "notes": fee.notes if fee else None}}
    # Include all fields used by the quote, not unrelated patient contact data.
    return {**values, "quote_token": request_fingerprint(values)}


def catalogue(db, patient_id, q, limit, offset):
    row = patient(db, patient_id)
    query = select(Treatment).options(lazyload(Treatment.fees)).where(Treatment.is_active.is_(True))
    if q.strip():
        term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(or_(Treatment.name.ilike(f"%{term}%", escape="\\"), Treatment.code.ilike(f"%{term}%", escape="\\")))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    treatments = list(db.scalars(query.order_by(Treatment.name, Treatment.id).offset(offset).limit(limit)))
    fees = {fee.treatment_id: fee for fee in db.scalars(select(TreatmentFee).where(
        TreatmentFee.treatment_id.in_([item.id for item in treatments]), TreatmentFee.patient_category == row.patient_category))}
    return {"patient_id": patient_id, "patient_category": row.patient_category.value, "currency": "GBP",
            "total": total, "items": [catalogue_row(item, row.patient_category, fees.get(item.id)) for item in treatments]}


def resolved_fee(quote, mode, amount, reason):
    fee = quote["fee"]
    reason = (reason or "").strip() or None
    if mode == "catalogue":
        if fee["type"] != "FIXED" or fee["amount_pence"] is None:
            raise HTTPException(422, "This catalogue fee needs an explicitly agreed amount or waiver")
        if amount is not None and amount != fee["amount_pence"]:
            raise HTTPException(422, "Catalogue amount changed; choose an override with a reason")
        if reason:
            raise HTTPException(422, "A catalogue fee has no override reason")
        amount = fee["amount_pence"]
    elif mode == "waived":
        if amount not in (None, 0) or not reason:
            raise HTTPException(422, "A waived fee must be zero and have a reason")
        amount = 0
    else:
        if amount is None or amount <= 0:
            raise HTTPException(422, "Enter a positive agreed fee, or explicitly waive it with a reason")
        if mode == "override" and not reason:
            raise HTTPException(422, "A fee override needs a reason")
        if mode == "agreed":
            if fee["type"] == "FIXED":
                raise HTTPException(422, "Use the catalogue fee or a reasoned override")
            if fee["type"] == "RANGE":
                low, high = fee["min_amount_pence"], fee["max_amount_pence"]
                if low is None or high is None or not low <= amount <= high:
                    raise HTTPException(422, "An amount outside the catalogue range needs a reasoned override")
            elif not reason:
                raise HTTPException(422, "An unspecified catalogue fee needs an agreed-fee reason")
    if amount < 0 or amount > 100_000_000:
        raise HTTPException(422, "Fee is outside the supported range")
    return amount, reason


def validate_snapshot_target(snapshot, target):
    if target.level not in {"root", "surface"}:
        # A missing site's future crown/bridge/denture/implant is a legitimate
        # proposal, not a declaration that the biological tooth is present.
        return
    native = snapshot["native"]["teeth"].get(target.tooth, {})
    condition = native.get("condition")
    crown = native.get("crown_observation") or {}
    if condition in {"missing", "implant", "unerupted"} or native.get("bridge_role") == "pontic" or crown.get("kind") in {"denture_cocr", "denture_acrylic"}:
        raise HTTPException(422, "The frozen chart has no eligible natural tooth area at this target")
    if target.level == "surface" and crown.get("kind") == "fractured":
        raise HTTPException(422, "The frozen chart has no drawable natural crown surfaces at this target")
    # Match the existing renderer's explicit FDI mapping, without guessing any
    # primary or unmapped source code. A native presence/reset override wins.
    if condition is None:
        quadrant = {"UR": 1, "UL": 2, "LL": 3, "LR": 4}[target.tooth[:2]]
        legacy = (snapshot.get("legacy") or {}).get("teeth", {}).get(f"{quadrant}{target.tooth[-1]}", {})
        dentition = native.get("dentition") or "permanent"
        root_count = schematic_root_count(target.tooth, dentition)
        current_root = any(str(index) in native.get("root_observations", {}) for index in range(1, root_count + 1))
        current_crown = native.get("crown_observation") is not None
        current_surface = bool(native.get("surface_observations"))
        legacy_types = {restoration.get("type") for restoration in legacy.get("restorations", [])}
        legacy_absence = legacy.get("missing") or legacy.get("extracted") or "extraction" in legacy_types
        absence_overridden = current_root or current_crown or (target.level == "surface" and current_surface)
        unresolved_implant = "implant" in legacy_types and not current_root and dentition != "deciduous"
        if (legacy_absence and not absence_overridden) or unresolved_implant:
            raise HTTPException(422, "The frozen cached chart has no eligible natural tooth area at this target")


def save_revision(db, item, user):
    db.flush()
    db.add(TreatmentPlanItemRevision(item_id=item.id, revision=item.revision,
        snapshot=item_out(item).model_dump(mode="json"), recorded_by_user_id=user.id))


def start(db, patient_id, user, request_id):
    row = patient(db, patient_id, lock=True)
    action, request = "clinical.planning.started", {"patient_id": patient_id}
    repeated = replay(db, user, request_id, action, request)
    if repeated is not None:
        return get_workspace(db, patient_id, user)
    plan = db.scalar(select(PatientTreatmentPlan).where(PatientTreatmentPlan.patient_id == patient_id))
    if plan is None:
        plan = PatientTreatmentPlan(patient_id=patient_id, snapshot=capture(db, row, user), created_by_user_id=user.id, updated_by_user_id=user.id)
        db.add(plan)
        db.flush()
        log_event(db, actor=user, action=action, entity_type="patient", entity_id=str(patient_id), request_id=request_id,
                  after_data={"plan_id": plan.id, "snapshot_version": 1, "captured_at": plan.snapshot["captured_at"]})
    receipt(db, user, request_id, action, request, plan.id)
    db.commit()
    return get_workspace(db, patient_id, user)


def create_item(db, patient_id, payload, user, request_id):
    row = patient(db, patient_id, lock=True)
    action, request = "clinical.planning.item.created", {"patient_id": patient_id, **payload.model_dump(mode="json")}
    repeated = replay(db, user, request_id, action, request)
    if repeated is not None:
        return item_out(db.get(TreatmentPlanItem, repeated))
    plan = db.scalar(select(PatientTreatmentPlan).where(PatientTreatmentPlan.patient_id == patient_id))
    if plan is None:
        raise HTTPException(409, "Start the planning workspace first")
    validate_snapshot_target(plan.snapshot, payload.target)
    # SHARE freezes the quoted treatment while remaining compatible with FK
    # checks by the existing fee-replacement endpoint (delete then insert).
    treatment = db.scalar(select(Treatment).options(lazyload(Treatment.fees)).where(Treatment.id == payload.treatment_id, Treatment.is_active.is_(True)).with_for_update(read=True, of=Treatment))
    if treatment is None:
        raise HTTPException(409, "Treatment is no longer active; refresh the catalogue")
    if not treatment.name.strip():
        raise HTTPException(409, "The catalogue treatment needs a name before it can be planned")
    fee = db.scalar(select(TreatmentFee).where(TreatmentFee.treatment_id == treatment.id, TreatmentFee.patient_category == row.patient_category)
        .with_for_update(read=True, of=TreatmentFee).execution_options(populate_existing=True))
    quote = catalogue_row(treatment, row.patient_category, fee)
    if quote["quote_token"] != payload.quote_token:
        raise HTTPException(409, "Catalogue or patient category changed; review the current quote")
    amount, reason = resolved_fee(quote, payload.fee_mode, payload.fee_pence, payload.fee_reason)
    # Keep legacy string surface semantics unchanged. Native P is retained in
    # the explicit target and mapped only for the legacy procedure field.
    legacy_surfaces = "".join("L" if value == "P" else value for value in payload.target.surfaces) or None
    item = TreatmentPlanItem(patient_id=patient_id, plan_id=plan.id, treatment_id=treatment.id,
        tooth=payload.target.tooth, surface=legacy_surfaces,
        procedure_code=treatment.code or f"CATALOGUE:{treatment.id}", description=treatment.name,
        fee_pence=amount, status=TreatmentPlanStatus.proposed, revision=1,
        planning_details={"target": payload.target.model_dump(), "drawing_kind": payload.drawing_kind,
                          "catalogue_snapshot": quote, "fee_mode": payload.fee_mode, "fee_reason": reason},
        created_by_user_id=user.id, updated_by_user_id=user.id)
    db.add(item)
    save_revision(db, item, user)
    log_event(db, actor=user, action=action, entity_type="patient", entity_id=str(patient_id), request_id=request_id,
        after_data={"plan_id": plan.id, "treatment_plan_item_id": item.id, "revision": 1, "treatment_id": treatment.id, "fee_pence": amount, "fee_mode": payload.fee_mode})
    receipt(db, user, request_id, action, request, item.id)
    db.commit()
    db.refresh(item)
    return item_out(item)


def update_item(db, patient_id, item_id, payload, user, request_id):
    patient(db, patient_id, lock=True)
    item = db.scalar(select(TreatmentPlanItem).where(TreatmentPlanItem.id == item_id,
        TreatmentPlanItem.patient_id == patient_id, TreatmentPlanItem.plan_id.is_not(None)).with_for_update(of=TreatmentPlanItem))
    if item is None:
        raise HTTPException(404, "Planning item not found")
    action, request = "clinical.planning.item.updated", {"patient_id": patient_id, "item_id": item_id, **payload.model_dump(mode="json", exclude_unset=True)}
    # Completion replay is still subject to its billing permission.
    if payload.status == TreatmentPlanStatus.completed:
        if not _user_has_capability(db, user.id, "billing.payments.write"):
            raise HTTPException(403, "Forbidden")
        if not payload.confirm_finance:
            raise HTTPException(422, "Confirm completion and its patient-account charge first")
    repeated = replay(db, user, request_id, action, request)
    if repeated is not None:
        return item_out(item)
    if item.revision != payload.expected_revision:
        raise HTTPException(409, "Planning item changed; reload and review before saving")
    before = item_out(item).model_dump(mode="json")
    details = deepcopy(item.planning_details)
    amount, next_status = item.fee_pence, payload.status or item.status
    if payload.fee_mode is not None:
        amount, reason = resolved_fee(details["catalogue_snapshot"], payload.fee_mode, payload.fee_pence, payload.fee_reason)
        details.update(fee_mode=payload.fee_mode, fee_reason=reason)
    changed = amount != item.fee_pence or details != item.planning_details or next_status != item.status
    if not changed:
        receipt(db, user, request_id, action, request, item.id)
        db.commit()
        return item_out(item)
    if item.status in {TreatmentPlanStatus.completed, TreatmentPlanStatus.cancelled, TreatmentPlanStatus.declined}:
        raise HTTPException(409, "Final treatment plan items cannot be edited")
    if next_status != item.status and next_status not in PLAN_TRANSITIONS[item.status]:
        raise HTTPException(409, "Treatment plan status transition is not permitted")
    previous_status = item.status
    item.fee_pence, item.planning_details, item.status = amount, details, next_status
    item.revision += 1
    item.updated_by_user_id = user.id
    procedure = charge = None
    if next_status == TreatmentPlanStatus.completed:
        if amount is None:
            raise HTTPException(422, "Agree or waive the fee before completing treatment")
        procedure, charge = complete_plan_item(db, item, user)
        item.completed_procedure_id = procedure.id
    save_revision(db, item, user)
    log_event(db, actor=user, action=action, entity_type="patient", entity_id=str(patient_id), request_id=request_id,
        before_data={"treatment_plan_item_id": item.id, "revision": before["revision"], "status": previous_status.value, "fee_pence": before["fee_pence"], "fee_mode": before["fee_mode"]},
        after_data={"treatment_plan_item_id": item.id, "revision": item.revision, "status": item.status.value, "fee_pence": amount, "fee_mode": details["fee_mode"]})
    if procedure is not None:
        log_event(db, actor=user, action="clinical.procedure.completed", entity_type="patient", entity_id=str(patient_id), request_id=request_id,
            after_data={"procedure_id": procedure.id, "treatment_plan_item_id": item.id, "tooth": item.tooth, "surface": item.surface, "procedure_code": item.procedure_code, "fee_pence": amount})
    if charge is not None:
        log_event(db, actor=user, action="ledger.charge_recorded", entity_type="patient", entity_id=str(patient_id), request_id=request_id,
            after_data={"ledger_entry_id": charge.id, "treatment_plan_item_id": item.id, "amount_pence": amount})
    receipt(db, user, request_id, action, request, item.id)
    db.commit()
    db.refresh(item)
    return item_out(item)


def item_history(db, patient_id, item_id, limit, before_revision):
    patient(db, patient_id)
    item = db.scalar(select(TreatmentPlanItem).where(TreatmentPlanItem.id == item_id,
        TreatmentPlanItem.patient_id == patient_id, TreatmentPlanItem.plan_id.is_not(None)))
    if item is None:
        raise HTTPException(404, "Planning item not found")
    query = select(TreatmentPlanItemRevision).where(TreatmentPlanItemRevision.item_id == item_id)
    if before_revision is not None:
        query = query.where(TreatmentPlanItemRevision.revision < before_revision)
    rows = list(db.scalars(query.order_by(TreatmentPlanItemRevision.revision.desc()).limit(limit + 1)))
    return {"items": [{"revision": row.revision, "snapshot": row.snapshot, "recorded_at": row.recorded_at,
        "recorded_by": {"id": row.recorded_by.id, "name": row.recorded_by.full_name}} for row in rows[:limit]],
        "next_before_revision": rows[limit - 1].revision if len(rows) > limit else None}
