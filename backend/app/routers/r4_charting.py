from __future__ import annotations

import io
import json
import logging
import time
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import and_, func, literal, nullslast, select
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.db.session import get_db
from app.deps import get_current_user
from app.models.patient import Patient
from app.models.user import Role
from app.models.r4_charting_canonical import R4ChartingCanonicalRecord
from app.models.r4_charting import (
    R4BPEEntry,
    R4BPEFurcation,
    R4ChartingImportState,
    R4FixedNote,
    R4NoteCategory,
    R4PatientNote,
    R4PerioPlaque,
    R4PerioProbe,
    R4ToothSurface,
)
from app.models.r4_treatment_plan import R4Treatment
from app.services.charting_csv import (
    ENTITY_ALIASES,
    ENTITY_COLUMNS,
    ENTITY_DATE_FIELDS,
    ENTITY_LINKAGE,
    ENTITY_SORT_KEYS,
    csv_text,
    date_range,
    format_dt,
    normalize_entity_rows,
    parse_entities,
    rows_for_csv,
)
from app.services.audit import log_event
from app.services.tooth_state_classification import classify_tooth_state_type
from app.schemas.r4_charting import (
    ChartingAuditIn,
    PaginatedR4PerioProbeOut,
    PaginatedR4PerioPlaqueOut,
    PaginatedR4ToothSurfaceOut,
    R4BPEEntryOut,
    R4BPEFurcationOut,
    R4ChartingMetaOut,
    R4FixedNoteOut,
    R4NoteCategoryOut,
    R4PatientNoteOut,
    R4PerioPlaqueOut,
    R4PerioProbeOut,
    R4TreatmentPlanOverlayItemOut,
    R4TreatmentPlanOverlayOut,
    R4TreatmentPlanToothGroupOut,
    R4ToothStateEntryOut,
    R4ToothStateOut,
    R4ToothStateRestorationOut,
    R4ToothSurfaceOut,
)
from app.services.rate_limit import SimpleRateLimiter

router = APIRouter(prefix="/patients/{patient_id}/charting", tags=["charting"])
logger = logging.getLogger("dental_pms.charting")

DEFAULT_LIMIT = 500
MAX_LIMIT = 5000
CHARTING_RATE_LIMITER = SimpleRateLimiter(max_events=60, window_seconds=60)
CHARTING_EXPORT_RATE_LIMITER = SimpleRateLimiter(max_events=10, window_seconds=60)
EXPORT_MAX_ROWS = max(settings.charting_export_max_rows, 1)


def _log_charting_access(
    *,
    user_id: int,
    user_email: str,
    patient_id: int | None,
    path: str,
    method: str,
    status_code: int,
    duration_ms: int,
) -> None:
    logger.info(
        "charting_access",
        extra={
            "user_id": user_id,
            "user_email": user_email,
            "patient_id": patient_id,
            "path": path,
            "method": method,
            "status_code": status_code,
            "duration_ms": duration_ms,
        },
    )


def _charting_access_context(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> dict[str, object]:
    start = time.monotonic()
    patient_id = request.path_params.get("patient_id")
    patient_value = int(patient_id) if isinstance(patient_id, str) and patient_id.isdigit() else None
    if patient_value is not None:
        patient = db.get(Patient, patient_value)
        if not patient or patient.deleted_at is not None:
            duration_ms = int((time.monotonic() - start) * 1000)
            _log_charting_access(
                user_id=user.id,
                user_email=user.email,
                patient_id=patient_value,
                path=request.url.path,
                method=request.method,
                status_code=404,
                duration_ms=duration_ms,
            )
            raise HTTPException(status_code=404, detail="Patient not found")
    if user.role == Role.external:
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_value,
            path=request.url.path,
            method=request.method,
            status_code=403,
            duration_ms=duration_ms,
        )
        raise HTTPException(
            status_code=403,
            detail="Charting access is restricted for external users.",
        )
    if not settings.feature_charting_viewer:
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_value,
            path=request.url.path,
            method=request.method,
            status_code=403,
            duration_ms=duration_ms,
        )
        raise HTTPException(status_code=403, detail="Charting viewer is disabled.")
    if settings.app_env.strip().lower() != "test":
        if not CHARTING_RATE_LIMITER.allow(f"user:{user.id}"):
            duration_ms = int((time.monotonic() - start) * 1000)
            _log_charting_access(
                user_id=user.id,
                user_email=user.email,
                patient_id=patient_value,
                path=request.url.path,
                method=request.method,
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                duration_ms=duration_ms,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many charting requests",
            )
    return {"user": user, "start": start, "request": request}


def _resolve_legacy_patient_code(db: Session, patient_id: int) -> int | None:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    if patient.legacy_source != "r4":
        return None
    legacy_id = patient.legacy_id or ""
    return int(legacy_id) if legacy_id.isdigit() else None


def _pg_rows(db: Session, stmt):
    rows = db.execute(stmt).mappings().all()
    normalized: list[dict[str, object]] = []
    for row in rows:
        payload = {}
        for key, value in row.items():
            payload[key] = format_dt(value)
        normalized.append(payload)
    return normalized


def _canonical_payload(record: R4ChartingCanonicalRecord) -> dict[str, object]:
    if isinstance(record.payload, dict):
        return dict(record.payload)
    return {}


