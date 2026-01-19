from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.r4_treatment_plan import (
    R4Treatment,
    R4TreatmentPlan,
    R4TreatmentPlanItem,
    R4TreatmentPlanReview,
)
from app.services.r4_import.source import R4Source
from app.services.r4_import.types import (
    R4Treatment as R4TreatmentPayload,
    R4TreatmentPlan as R4TreatmentPlanPayload,
    R4TreatmentPlanItem as R4TreatmentPlanItemPayload,
    R4TreatmentPlanReview as R4TreatmentPlanReviewPayload,
)


@dataclass
class TreatmentImportStats:
    treatments_created: int = 0
    treatments_updated: int = 0
    treatments_skipped: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class TreatmentPlanImportStats:
    plans_created: int = 0
    plans_updated: int = 0
    plans_skipped: int = 0
    plans_unmapped_patient_refs: int = 0
    items_created: int = 0
    items_updated: int = 0
    items_skipped: int = 0
    items_missing_plan_refs: int = 0
    reviews_created: int = 0
    reviews_updated: int = 0
    reviews_skipped: int = 0
    reviews_missing_plan_refs: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def import_r4_treatments(
    session: Session,
    source: R4Source,
    actor_id: int,
    legacy_source: str = "r4",
    limit: int | None = None,
) -> TreatmentImportStats:
    stats = TreatmentImportStats()
    for treatment in source.list_treatments(limit=limit):
        _upsert_treatment(session, treatment, actor_id, legacy_source, stats)
    return stats


def import_r4_treatment_plans(
    session: Session,
    source: R4Source,
    actor_id: int,
    legacy_source: str = "r4",
    patients_from: int | None = None,
    patients_to: int | None = None,
    tp_from: int | None = None,
    tp_to: int | None = None,
    limit: int | None = None,
) -> TreatmentPlanImportStats:
    stats = TreatmentPlanImportStats()
    plans_by_key: dict[tuple[int, int], R4TreatmentPlan] = {}
    patients_by_code: dict[int, Patient | None] = {}

    for plan in source.list_treatment_plans(
        patients_from=patients_from,
        patients_to=patients_to,
        tp_from=tp_from,
        tp_to=tp_to,
        limit=limit,
    ):
        row = _upsert_plan(
            session,
            plan,
            actor_id,
            legacy_source,
            stats,
            patients_by_code,
        )
        plans_by_key[(plan.patient_code, plan.tp_number)] = row

    session.flush()

    for item in source.list_treatment_plan_items(
        patients_from=patients_from,
        patients_to=patients_to,
        tp_from=tp_from,
        tp_to=tp_to,
        limit=limit,
    ):
        plan = plans_by_key.get((item.patient_code, item.tp_number))
        if plan is None:
            plan = session.scalar(
                select(R4TreatmentPlan).where(
                    R4TreatmentPlan.legacy_source == legacy_source,
                    R4TreatmentPlan.legacy_patient_code == item.patient_code,
                    R4TreatmentPlan.legacy_tp_number == item.tp_number,
                )
            )
        if plan is None:
            stats.items_missing_plan_refs += 1
            continue
        _upsert_item(session, plan, item, actor_id, legacy_source, stats)

    for review in source.list_treatment_plan_reviews(
        patients_from=patients_from,
        patients_to=patients_to,
        tp_from=tp_from,
        tp_to=tp_to,
        limit=limit,
    ):
        plan = plans_by_key.get((review.patient_code, review.tp_number))
        if plan is None:
            plan = session.scalar(
                select(R4TreatmentPlan).where(
                    R4TreatmentPlan.legacy_source == legacy_source,
                    R4TreatmentPlan.legacy_patient_code == review.patient_code,
                    R4TreatmentPlan.legacy_tp_number == review.tp_number,
                )
            )
        if plan is None:
            stats.reviews_missing_plan_refs += 1
            continue
        _upsert_review(session, plan, review, actor_id, stats)

    return stats


def _upsert_treatment(
    session: Session,
    treatment: R4TreatmentPayload,
    actor_id: int,
    legacy_source: str,
    stats: TreatmentImportStats,
) -> R4Treatment:
    existing = session.scalar(
        select(R4Treatment).where(
            R4Treatment.legacy_source == legacy_source,
            R4Treatment.legacy_treatment_code == treatment.treatment_code,
        )
    )
    updates = {
        "description": treatment.description,
        "short_code": treatment.short_code,
        "default_time": treatment.default_time_minutes,
        "exam": treatment.exam,
        "patient_required": treatment.patient_required,
    }
    if existing:
        updates["updated_by_user_id"] = actor_id
        updated = _apply_updates(existing, updates)
        if updated:
            stats.treatments_updated += 1
        else:
            stats.treatments_skipped += 1
        return existing
    row = R4Treatment(
        legacy_source=legacy_source,
        legacy_treatment_code=treatment.treatment_code,
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
        **updates,
    )
    session.add(row)
    stats.treatments_created += 1
    return row


