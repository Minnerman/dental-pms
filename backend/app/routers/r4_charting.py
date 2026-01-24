from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
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

router = APIRouter(
    prefix="/patients/{patient_id}/charting",
    tags=["charting"],
    dependencies=[Depends(require_admin)],
)

DEFAULT_LIMIT = 500
MAX_LIMIT = 5000


def _ensure_charting_enabled() -> None:
    if not settings.feature_charting_viewer:
        raise HTTPException(status_code=403, detail="Charting viewer is disabled.")


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
    _=Depends(_ensure_charting_enabled),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    patient_code = _resolve_legacy_patient_code(db, patient_id)
    if patient_code is None:
        return PaginatedR4PerioProbeOut(
            items=[],
            total=0,
            limit=limit,
            offset=offset,
            has_more=False,
        ).model_dump()
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
    return PaginatedR4PerioProbeOut(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=has_more,
    ).model_dump()


@router.get("/bpe", response_model=list[R4BPEEntryOut])
def list_bpe_entries(
    patient_id: int,
    db: Session = Depends(get_db),
    _=Depends(_ensure_charting_enabled),
) -> list[R4BPEEntry]:
    patient_code = _resolve_legacy_patient_code(db, patient_id)
    if patient_code is None:
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
    return list(db.scalars(stmt))


@router.get("/bpe-furcations", response_model=list[R4BPEFurcationOut])
def list_bpe_furcations(
    patient_id: int,
    db: Session = Depends(get_db),
    _=Depends(_ensure_charting_enabled),
) -> list[R4BPEFurcation]:
    patient_code = _resolve_legacy_patient_code(db, patient_id)
    if patient_code is None:
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
    return list(db.scalars(stmt))


@router.get("/notes", response_model=list[R4PatientNoteOut])
def list_patient_notes(
    patient_id: int,
    db: Session = Depends(get_db),
    _=Depends(_ensure_charting_enabled),
) -> list[R4PatientNote]:
    patient_code = _resolve_legacy_patient_code(db, patient_id)
    if patient_code is None:
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
    return list(db.scalars(stmt))


@router.get("/tooth-surfaces", response_model=PaginatedR4ToothSurfaceOut)
def list_tooth_surfaces(
    patient_id: int,
    db: Session = Depends(get_db),
    _=Depends(_ensure_charting_enabled),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    patient_code = _resolve_legacy_patient_code(db, patient_id)
    if patient_code is None:
        return PaginatedR4ToothSurfaceOut(
            items=[],
            total=0,
            limit=limit,
            offset=offset,
            has_more=False,
        ).model_dump()
    total = db.scalar(select(func.count()).select_from(R4ToothSurface))
    total = int(total or 0)
    stmt = select(R4ToothSurface).order_by(
        R4ToothSurface.legacy_tooth_id.asc(),
        R4ToothSurface.legacy_surface_no.asc(),
    ).offset(offset).limit(limit)
    items = list(db.scalars(stmt))
    has_more = offset + len(items) < total
    return PaginatedR4ToothSurfaceOut(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=has_more,
    ).model_dump()


@router.get("/meta", response_model=R4ChartingMetaOut)
def get_charting_meta(
    patient_id: int,
    db: Session = Depends(get_db),
    _=Depends(_ensure_charting_enabled),
) -> R4ChartingMetaOut:
    patient_code = _resolve_legacy_patient_code(db, patient_id)
    record = db.scalar(
        select(R4ChartingImportState).where(R4ChartingImportState.patient_id == patient_id)
    )
    last_imported_at = record.last_imported_at if record else None
    return R4ChartingMetaOut(
        patient_id=patient_id,
        legacy_patient_code=patient_code,
        last_imported_at=last_imported_at,
        source="r4",
    )