def _coerce_optional_int(value: object | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _coerce_optional_bool(value: object | None) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return None


def _coerce_optional_datetime(value: object | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _surface_key(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    if text in {"M", "O", "D", "B", "L", "I"}:
        return text
    numeric = _coerce_optional_int(value)
    if numeric is None:
        return None
    return {
        1: "M",
        2: "O",
        3: "D",
        4: "B",
        5: "L",
        6: "I",
    }.get(numeric)


def _extract_surface_keys(
    payload: dict[str, object],
    fallback_surface: object | None,
) -> list[str]:
    values: list[object] = []
    raw_surfaces = payload.get("surfaces")
    if isinstance(raw_surfaces, list):
        values.extend(raw_surfaces)
    elif raw_surfaces is not None:
        values.append(raw_surfaces)

    raw_surface = payload.get("surface")
    if raw_surface is not None:
        values.append(raw_surface)
    if fallback_surface is not None:
        values.append(fallback_surface)

    surface_keys: list[str] = []
    for value in values:
        surface_key = _surface_key(value)
        if surface_key is None:
            continue
        if surface_key not in surface_keys:
            surface_keys.append(surface_key)
    return surface_keys


def _bool_from_payload(payload: dict[str, object], keys: tuple[str, ...]) -> bool | None:
    for key in keys:
        if key in payload:
            value = _coerce_optional_bool(payload.get(key))
            if value is not None:
                return value
    return None


@router.get("/perio-probes", response_model=PaginatedR4PerioProbeOut)
def list_perio_probes(
    patient_id: int,
    db: Session = Depends(get_db),
    access=Depends(_charting_access_context),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None, alias="to"),
    tooth: int | None = Query(default=None, ge=1),
    site: int | None = Query(default=None, ge=1),
    bleeding: int | None = Query(default=None, ge=0, le=1),
    plaque: int | None = Query(default=None, ge=0, le=1),
) -> dict[str, object]:
    user = access["user"]
    start = access["start"]
    request: Request = access["request"]
    try:
        patient_code = _resolve_legacy_patient_code(db, patient_id)
        if patient_code is None:
            payload = PaginatedR4PerioProbeOut(
                items=[],
                total=0,
                limit=limit,
                offset=offset,
                has_more=False,
            ).model_dump()
            duration_ms = int((time.monotonic() - start) * 1000)
            _log_charting_access(
                user_id=user.id,
                user_email=user.email,
                patient_id=patient_id,
                path=request.url.path,
                method=request.method,
                status_code=200,
                duration_ms=duration_ms,
            )
            return payload
        filters = [R4PerioProbe.legacy_patient_code == patient_code]
        if from_:
            filters.append(R4PerioProbe.recorded_at >= from_)
        if to:
            filters.append(R4PerioProbe.recorded_at <= to)
        if tooth is not None:
            filters.append(R4PerioProbe.tooth == tooth)
        if site is not None:
            filters.append(R4PerioProbe.probing_point == site)
        if bleeding is not None:
            if bleeding == 1:
                filters.append(
                    and_(
                        R4PerioProbe.bleeding.is_not(None),
                        R4PerioProbe.bleeding > 0,
                    )
                )
            else:
                filters.append(R4PerioProbe.bleeding == 0)
        if plaque is not None:
            if plaque == 1:
                filters.append(
                    and_(
                        R4PerioProbe.plaque.is_not(None),
                        R4PerioProbe.plaque > 0,
                    )
                )
            else:
                filters.append(R4PerioProbe.plaque == 0)
        total = db.scalar(select(func.count()).select_from(R4PerioProbe).where(*filters))
        total = int(total or 0)
        stmt = (
            select(R4PerioProbe)
            .where(*filters)
            .order_by(
                nullslast(R4PerioProbe.recorded_at.asc()),
                nullslast(R4PerioProbe.tooth.asc()),
                nullslast(R4PerioProbe.probing_point.asc()),
                nullslast(R4PerioProbe.legacy_trans_id.asc()),
                R4PerioProbe.legacy_probe_key.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
        items = list(db.scalars(stmt))
        has_more = offset + len(items) < total
        payload = PaginatedR4PerioProbeOut(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
        ).model_dump()
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=200,
            duration_ms=duration_ms,
        )
        return payload
    except HTTPException as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=exc.status_code,
            duration_ms=duration_ms,
        )
        raise


@router.get("/perio-plaque", response_model=PaginatedR4PerioPlaqueOut)
def list_perio_plaque(
    patient_id: int,
    db: Session = Depends(get_db),
    access=Depends(_charting_access_context),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None, alias="to"),
    tooth: int | None = Query(default=None, ge=1),
    plaque: int | None = Query(default=None, ge=0, le=1),
    bleeding: int | None = Query(default=None, ge=0, le=1),
) -> dict[str, object]:
    user = access["user"]
    start = access["start"]
    request: Request = access["request"]
    try:
        patient_code = _resolve_legacy_patient_code(db, patient_id)
        if patient_code is None:
            payload = PaginatedR4PerioPlaqueOut(
                items=[],
                total=0,
                limit=limit,
                offset=offset,
                has_more=False,
            ).model_dump()
            duration_ms = int((time.monotonic() - start) * 1000)
            _log_charting_access(
                user_id=user.id,
                user_email=user.email,
                patient_id=patient_id,
                path=request.url.path,
                method=request.method,
                status_code=200,
                duration_ms=duration_ms,
            )
            return payload
        filters = [R4PerioPlaque.legacy_patient_code == patient_code]
        if from_:
            filters.append(R4PerioPlaque.recorded_at >= from_)
        if to:
            filters.append(R4PerioPlaque.recorded_at <= to)
        if tooth is not None:
            filters.append(R4PerioPlaque.tooth == tooth)
        if plaque is not None:
            if plaque == 1:
                filters.append(
                    and_(
                        R4PerioPlaque.plaque.is_not(None),
                        R4PerioPlaque.plaque > 0,
                    )
                )
            else:
                filters.append(R4PerioPlaque.plaque == 0)
        if bleeding is not None:
            if bleeding == 1:
                filters.append(
                    and_(
                        R4PerioPlaque.bleeding.is_not(None),
                        R4PerioPlaque.bleeding > 0,
                    )
                )
            else:
                filters.append(R4PerioPlaque.bleeding == 0)
        total = db.scalar(select(func.count()).select_from(R4PerioPlaque).where(*filters))
        total = int(total or 0)
        stmt = (
            select(R4PerioPlaque)
            .where(*filters)
            .order_by(
                nullslast(R4PerioPlaque.recorded_at.asc()),
                nullslast(R4PerioPlaque.tooth.asc()),
                nullslast(R4PerioPlaque.legacy_trans_id.asc()),
                R4PerioPlaque.legacy_plaque_key.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
        items = list(db.scalars(stmt))
        has_more = offset + len(items) < total
        payload = PaginatedR4PerioPlaqueOut(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
        ).model_dump()
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=200,
            duration_ms=duration_ms,
        )
        return payload
    except HTTPException as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=exc.status_code,
            duration_ms=duration_ms,
        )
        raise


@router.get("/treatment-plan-items", response_model=R4TreatmentPlanOverlayOut)
def list_treatment_plan_items_overlay(
    patient_id: int,
    db: Session = Depends(get_db),
    access=Depends(_charting_access_context),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    include_planned: bool = Query(default=True),
    include_completed: bool = Query(default=True),
) -> R4TreatmentPlanOverlayOut:
    user = access["user"]
    start = access["start"]
    request: Request = access["request"]
    try:
        patient_code = _resolve_legacy_patient_code(db, patient_id)
        if patient_code is None:
            payload = R4TreatmentPlanOverlayOut(
                patient_id=patient_id,
                legacy_patient_code=None,
                total_items=0,
                total_planned=0,
                total_completed=0,
                tooth_groups=[],
                unassigned_items=[],
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            _log_charting_access(
                user_id=user.id,
                user_email=user.email,
                patient_id=patient_id,
                path=request.url.path,
                method=request.method,
                status_code=200,
                duration_ms=duration_ms,
            )
            return payload
        if not include_planned and not include_completed:
            payload = R4TreatmentPlanOverlayOut(
                patient_id=patient_id,
                legacy_patient_code=patient_code,
                total_items=0,
                total_planned=0,
                total_completed=0,
                tooth_groups=[],
                unassigned_items=[],
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            _log_charting_access(
                user_id=user.id,
                user_email=user.email,
                patient_id=patient_id,
                path=request.url.path,
                method=request.method,
                status_code=200,
                duration_ms=duration_ms,
            )
            return payload

        stmt = (
            select(R4ChartingCanonicalRecord, R4Treatment.description.label("code_label"))
            .outerjoin(
                R4Treatment,
                and_(
                    R4Treatment.legacy_source == "r4",
                    R4Treatment.legacy_treatment_code == R4ChartingCanonicalRecord.code_id,
                ),
            )
            .where(
                R4ChartingCanonicalRecord.legacy_patient_code == patient_code,
                R4ChartingCanonicalRecord.domain.in_(("treatment_plan_item", "treatment_plan_items")),
            )
            .order_by(
                nullslast(R4ChartingCanonicalRecord.recorded_at.desc()),
                R4ChartingCanonicalRecord.r4_source_id.desc(),
            )
            .limit(limit)
        )

        tooth_buckets: dict[int, list[R4TreatmentPlanOverlayItemOut]] = {}
        unassigned_items: list[R4TreatmentPlanOverlayItemOut] = []
        total_planned = 0
        total_completed = 0
        total_items = 0

        for record, code_label in db.execute(stmt).all():
            payload = _canonical_payload(record)
            completed = _coerce_optional_bool(payload.get("completed"))
            is_completed = completed is True
            if is_completed and not include_completed:
                continue
            if (not is_completed) and not include_planned:
                continue

            tooth = _coerce_optional_int(payload.get("tooth"))
            surface = _coerce_optional_int(payload.get("surface"))
            code_id = _coerce_optional_int(payload.get("code_id"))
            item = R4TreatmentPlanOverlayItemOut(
                tp_number=_coerce_optional_int(payload.get("tp_number")),
                tp_item=_coerce_optional_int(payload.get("tp_item")),
                tp_item_key=(
                    str(payload.get("tp_item_key"))
                    if payload.get("tp_item_key") is not None
                    else (record.r4_source_id or None)
                ),
                code_id=code_id if code_id is not None else record.code_id,
                code_label=(code_label or ("Unknown code" if code_id is not None else None)),
                tooth=tooth,
                surface=surface,
                tooth_level=surface in (None, 0),
                completed=completed if completed is not None else False,
                item_date=_coerce_optional_datetime(payload.get("item_date")),
                plan_creation_date=_coerce_optional_datetime(
                    payload.get("plan_creation_date") or payload.get("creation_date")
                ),
            )
            total_items += 1
            if is_completed:
                total_completed += 1
            else:
                total_planned += 1
            if tooth is None or tooth <= 0:
                unassigned_items.append(item)
                continue
            tooth_buckets.setdefault(tooth, []).append(item)

        tooth_groups: list[R4TreatmentPlanToothGroupOut] = []
        for tooth in sorted(tooth_buckets):
            items = tooth_buckets[tooth]
            planned_count = sum(1 for item in items if item.completed is not True)
            completed_count = sum(1 for item in items if item.completed is True)
            tooth_groups.append(
                R4TreatmentPlanToothGroupOut(
                    tooth=tooth,
                    planned_count=planned_count,
                    completed_count=completed_count,
                    items=items,
                )
            )

        response = R4TreatmentPlanOverlayOut(
            patient_id=patient_id,
            legacy_patient_code=patient_code,
            total_items=total_items,
            total_planned=total_planned,
            total_completed=total_completed,
            tooth_groups=tooth_groups,
            unassigned_items=unassigned_items,
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=200,
            duration_ms=duration_ms,
        )
        return response
    except HTTPException as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=exc.status_code,
            duration_ms=duration_ms,
        )
        raise


@router.get("/tooth-state", response_model=R4ToothStateOut)
def get_tooth_state(
    patient_id: int,
    db: Session = Depends(get_db),
    access=Depends(_charting_access_context),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
) -> R4ToothStateOut:
    user = access["user"]
    start = access["start"]
    request: Request = access["request"]
    try:
        patient_code = _resolve_legacy_patient_code(db, patient_id)
        if patient_code is None:
            response = R4ToothStateOut(patient_id=patient_id, legacy_patient_code=None, teeth={})
            duration_ms = int((time.monotonic() - start) * 1000)
            _log_charting_access(
                user_id=user.id,
                user_email=user.email,
                patient_id=patient_id,
                path=request.url.path,
                method=request.method,
                status_code=200,
                duration_ms=duration_ms,
            )
            return response

        stmt = (
            select(R4ChartingCanonicalRecord, R4Treatment.description.label("code_label"))
            .outerjoin(
                R4Treatment,
                and_(
                    R4Treatment.legacy_source == "r4",
                    R4Treatment.legacy_treatment_code == R4ChartingCanonicalRecord.code_id,
                ),
            )
            .where(
                R4ChartingCanonicalRecord.legacy_patient_code == patient_code,
                R4ChartingCanonicalRecord.domain.in_(("treatment_plan_item", "treatment_plan_items")),
            )
            .order_by(
                nullslast(R4ChartingCanonicalRecord.recorded_at.desc()),
                R4ChartingCanonicalRecord.r4_source_id.desc(),
            )
            .limit(limit)
        )

        teeth: dict[str, R4ToothStateEntryOut] = {}
        seen_restorations: dict[str, set[str]] = {}

        for record, code_label in db.execute(stmt).all():
            payload = _canonical_payload(record)
            completed = _coerce_optional_bool(payload.get("completed"))
            if completed is not True:
                continue

            tooth = _coerce_optional_int(payload.get("tooth"))
            if tooth is None:
                tooth = record.tooth
            if tooth is None or tooth <= 0:
                continue

            resolved_code_id = record.code_id
            if resolved_code_id is None:
                resolved_code_id = _coerce_optional_int(payload.get("code_id"))
            resolved_code_label: str | None = code_label
            if not resolved_code_label and resolved_code_id is not None:
                resolved_code_label = "Unknown code"

            tooth_key = str(tooth)
            entry = teeth.setdefault(
                tooth_key,
                R4ToothStateEntryOut(restorations=[], missing=False, extracted=False),
            )

            restoration_type = classify_tooth_state_type(resolved_code_label)
            if restoration_type == "extraction":
                entry.extracted = True

            restoration_surfaces = _extract_surface_keys(payload, record.surface)

            dedupe_key = "|".join(
                [
                    restoration_type,
                    ",".join(restoration_surfaces),
                    record.r4_source or "",
                    record.r4_source_id or "",
                ]
            )
            seen = seen_restorations.setdefault(tooth_key, set())
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            restoration_meta: dict[str, object] = {
                "source_domain": record.domain,
                "source_table": record.r4_source,
                "source_id": record.r4_source_id,
                "completed": True,
                "raw_surface": payload.get("surface", record.surface),
            }
            if resolved_code_id is not None:
                restoration_meta["code_id"] = resolved_code_id
            if resolved_code_label:
                restoration_meta["code_label"] = resolved_code_label
            if restoration_surfaces:
                restoration_meta["mapped_surfaces"] = restoration_surfaces
            entry.restorations.append(
                R4ToothStateRestorationOut(
                    type=restoration_type,
                    surfaces=restoration_surfaces,
                    meta=restoration_meta,
                )
            )

        response = R4ToothStateOut(
            patient_id=patient_id,
            legacy_patient_code=patient_code,
            teeth=teeth,
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=200,
            duration_ms=duration_ms,
        )
        return response
    except HTTPException as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=exc.status_code,
            duration_ms=duration_ms,
        )
        raise


@router.get("/bpe", response_model=list[R4BPEEntryOut])
def list_bpe_entries(
    patient_id: int,
    db: Session = Depends(get_db),
    access=Depends(_charting_access_context),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None, alias="to"),
    latest_only: bool = Query(default=False, alias="latest_only"),
) -> list[R4BPEEntry]:
    user = access["user"]
    start = access["start"]
    request: Request = access["request"]
    try:
        patient_code = _resolve_legacy_patient_code(db, patient_id)
        if patient_code is None:
            duration_ms = int((time.monotonic() - start) * 1000)
            _log_charting_access(
                user_id=user.id,
                user_email=user.email,
                patient_id=patient_id,
                path=request.url.path,
                method=request.method,
                status_code=200,
                duration_ms=duration_ms,
            )
            return []
        filters = [R4BPEEntry.legacy_patient_code == patient_code]
        if from_:
            filters.append(R4BPEEntry.recorded_at >= from_)
        if to:
            filters.append(R4BPEEntry.recorded_at <= to)
        if latest_only:
            latest_date = db.scalar(
                select(func.max(func.date(R4BPEEntry.recorded_at))).where(*filters)
            )
            if latest_date is not None:
                filters.append(func.date(R4BPEEntry.recorded_at) == latest_date)
        stmt = (
            select(R4BPEEntry)
            .where(*filters)
            .order_by(
                nullslast(R4BPEEntry.recorded_at.asc()),
                nullslast(R4BPEEntry.legacy_bpe_id.asc()),
                R4BPEEntry.legacy_bpe_key.asc(),
            )
        )
        payload = list(db.scalars(stmt))
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=200,
            duration_ms=duration_ms,
        )
        return payload
    except HTTPException as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=exc.status_code,
            duration_ms=duration_ms,
        )
        raise