def _upsert_plan(
    session: Session,
    plan: R4TreatmentPlanPayload,
    actor_id: int,
    legacy_source: str,
    stats: TreatmentPlanImportStats,
    patients_by_code: dict[int, Patient | None],
) -> R4TreatmentPlan:
    existing = session.scalar(
        select(R4TreatmentPlan).where(
            R4TreatmentPlan.legacy_source == legacy_source,
            R4TreatmentPlan.legacy_patient_code == plan.patient_code,
            R4TreatmentPlan.legacy_tp_number == plan.tp_number,
        )
    )
    patient = _resolve_patient(
        session, legacy_source, plan.patient_code, patients_by_code
    )
    mapped_patient_id = patient.id if patient else None
    updates = {
        "legacy_patient_code": plan.patient_code,
        "legacy_tp_number": plan.tp_number,
        "plan_index": plan.plan_index,
        "is_master": plan.is_master,
        "is_current": plan.is_current,
        "is_accepted": plan.is_accepted,
        "creation_date": plan.creation_date,
        "acceptance_date": plan.acceptance_date,
        "completion_date": plan.completion_date,
        "status_code": plan.status_code,
        "reason_id": plan.reason_id,
        "tp_group": plan.tp_group,
    }
    if existing:
        updates["updated_by_user_id"] = actor_id
        if existing.patient_id is None and mapped_patient_id is not None:
            updates["patient_id"] = mapped_patient_id
        elif existing.patient_id is None and mapped_patient_id is None:
            stats.plans_unmapped_patient_refs += 1
        updated = _apply_updates(existing, updates)
        if updated:
            stats.plans_updated += 1
        else:
            stats.plans_skipped += 1
        return existing

    if mapped_patient_id is None:
        stats.plans_unmapped_patient_refs += 1
    updates["patient_id"] = mapped_patient_id
    row = R4TreatmentPlan(
        legacy_source=legacy_source,
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
        **updates,
    )
    session.add(row)
    stats.plans_created += 1
    return row


def _upsert_item(
    session: Session,
    plan: R4TreatmentPlan,
    item: R4TreatmentPlanItemPayload,
    actor_id: int,
    legacy_source: str,
    stats: TreatmentPlanImportStats,
) -> R4TreatmentPlanItem:
    existing = None
    if item.tp_item_key is not None:
        existing = session.scalar(
            select(R4TreatmentPlanItem).where(
                R4TreatmentPlanItem.legacy_source == legacy_source,
                R4TreatmentPlanItem.legacy_tp_item_key == item.tp_item_key,
            )
        )
    if existing is None:
        existing = session.scalar(
            select(R4TreatmentPlanItem).where(
                R4TreatmentPlanItem.treatment_plan_id == plan.id,
                R4TreatmentPlanItem.legacy_tp_item == item.tp_item,
            )
        )
    updates = {
        "treatment_plan_id": plan.id,
        "legacy_tp_item": item.tp_item,
        "legacy_tp_item_key": item.tp_item_key,
        "code_id": item.code_id,
        "tooth": item.tooth,
        "surface": item.surface,
        "appointment_need_id": item.appointment_need_id,
        "completed": item.completed,
        "completed_date": item.completed_date,
        "patient_cost": item.patient_cost,
        "dpb_cost": item.dpb_cost,
        "discretionary_cost": item.discretionary_cost,
        "material": item.material,
        "arch_code": item.arch_code,
    }
    if existing:
        updates["updated_by_user_id"] = actor_id
        updated = _apply_updates(existing, updates)
        if updated:
            stats.items_updated += 1
        else:
            stats.items_skipped += 1
        return existing

    row = R4TreatmentPlanItem(
        legacy_source=legacy_source,
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
        **updates,
    )
    session.add(row)
    stats.items_created += 1
    return row


def _upsert_review(
    session: Session,
    plan: R4TreatmentPlan,
    review: R4TreatmentPlanReviewPayload,
    actor_id: int,
    stats: TreatmentPlanImportStats,
) -> R4TreatmentPlanReview:
    existing = session.scalar(
        select(R4TreatmentPlanReview).where(
            R4TreatmentPlanReview.treatment_plan_id == plan.id,
        )
    )
    updates = {
        "temporary_note": review.temporary_note,
        "reviewed": review.reviewed,
        "last_edit_user": review.last_edit_user,
        "last_edit_date": review.last_edit_date,
    }
    if existing:
        updates["updated_by_user_id"] = actor_id
        updated = _apply_updates(existing, updates)
        if updated:
            stats.reviews_updated += 1
        else:
            stats.reviews_skipped += 1
        return existing

    row = R4TreatmentPlanReview(
        treatment_plan_id=plan.id,
        created_by_user_id=actor_id,
        updated_by_user_id=actor_id,
        **updates,
    )
    session.add(row)
    stats.reviews_created += 1
    return row


def _resolve_patient(
    session: Session,
    legacy_source: str,
    patient_code: int,
    patients_by_code: dict[int, Patient | None],
) -> Patient | None:
    if patient_code in patients_by_code:
        return patients_by_code[patient_code]
    patient = session.scalar(
        select(Patient).where(
            Patient.legacy_source == legacy_source,
            Patient.legacy_id == str(patient_code),
        )
    )
    patients_by_code[patient_code] = patient
    return patient


def _apply_updates(model, updates: dict) -> bool:
    changed = False
    for field, value in updates.items():
        if getattr(model, field) != value:
            setattr(model, field, value)
            changed = True
    return changed
