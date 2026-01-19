from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
import os
import time

from sqlalchemy import func, select
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
    batch_size: int = 1000,
    sleep_ms: int = 0,
    progress_every: int = 5000,
    progress_enabled: bool = False,
) -> TreatmentPlanImportStats:
    stats = TreatmentPlanImportStats()
    patients_by_code: dict[int, Patient | None] = {}
    started_at = time.monotonic()
    plans_processed = 0
    items_processed = 0
    batch_size = max(1, batch_size)

    def process_plan_batch(batch: list[R4TreatmentPlanPayload]) -> None:
        nonlocal plans_processed
        for plan in batch:
            _upsert_plan(
                session,
                plan,
                actor_id,
                legacy_source,
                stats,
                patients_by_code,
            )
            plans_processed += 1
            _maybe_emit_progress(
                progress_enabled,
                progress_every,
                started_at,
                stats,
                "plans",
                plans_processed,
                items_processed,
            )
        session.flush()
        session.expunge_all()
        _maybe_sleep(sleep_ms)

    batch: list[R4TreatmentPlanPayload] = []
    for plan in source.list_treatment_plans(
        patients_from=patients_from,
        patients_to=patients_to,
        tp_from=tp_from,
        tp_to=tp_to,
        limit=limit,
    ):
        batch.append(plan)
        if len(batch) >= batch_size:
            process_plan_batch(batch)
            batch = []
    if batch:
        process_plan_batch(batch)

    def process_item_batch(batch: list[R4TreatmentPlanItemPayload]) -> None:
        nonlocal items_processed
        for item in batch:
            plan = session.scalar(
                select(R4TreatmentPlan).where(
                    R4TreatmentPlan.legacy_source == legacy_source,
                    R4TreatmentPlan.legacy_patient_code == item.patient_code,
                    R4TreatmentPlan.legacy_tp_number == item.tp_number,
                )
            )
            if plan is None:
                stats.items_missing_plan_refs += 1
                items_processed += 1
                _maybe_emit_progress(
                    progress_enabled,
                    progress_every,
                    started_at,
                    stats,
                    "items",
                    plans_processed,
                    items_processed,
                )
                continue
            _upsert_item(session, plan, item, actor_id, legacy_source, stats)
            items_processed += 1
            _maybe_emit_progress(
                progress_enabled,
                progress_every,
                started_at,
                stats,
                "items",
                plans_processed,
                items_processed,
            )
        session.flush()
        session.expunge_all()
        _maybe_sleep(sleep_ms)

    batch = []
    for item in source.list_treatment_plan_items(
        patients_from=patients_from,
        patients_to=patients_to,
        tp_from=tp_from,
        tp_to=tp_to,
        limit=limit,
    ):
        batch.append(item)
        if len(batch) >= batch_size:
            process_item_batch(batch)
            batch = []
    if batch:
        process_item_batch(batch)

    for review in source.list_treatment_plan_reviews(
        patients_from=patients_from,
        patients_to=patients_to,
        tp_from=tp_from,
        tp_to=tp_to,
        limit=limit,
    ):
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