@router.get("/bpe-furcations", response_model=list[R4BPEFurcationOut])
def list_bpe_furcations(
    patient_id: int,
    db: Session = Depends(get_db),
    access=Depends(_charting_access_context),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None, alias="to"),
    latest_only: bool = Query(default=False, alias="latest_only"),
) -> list[R4BPEFurcation]:
    user = access["user"]
    start = access["start"]
    request: Request = access["request"]
    try:
        patient_code = _resolve_legacy_patient_code(db, patient_id)
        if patient_code is None:
            duration_ms = int((time.monotonic() - start) * 1000)
            _log_charting_access(
                user_id=user.id,
                user_email=user.email,
                patient_id=patient_id,
                path=request.url.path,
                method=request.method,
                status_code=200,
                duration_ms=duration_ms,
            )
            return []
        filters = [R4BPEFurcation.legacy_patient_code == patient_code]
        if from_:
            filters.append(R4BPEFurcation.recorded_at >= from_)
        if to:
            filters.append(R4BPEFurcation.recorded_at <= to)
        if latest_only:
            latest_date = db.scalar(
                select(func.max(func.date(R4BPEFurcation.recorded_at))).where(*filters)
            )
            if latest_date is not None:
                filters.append(func.date(R4BPEFurcation.recorded_at) == latest_date)
        stmt = (
            select(R4BPEFurcation)
            .where(*filters)
            .order_by(
                nullslast(R4BPEFurcation.recorded_at.asc()),
                nullslast(R4BPEFurcation.legacy_bpe_id.asc()),
                nullslast(R4BPEFurcation.tooth.asc()),
                nullslast(R4BPEFurcation.furcation.asc()),
                R4BPEFurcation.legacy_bpe_furcation_key.asc(),
            )
        )
        payload = list(db.scalars(stmt))
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=200,
            duration_ms=duration_ms,
        )
        return payload
    except HTTPException as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=exc.status_code,
            duration_ms=duration_ms,
        )
        raise


