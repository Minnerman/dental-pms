"""One date-effective catalogue fee resolver, with immutable native revisions."""
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import hashlib
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import Date, case, func, literal, select, text
from sqlalchemy.orm import lazyload

from app.models.audit_log import AuditLog
from app.models.patient import PatientCategory
from app.models.treatment import FeeType, Treatment, TreatmentFee, TreatmentFeeVersion
from app.schemas.treatment import TreatmentOut
from app.services.audit import log_event
from app.services.native_notes import request_fingerprint

LEVELS = ("tooth", "root", "crown", "surface", "general")
FEE_FIELDS = ("fee_type", "amount_pence", "min_amount_pence", "max_amount_pence", "notes")
ROUTINE_DEFAULTS = {
    "tooth": ("Simple extraction", "Surgical extraction", "Implant"),
    "root": ("Removal of old root canal", "Root canal", "Post and/or Core"),
    "crown": ("White crown", "Bridge unit", "Small acrylic denture (1–3 teeth)",
              "Large acrylic denture (more than 3 teeth)", "Cobalt-chrome denture", "Veneer"),
    "surface": ("White filling", "Gold inlay"),
    "general": ("Examination", "Examination with dental hygiene", "Dental hygiene", "Home visit examination",
                "All on 4", "Overdenture (snap-on denture)"),
}


def practice_today(now=None):
    return (now or datetime.now(timezone.utc)).astimezone(ZoneInfo("Europe/London")).date()


@dataclass(frozen=True)
class EffectiveFee:
    id: int
    treatment_id: int
    patient_category: PatientCategory
    fee_type: FeeType | None
    amount_pence: int | None
    min_amount_pence: int | None
    max_amount_pence: int | None
    notes: str | None
    version_id: int | None = None
    effective_from: date | None = None
    revision: int = 0
    source: str = "legacy"
    recorded_at: datetime | None = None
    recorded_by: dict | None = None


@dataclass
class FeeState:
    current: EffectiveFee | None = None
    baseline: EffectiveFee | None = None
    scheduled: list[EffectiveFee] = field(default_factory=list)
    revision: int = 0


def resolved(row):
    values = {name: getattr(row, name) for name in ("id", "treatment_id", "patient_category", *FEE_FIELDS)}
    if isinstance(row, TreatmentFeeVersion):
        values.update(version_id=row.id, effective_from=row.effective_from, revision=row.revision, source="version",
            recorded_at=row.recorded_at, recorded_by={"id": row.recorded_by_user_id, "name": row.recorded_by.full_name})
    return EffectiveFee(**values)


def fee_projection(fee):
    if fee is None:
        return None
    return {key: getattr(fee, key) for key in ("version_id", "effective_from", "revision", "source", *FEE_FIELDS,
                                               "recorded_at", "recorded_by")}


def fee_states(db, treatment_ids, category=None, *, today=None, lock_baseline=False):
    """Two bounded bulk queries: undated baseline plus current/future winners.

    SQL ranks all past entries into one bucket and each future date into its
    own bucket. Superseded rows/past history are not loaded into an index page.
    MAX revision is calculated before filtering to protect the whole timeline.
    """
    if not treatment_ids:
        return {}
    states = {}
    baseline = select(TreatmentFee).where(TreatmentFee.treatment_id.in_(treatment_ids))
    if category is not None:
        baseline = baseline.where(TreatmentFee.patient_category == category)
    if lock_baseline:
        baseline = baseline.with_for_update(read=True, of=TreatmentFee).execution_options(populate_existing=True)
    for row in db.scalars(baseline):
        value = resolved(row)
        states[(row.treatment_id, row.patient_category)] = FeeState(current=value, baseline=value)
    # For a new quote, take the date after any legacy fee-row lock wait.
    today = today or practice_today()
    model = TreatmentFeeVersion
    bucket = case((model.effective_from <= today, literal(date.min, type_=Date())), else_=model.effective_from)
    ranked = select(model.id,
        func.row_number().over(partition_by=(model.treatment_id, model.patient_category, bucket),
            order_by=(model.effective_from.desc(), model.revision.desc())).label("position"),
        func.max(model.revision).over(partition_by=(model.treatment_id, model.patient_category)).label("latest_revision"),
    ).where(model.treatment_id.in_(treatment_ids))
    if category is not None:
        ranked = ranked.where(model.patient_category == category)
    ranked = ranked.subquery()
    for row, latest_revision in db.execute(select(model, ranked.c.latest_revision).join(ranked, ranked.c.id == model.id)
            .where(ranked.c.position == 1).order_by(model.effective_from, model.revision)):
        state = states.setdefault((row.treatment_id, row.patient_category), FeeState())
        state.revision = latest_revision
        if row.effective_from <= today:
            state.current = resolved(row)
        else:
            state.scheduled.append(resolved(row))
    return states