def summarize_r4_treatment_plans(
    session: Session, legacy_source: str = "r4"
) -> dict[str, object]:
    total_plans = session.scalar(
        select(func.count()).select_from(R4TreatmentPlan).where(
            R4TreatmentPlan.legacy_source == legacy_source
        )
    )
    total_items = session.scalar(
        select(func.count()).select_from(R4TreatmentPlanItem).where(
            R4TreatmentPlanItem.legacy_source == legacy_source
        )
    )
    null_patient = session.scalar(
        select(func.count()).select_from(R4TreatmentPlan).where(
            R4TreatmentPlan.legacy_source == legacy_source,
            R4TreatmentPlan.patient_id.is_(None),
        )
    )
    min_date = session.scalar(
        select(func.min(R4TreatmentPlan.creation_date)).where(
            R4TreatmentPlan.legacy_source == legacy_source
        )
    )
    max_date = session.scalar(
        select(func.max(R4TreatmentPlan.creation_date)).where(
            R4TreatmentPlan.legacy_source == legacy_source
        )
    )
    top_codes = session.execute(
        select(R4TreatmentPlanItem.code_id, func.count().label("count"))
        .where(
            R4TreatmentPlanItem.legacy_source == legacy_source,
            R4TreatmentPlanItem.code_id.is_not(None),
        )
        .group_by(R4TreatmentPlanItem.code_id)
        .order_by(func.count().desc())
        .limit(20)
    ).all()
    return {
        "legacy_source": legacy_source,
        "plans_total": int(total_plans or 0),
        "items_total": int(total_items or 0),
        "plans_with_null_patient_id": int(null_patient or 0),
        "min_creation_date": min_date.isoformat() if min_date else None,
        "max_creation_date": max_date.isoformat() if max_date else None,
        "top_code_ids": [
            {"code_id": int(code_id), "count": int(count)}
            for code_id, count in top_codes
        ],
    }


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
        "creation_date": _normalize_datetime(plan.creation_date),
        "acceptance_date": _normalize_datetime(plan.acceptance_date),
        "completion_date": _normalize_datetime(plan.completion_date),
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
        updated = _apply_updates(existing, updates, debug_label="plan")
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
        "completed_date": _normalize_datetime(item.completed_date),
        "patient_cost": _normalize_money(item.patient_cost),
        "dpb_cost": _normalize_money(item.dpb_cost),
        "discretionary_cost": _normalize_money(item.discretionary_cost),
        "material": _normalize_string(item.material),
        "arch_code": item.arch_code,
    }
    if existing:
        updates["updated_by_user_id"] = actor_id
        updated = _apply_updates(existing, updates, debug_label="item")
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
        "last_edit_user": _normalize_string(review.last_edit_user),
        "last_edit_date": _normalize_datetime(review.last_edit_date),
    }
    if existing:
        updates["updated_by_user_id"] = actor_id
        updated = _apply_updates(existing, updates, debug_label="review")
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


def _apply_updates(model, updates: dict, debug_label: str | None = None) -> bool:
    changed_fields: list[str] = []
    for field, value in updates.items():
        if getattr(model, field) != value:
            changed_fields.append(field)
            setattr(model, field, value)
    if changed_fields and debug_label and _debug_diffs_enabled():
        print(f"r4_import_diff {debug_label} fields={','.join(changed_fields)}")
    return bool(changed_fields)


def _debug_diffs_enabled() -> bool:
    return os.getenv("R4_IMPORT_DEBUG_DIFFS") == "1"


def _maybe_emit_progress(
    enabled: bool,
    progress_every: int,
    started_at: float,
    stats: TreatmentPlanImportStats,
    phase: str,
    plans_processed: int,
    items_processed: int,
) -> None:
    if not enabled or progress_every <= 0:
        return
    if phase == "plans":
        if plans_processed % progress_every != 0:
            return
    else:
        if items_processed % progress_every != 0:
            return
    elapsed = max(time.monotonic() - started_at, 0.001)
    payload = {
        "event": "r4_import_progress",
        "phase": phase,
        "elapsed_seconds": round(elapsed, 2),
        "plans_processed": plans_processed,
        "items_processed": items_processed,
        "plans_per_second": round(plans_processed / elapsed, 2),
        "items_per_second": round(items_processed / elapsed, 2),
        "plans_created": stats.plans_created,
        "plans_updated": stats.plans_updated,
        "plans_skipped": stats.plans_skipped,
        "items_created": stats.items_created,
        "items_updated": stats.items_updated,
        "items_skipped": stats.items_skipped,
    }
    print(json.dumps(payload, sort_keys=True))


def _maybe_sleep(sleep_ms: int) -> None:
    if sleep_ms <= 0:
        return
    time.sleep(sleep_ms / 1000.0)


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    microseconds = (value.microsecond // 1000) * 1000
    return value.replace(microsecond=microseconds)


def _normalize_money(value: float | Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _normalize_string(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.rstrip()
    return cleaned or None