@router.get("/notes", response_model=list[R4PatientNoteOut])
def list_patient_notes(
    patient_id: int,
    db: Session = Depends(get_db),
    access=Depends(_charting_access_context),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None, alias="to"),
    q: str | None = Query(default=None, alias="q"),
    category: int | None = Query(default=None, alias="category"),
) -> list[R4PatientNote]:
    user = access["user"]
    start = access["start"]
    request: Request = access["request"]
    try:
        patient_code = _resolve_legacy_patient_code(db, patient_id)
        if patient_code is None:
            duration_ms = int((time.monotonic() - start) * 1000)
            _log_charting_access(
                user_id=user.id,
                user_email=user.email,
                patient_id=patient_id,
                path=request.url.path,
                method=request.method,
                status_code=200,
                duration_ms=duration_ms,
            )
            return []
        filters = [R4PatientNote.legacy_patient_code == patient_code]
        if from_:
            filters.append(R4PatientNote.note_date >= from_)
        if to:
            filters.append(R4PatientNote.note_date <= to)
        if q:
            filters.append(R4PatientNote.note.ilike(f"%{q}%"))
        if category is not None:
            filters.append(R4PatientNote.category_number == category)
        stmt = (
            select(R4PatientNote)
            .where(*filters)
            .order_by(
                nullslast(R4PatientNote.note_date.asc()),
                nullslast(R4PatientNote.legacy_note_number.asc()),
                R4PatientNote.legacy_note_key.asc(),
            )
        )
        payload = list(db.scalars(stmt))
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=200,
            duration_ms=duration_ms,
        )
        return payload
    except HTTPException as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=exc.status_code,
            duration_ms=duration_ms,
        )
        raise


