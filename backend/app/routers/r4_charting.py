from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, nullslast, select
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.db.session import get_db
from app.deps import require_admin
from app.models.patient import Patient
from app.models.r4_charting import (
    R4BPEEntry,
    R4BPEFurcation,
    R4ChartingImportState,
    R4PatientNote,
    R4PerioProbe,
    R4ToothSurface,
)
from app.schemas.r4_charting import (
    PaginatedR4PerioProbeOut,
    PaginatedR4ToothSurfaceOut,
    R4BPEEntryOut,
    R4BPEFurcationOut,
    R4ChartingMetaOut,
    R4PatientNoteOut,
    R4PerioProbeOut,
    R4ToothSurfaceOut,
)
from app.services.rate_limit import SimpleRateLimiter

router = APIRouter(prefix="/patients/{patient_id}/charting", tags=["charting"])
logger = logging.getLogger("dental_pms.charting")

DEFAULT_LIMIT = 500
MAX_LIMIT = 5000
CHARTING_RATE_LIMITER = SimpleRateLimiter(max_events=60, window_seconds=60)


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
    user=Depends(require_admin),
) -> dict[str, object]:
    start = time.monotonic()
    patient_id = request.path_params.get("patient_id")
    patient_value = int(patient_id) if isinstance(patient_id, str) and patient_id.isdigit() else None
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
    if not settings.enable_test_routes and settings.app_env.strip().lower() != "test":
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


@router.get("/perio-probes", response_model=PaginatedR4PerioProbeOut)
def list_perio_probes(
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
        total = db.scalar(
            select(func.count()).select_from(R4PerioProbe).where(
                R4PerioProbe.legacy_patient_code == patient_code
            )
        )
        total = int(total or 0)
        stmt = (
            select(R4PerioProbe)
            .where(R4PerioProbe.legacy_patient_code == patient_code)
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


@router.get("/bpe", response_model=list[R4BPEEntryOut])
def list_bpe_entries(
    patient_id: int,
    db: Session = Depends(get_db),
    access=Depends(_charting_access_context),
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
        stmt = (
            select(R4BPEEntry)
            .where(R4BPEEntry.legacy_patient_code == patient_code)
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
        stmt = (
            select(R4BPEFurcation)
            .where(R4BPEFurcation.legacy_patient_code == patient_code)
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
        stmt = (
            select(R4PatientNote)
            .where(R4PatientNote.legacy_patient_code == patient_code)
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