def treatment_order():
    return (case({level: index for index, level in enumerate(LEVELS)}, value=Treatment.level, else_=len(LEVELS)),
            Treatment.display_order, func.lower(Treatment.name), Treatment.id)


def get_treatment(db, treatment_id, *, lock=False):
    query = select(Treatment).options(lazyload(Treatment.fees)).where(Treatment.id == treatment_id)
    if lock:
        query = query.with_for_update(of=Treatment)
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "Treatment not found")
    return row


def index_item(row, state):
    return {**TreatmentOut.model_validate(row).model_dump(), "current_fee": fee_projection(state.current),
            "scheduled_fees": [fee_projection(fee) for fee in state.scheduled], "fee_revision": state.revision}


def treatment_index(db, category, include_inactive):
    today = practice_today()
    query = select(Treatment).options(lazyload(Treatment.fees)).order_by(*treatment_order())
    if not include_inactive:
        query = query.where(Treatment.is_active.is_(True))
    treatments = list(db.scalars(query))
    states = fee_states(db, [row.id for row in treatments], category, today=today)
    return {"practice_today": today, "timezone": "Europe/London", "currency": "GBP", "patient_category": category,
            "items": [index_item(row, states.get((row.id, category), FeeState())) for row in treatments]}


def current_fees(db, treatment_id):
    get_treatment(db, treatment_id)
    states = fee_states(db, [treatment_id])
    return [state.current for _, state in sorted(states.items(), key=lambda pair: pair[0][1].value)
            if state.current is not None and state.current.fee_type is not None]


def append_version(db, row, category, state, values, effective_from, actor, *, request_id=None, fingerprint=None):
    version = TreatmentFeeVersion(treatment_id=row.id, patient_category=category, revision=state.revision + 1,
        effective_from=effective_from, recorded_by_user_id=actor.id, request_id=request_id,
        request_fingerprint=fingerprint, **values)
    db.add(version)
    db.flush()
    log_event(db, actor=actor, action="treatment.fee.changed", entity_type="treatment", entity_id=str(row.id), request_id=request_id,
        before_data={"patient_category": category.value, "fee_revision": state.revision},
        after_data={"patient_category": category.value, "fee_revision": version.revision, "version_id": version.id,
            "effective_from": effective_from.isoformat(), **{key: (value.value if isinstance(value, FeeType) else value)
                for key, value in values.items() if key != "notes"}})
    return version


def change_fee(db, treatment_id, payload, actor, request_id):
    if not request_id.strip():
        raise HTTPException(422, "Request-Id must not be blank")
    lock_key = int.from_bytes(hashlib.sha256(f"treatment-fee:{actor.id}:{request_id}".encode()).digest()[:8], "big", signed=True)
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
    row = get_treatment(db, treatment_id, lock=True)
    fingerprint = request_fingerprint({"treatment_id": treatment_id, **payload.model_dump(mode="json")})
    duplicate = db.scalar(select(TreatmentFeeVersion).where(TreatmentFeeVersion.recorded_by_user_id == actor.id,
        TreatmentFeeVersion.request_id == request_id))
    today = practice_today()
    state = fee_states(db, [row.id], payload.patient_category, today=today).get((row.id, payload.patient_category), FeeState())
    if duplicate is not None:
        if duplicate.request_fingerprint != fingerprint:
            raise HTTPException(409, "Request-Id was used for a different fee change")
        return index_item(row, state)
    if db.scalar(select(AuditLog.id).where(AuditLog.actor_user_id == actor.id, AuditLog.request_id == request_id).limit(1)) is not None:
        raise HTTPException(409, "Request-Id was used for another operation")
    if payload.expected_revision != state.revision:
        raise HTTPException(409, "The fee schedule changed; reload it before saving")
    if payload.effective_from < today:
        raise HTTPException(422, "A fee change must start today or in the future using the UK practice date")
    append_version(db, row, payload.patient_category, state, {key: getattr(payload, key) for key in FEE_FIELDS},
        payload.effective_from, actor, request_id=request_id, fingerprint=fingerprint)
    db.commit()
    state = fee_states(db, [row.id], payload.patient_category, today=today).get((row.id, payload.patient_category), FeeState())
    return index_item(row, state)