@router.get("/note-categories", response_model=list[R4NoteCategoryOut])
def list_note_categories(
    patient_id: int,
    db: Session = Depends(get_db),
    access=Depends(_charting_access_context),
) -> list[R4NoteCategory]:
    user = access["user"]
    start = access["start"]
    request: Request = access["request"]
    try:
        patient_code = _resolve_legacy_patient_code(db, patient_id)
        if patient_code is None:
            duration_ms = int((time.monotonic() - start) * 1000)
            _log_charting_access(
                user_id=user.id,
                user_email=user.email,
                patient_id=patient_id,
                path=request.url.path,
                method=request.method,
                status_code=200,
                duration_ms=duration_ms,
            )
            return []
        stmt = select(R4NoteCategory).order_by(R4NoteCategory.legacy_category_number.asc())
        payload = list(db.scalars(stmt))
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=200,
            duration_ms=duration_ms,
        )
        return payload
    except HTTPException as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=exc.status_code,
            duration_ms=duration_ms,
        )
        raise


@router.get("/fixed-notes", response_model=list[R4FixedNoteOut])
def list_fixed_notes(
    patient_id: int,
    db: Session = Depends(get_db),
    access=Depends(_charting_access_context),
    category: int | None = Query(default=None, ge=0),
) -> list[R4FixedNote]:
    user = access["user"]
    start = access["start"]
    request: Request = access["request"]
    try:
        patient_code = _resolve_legacy_patient_code(db, patient_id)
        if patient_code is None:
            duration_ms = int((time.monotonic() - start) * 1000)
            _log_charting_access(
                user_id=user.id,
                user_email=user.email,
                patient_id=patient_id,
                path=request.url.path,
                method=request.method,
                status_code=200,
                duration_ms=duration_ms,
            )
            return []
        filters = []
        if category is not None:
            filters.append(R4FixedNote.category_number == category)
        stmt = (
            select(R4FixedNote)
            .where(*filters)
            .order_by(
                nullslast(R4FixedNote.category_number.asc()),
                R4FixedNote.legacy_fixed_note_code.asc(),
            )
        )
        payload = list(db.scalars(stmt))
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=200,
            duration_ms=duration_ms,
        )
        return payload
    except HTTPException as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=exc.status_code,
            duration_ms=duration_ms,
        )
        raise


@router.get("/tooth-surfaces", response_model=PaginatedR4ToothSurfaceOut)
def list_tooth_surfaces(
    patient_id: int,
    db: Session = Depends(get_db),
    access=Depends(_charting_access_context),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    user = access["user"]
    start = access["start"]
    request: Request = access["request"]
    try:
        patient_code = _resolve_legacy_patient_code(db, patient_id)
        if patient_code is None:
            payload = PaginatedR4ToothSurfaceOut(
                items=[],
                total=0,
                limit=limit,
                offset=offset,
                has_more=False,
            ).model_dump()
            duration_ms = int((time.monotonic() - start) * 1000)
            _log_charting_access(
                user_id=user.id,
                user_email=user.email,
                patient_id=patient_id,
                path=request.url.path,
                method=request.method,
                status_code=200,
                duration_ms=duration_ms,
            )
            return payload
        total = db.scalar(select(func.count()).select_from(R4ToothSurface))
        total = int(total or 0)
        stmt = select(R4ToothSurface).order_by(
            R4ToothSurface.legacy_tooth_id.asc(),
            R4ToothSurface.legacy_surface_no.asc(),
        ).offset(offset).limit(limit)
        items = list(db.scalars(stmt))
        has_more = offset + len(items) < total
        payload = PaginatedR4ToothSurfaceOut(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
        ).model_dump()
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=200,
            duration_ms=duration_ms,
        )
        return payload
    except HTTPException as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=exc.status_code,
            duration_ms=duration_ms,
        )
        raise


@router.get("/meta", response_model=R4ChartingMetaOut)
def get_charting_meta(
    patient_id: int,
    db: Session = Depends(get_db),
    access=Depends(_charting_access_context),
) -> R4ChartingMetaOut:
    user = access["user"]
    start = access["start"]
    request: Request = access["request"]
    try:
        patient_code = _resolve_legacy_patient_code(db, patient_id)
        record = db.scalar(
            select(R4ChartingImportState).where(
                R4ChartingImportState.patient_id == patient_id
            )
        )
        last_imported_at = record.last_imported_at if record else None
        payload = R4ChartingMetaOut(
            patient_id=patient_id,
            legacy_patient_code=patient_code,
            last_imported_at=last_imported_at,
            source="r4",
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=200,
            duration_ms=duration_ms,
        )
        return payload
    except HTTPException as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=exc.status_code,
            duration_ms=duration_ms,
        )
        raise