def fee_history(db, treatment_id, category, limit, before_revision):
    get_treatment(db, treatment_id)
    state = fee_states(db, [treatment_id], category).get((treatment_id, category), FeeState())
    query = select(TreatmentFeeVersion).where(TreatmentFeeVersion.treatment_id == treatment_id,
        TreatmentFeeVersion.patient_category == category)
    if before_revision is not None:
        query = query.where(TreatmentFeeVersion.revision < before_revision)
    rows = list(db.scalars(query.order_by(TreatmentFeeVersion.revision.desc()).limit(limit + 1)))
    return {"treatment_id": treatment_id, "patient_category": category, "fee_revision": state.revision,
        "baseline_fee": fee_projection(state.baseline), "items": [fee_projection(resolved(row)) for row in rows[:limit]],
        "next_before_revision": rows[limit - 1].revision if len(rows) > limit else None}


def replace_current_fees(db, treatment_id, payload, actor):
    """Old list PUT means today's replacement, never deletion of future/history."""
    row = get_treatment(db, treatment_id, lock=True)
    if len({fee.patient_category for fee in payload}) != len(payload):
        raise HTTPException(422, "Each patient category may appear only once")
    today = practice_today()
    states = fee_states(db, [row.id], today=today)
    supplied = {fee.patient_category: fee for fee in payload}
    for category in PatientCategory:
        state = states.get((row.id, category), FeeState())
        values = {key: getattr(supplied[category], key) if category in supplied else None for key in FEE_FIELDS}
        current = {key: getattr(state.current, key) if state.current is not None else None for key in FEE_FIELDS}
        if values != current:
            append_version(db, row, category, state, values, today, actor)
    db.commit()
    return current_fees(db, row.id)


def initialize_routines(db, actor):
    db.execute(text("SELECT pg_advisory_xact_lock(6100610061)"))
    rows = list(db.scalars(select(Treatment).options(lazyload(Treatment.fees)).with_for_update(of=Treatment)))
    existing = {row.routine_key for row in rows if row.routine_key is not None}
    matches = {}
    # Resolve every candidate before mutation: never partially initialize an
    # ambiguous catalogue or merge identities, prices or historical usage.
    for level, names in ROUTINE_DEFAULTS.items():
        for order, name in enumerate(names, start=1):
            key = f"routine-v1:{level}:{order}"
            if key in existing:
                continue
            candidates = [row for row in rows if row.name.strip().casefold() == name.casefold()]
            if len(candidates) > 1 or (candidates and
                    (candidates[0].level not in (None, level) or candidates[0].routine_key is not None)):
                raise HTTPException(422, f"Review existing catalogue entries named '{name}' before adding routine treatments")
            matches[key] = candidates[0] if candidates else None
    created = kept = 0
    adopted = []
    for level, names in ROUTINE_DEFAULTS.items():
        for order, name in enumerate(names, start=1):
            key = f"routine-v1:{level}:{order}"
            if key in existing:
                kept += 1
                continue
            matched = matches[key]
            if matched is not None:
                before = {"level": matched.level, "display_order": matched.display_order}
                matched.level, matched.display_order, matched.routine_key = level, order * 10, key
                matched.updated_by_user_id = actor.id
                adopted.append(matched.id)
                log_event(db, actor=actor, action="treatment.routine.classified", entity_type="treatment",
                    entity_id=str(matched.id), before_data=before,
                    after_data={"level": level, "display_order": order * 10, "routine_key": key})
                kept += 1
                continue
            db.add(Treatment(name=name, level=level, display_order=order * 10, routine_key=key,
                is_active=True, created_by_user_id=actor.id, updated_by_user_id=actor.id))
            created += 1
    if created or adopted:
        db.flush()
        log_event(db, actor=actor, action="treatment.routines.initialized", entity_type="treatment_catalogue", entity_id="native",
            after_data={"created": created, "preserved": kept, "classified_ids": adopted, "new_fee_policy": "unset"})
    db.commit()
    return {"created": created, "existing": kept, "total": created + kept}