def _export_rows_for_entity(
    db: Session,
    entity: str,
    patient_code: int,
) -> tuple[list[dict[str, object]], int]:
    if entity == "patient_notes":
        stmt = select(
            R4PatientNote.legacy_patient_code.label("patient_code"),
            R4PatientNote.legacy_note_key.label("legacy_note_key"),
            R4PatientNote.legacy_note_number.label("note_number"),
            R4PatientNote.note_date.label("note_date"),
            R4PatientNote.note.label("note"),
            R4PatientNote.tooth.label("tooth"),
            R4PatientNote.surface.label("surface"),
            R4PatientNote.category_number.label("category_number"),
            R4PatientNote.fixed_note_code.label("fixed_note_code"),
            R4PatientNote.user_code.label("user_code"),
        ).where(R4PatientNote.legacy_patient_code == patient_code)
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        return _pg_rows(db, stmt.limit(EXPORT_MAX_ROWS)), total
    if entity == "bpe":
        stmt = select(
            R4BPEEntry.legacy_patient_code.label("patient_code"),
            R4BPEEntry.legacy_bpe_key.label("legacy_bpe_key"),
            R4BPEEntry.legacy_bpe_id.label("legacy_bpe_id"),
            R4BPEEntry.recorded_at.label("recorded_at"),
            R4BPEEntry.sextant_1.label("sextant_1"),
            R4BPEEntry.sextant_2.label("sextant_2"),
            R4BPEEntry.sextant_3.label("sextant_3"),
            R4BPEEntry.sextant_4.label("sextant_4"),
            R4BPEEntry.sextant_5.label("sextant_5"),
            R4BPEEntry.sextant_6.label("sextant_6"),
        ).where(R4BPEEntry.legacy_patient_code == patient_code)
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        return _pg_rows(db, stmt.limit(EXPORT_MAX_ROWS)), total
    if entity == "bpe_furcations":
        stmt = select(
            R4BPEFurcation.legacy_patient_code.label("patient_code"),
            R4BPEFurcation.legacy_bpe_furcation_key.label("legacy_bpe_furcation_key"),
            R4BPEFurcation.legacy_bpe_id.label("legacy_bpe_id"),
            R4BPEFurcation.recorded_at.label("recorded_at"),
            R4BPEFurcation.tooth.label("tooth"),
            R4BPEFurcation.furcation.label("furcation"),
            R4BPEFurcation.sextant.label("sextant"),
        ).where(R4BPEFurcation.legacy_patient_code == patient_code)
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        return _pg_rows(db, stmt.limit(EXPORT_MAX_ROWS)), total
    if entity == "perio_probes":
        stmt = select(
            R4PerioProbe.legacy_patient_code.label("patient_code"),
            R4PerioProbe.legacy_probe_key.label("legacy_probe_key"),
            R4PerioProbe.legacy_trans_id.label("legacy_trans_id"),
            R4PerioProbe.recorded_at.label("recorded_at"),
            R4PerioProbe.tooth.label("tooth"),
            R4PerioProbe.probing_point.label("probing_point"),
            R4PerioProbe.depth.label("depth"),
            R4PerioProbe.bleeding.label("bleeding"),
            R4PerioProbe.plaque.label("plaque"),
        ).where(R4PerioProbe.legacy_patient_code == patient_code)
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        return _pg_rows(db, stmt.limit(EXPORT_MAX_ROWS)), total
    if entity == "perio_plaque":
        stmt = select(
            R4PerioPlaque.legacy_patient_code.label("patient_code"),
            R4PerioPlaque.legacy_plaque_key.label("legacy_plaque_key"),
            R4PerioPlaque.legacy_trans_id.label("legacy_trans_id"),
            R4PerioPlaque.recorded_at.label("recorded_at"),
            R4PerioPlaque.tooth.label("tooth"),
            R4PerioPlaque.plaque.label("plaque"),
            R4PerioPlaque.bleeding.label("bleeding"),
        ).where(R4PerioPlaque.legacy_patient_code == patient_code)
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        return _pg_rows(db, stmt.limit(EXPORT_MAX_ROWS)), total
    if entity == "fixed_notes":
        codes = list(
            db.scalars(
                select(func.distinct(R4PatientNote.fixed_note_code)).where(
                    R4PatientNote.legacy_patient_code == patient_code,
                    R4PatientNote.fixed_note_code.is_not(None),
                )
            )
        )
        if not codes:
            return [], 0
        stmt = select(
            literal(patient_code).label("patient_code"),
            R4FixedNote.legacy_fixed_note_code.label("legacy_fixed_note_code"),
            R4FixedNote.category_number.label("category_number"),
            R4FixedNote.description.label("description"),
            R4FixedNote.note.label("note"),
            R4FixedNote.tooth.label("tooth"),
            R4FixedNote.surface.label("surface"),
        ).where(R4FixedNote.legacy_fixed_note_code.in_(codes))
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        return _pg_rows(db, stmt.limit(EXPORT_MAX_ROWS)), total
    if entity == "note_categories":
        categories = list(
            db.scalars(
                select(func.distinct(R4PatientNote.category_number)).where(
                    R4PatientNote.legacy_patient_code == patient_code,
                    R4PatientNote.category_number.is_not(None),
                )
            )
        )
        if not categories:
            return [], 0
        stmt = select(
            literal(patient_code).label("patient_code"),
            R4NoteCategory.legacy_category_number.label("legacy_category_number"),
            R4NoteCategory.description.label("description"),
        ).where(R4NoteCategory.legacy_category_number.in_(categories))
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        return _pg_rows(db, stmt.limit(EXPORT_MAX_ROWS)), total
    if entity == "tooth_surfaces":
        stmt = select(
            R4ToothSurface.legacy_tooth_id.label("legacy_tooth_id"),
            R4ToothSurface.legacy_surface_no.label("legacy_surface_no"),
            R4ToothSurface.label.label("label"),
            R4ToothSurface.short_label.label("short_label"),
            R4ToothSurface.sort_order.label("sort_order"),
        )
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        return _pg_rows(db, stmt.limit(EXPORT_MAX_ROWS)), total
    raise HTTPException(status_code=400, detail=f"Unsupported export entity: {entity}")


@router.get("/export")
def export_charting(
    patient_id: int,
    db: Session = Depends(get_db),
    access=Depends(_charting_access_context),
    entities: str | None = Query(default=None),
) -> Response:
    user = access["user"]
    start = access["start"]
    request: Request = access["request"]
    try:
        if settings.app_env.strip().lower() != "test":
            if not CHARTING_EXPORT_RATE_LIMITER.allow(f"user:{user.id}"):
                duration_ms = int((time.monotonic() - start) * 1000)
                _log_charting_access(
                    user_id=user.id,
                    user_email=user.email,
                    patient_id=patient_id,
                    path=request.url.path,
                    method=request.method,
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    duration_ms=duration_ms,
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many charting export requests",
                )
        patient_code = _resolve_legacy_patient_code(db, patient_id)
        if patient_code is None:
            raise HTTPException(status_code=404, detail="Patient is not linked to R4.")
        selected = parse_entities(entities, ENTITY_ALIASES)
        if not selected:
            raise HTTPException(status_code=400, detail="No export entities requested.")
        buffer = io.BytesIO()
        index_rows: list[dict[str, object]] = []
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for entity in selected:
                raw_rows, total_rows = _export_rows_for_entity(db, entity, patient_code)
                if len(raw_rows) > EXPORT_MAX_ROWS:
                    raw_rows = raw_rows[:EXPORT_MAX_ROWS]
                truncated = total_rows > EXPORT_MAX_ROWS
                normalized = normalize_entity_rows(entity, raw_rows, patient_code)
                csv_rows = rows_for_csv(normalized, ENTITY_COLUMNS[entity], patient_code)
                csv_body = csv_text(csv_rows, ENTITY_COLUMNS[entity], ENTITY_SORT_KEYS.get(entity, []))
                archive.writestr(f"postgres_{entity}.csv", csv_body)
                min_date, max_date = date_range(normalized, ENTITY_DATE_FIELDS.get(entity, []))
                index_rows.append(
                    {
                        "entity": entity,
                        "linkage_method": ENTITY_LINKAGE.get(entity),
                        "sqlserver_status": None,
                        "sqlserver_reason": None,
                        "sqlserver_count": None,
                        "sqlserver_total": None,
                        "sqlserver_unique_count": None,
                        "sqlserver_duplicate_count": None,
                        "sqlserver_date_min": None,
                        "sqlserver_date_max": None,
                        "postgres_count": len(normalized),
                        "postgres_total": total_rows,
                        "postgres_unique_count": len(normalized),
                        "postgres_duplicate_count": 0,
                        "postgres_date_min": min_date,
                        "postgres_date_max": max_date,
                        "postgres_truncated": truncated,
                        "postgres_limit": EXPORT_MAX_ROWS,
                    }
                )
            index_columns = [
                "entity",
                "linkage_method",
                "sqlserver_status",
                "sqlserver_reason",
                "sqlserver_count",
                "sqlserver_total",
                "sqlserver_unique_count",
                "sqlserver_duplicate_count",
                "sqlserver_date_min",
                "sqlserver_date_max",
                "postgres_count",
                "postgres_total",
                "postgres_unique_count",
                "postgres_duplicate_count",
                "postgres_date_min",
                "postgres_date_max",
                "postgres_truncated",
                "postgres_limit",
            ]
            index_csv = csv_text(index_rows, index_columns, ["entity"])
            archive.writestr("index.csv", index_csv)
            review_pack = {
                "generated_at": format_dt(datetime.now(timezone.utc)),
                "entities": selected,
                "export_limit": EXPORT_MAX_ROWS,
                "totals": {row["entity"]: row["postgres_total"] for row in index_rows},
                "truncated": {
                    row["entity"]: row["postgres_truncated"] for row in index_rows
                },
            }
            archive.writestr(
                "review_pack.json", json.dumps(review_pack, indent=2, sort_keys=True)
            )
        buffer.seek(0)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filename = f"charting_{patient_code}_{stamp}.zip"
        duration_ms = int((time.monotonic() - start) * 1000)
        log_event(
            db,
            actor=user,
            action="charting.export",
            entity_type="patient",
            entity_id=str(patient_id),
            after_data={
                "patient_code": patient_code,
                "entities": selected,
                "export_limit": EXPORT_MAX_ROWS,
            },
            ip_address=request.client.host if request else None,
        )
        db.commit()
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=200,
            duration_ms=duration_ms,
        )
        return Response(
            content=buffer.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=exc.status_code,
            duration_ms=duration_ms,
        )
        raise


@router.post("/audit", status_code=status.HTTP_204_NO_CONTENT)
def audit_charting_event(
    patient_id: int,
    payload: ChartingAuditIn,
    db: Session = Depends(get_db),
    access=Depends(_charting_access_context),
) -> Response:
    user = access["user"]
    start = access["start"]
    request: Request = access["request"]
    try:
        log_event(
            db,
            actor=user,
            action=f"charting.{payload.action}",
            entity_type="patient",
            entity_id=str(patient_id),
            after_data={"section": payload.section},
            ip_address=request.client.host if request else None,
        )
        db.commit()
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=status.HTTP_204_NO_CONTENT,
            duration_ms=duration_ms,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        _log_charting_access(
            user_id=user.id,
            user_email=user.email,
            patient_id=patient_id,
            path=request.url.path,
            method=request.method,
            status_code=exc.status_code,
            duration_ms=duration_ms,
        )
        raise
