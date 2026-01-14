from collections import OrderedDict
from datetime import date, datetime, timedelta, timezone
from io import BytesIO, StringIO
import csv
import logging
import re
import time
import zipfile

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy import case, false, func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.patient import Patient, RecallStatus
from app.models.patient_recall import (
    PatientRecall,
    PatientRecallKind,
    PatientRecallStatus,
)
from app.models.patient_recall_communication import (
    PatientRecallCommunication,
    PatientRecallCommunicationChannel,
)
from app.models.patient_recall_communication import (
    PatientRecallCommunicationChannel,
    PatientRecallCommunicationDirection,
    PatientRecallCommunicationStatus,
)
from app.models.user import User
from app.schemas.patient import PatientRecallSettingsOut, RecallUpdate
from app.schemas.patient_document import PatientDocumentCreate, PatientDocumentOut
from app.schemas.recalls import RecallContactCreate, RecallDashboardRow, RecallKpiOut
from app.models.document_template import DocumentTemplate
from app.models.patient_document import PatientDocument
from app.services.audit import log_event, snapshot_model
from app.services.document_render import render_template_with_warnings
from app.services.recall_letter_pdf import build_recall_letter_pdf
from app.services.recall_communications import log_recall_communication
from app.services.recalls import resolve_recall_status

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/recalls", tags=["recalls"])
MAX_EXPORT_ROWS = 2000
EXPORT_COUNT_CACHE_TTL_SECONDS = 60
EXPORT_COUNT_CACHE_MAX = 500
_export_count_cache: OrderedDict[tuple, tuple[float, int]] = OrderedDict()
_export_count_cache_epoch = 0


def _stringify(value: object | None) -> str:
    if value is None:
        return "none"
    if isinstance(value, str) and not value.strip():
        return "none"
    if hasattr(value, "value"):
        return value.value
    return str(value)


def _log_recall_timeline(
    db: Session,
    *,
    actor: User,
    patient: Patient,
    before_data: dict,
    request_id: str | None,
    ip_address: str | None,
) -> None:
    old_status = _stringify(before_data.get("recall_status"))
    new_status = _stringify(patient.recall_status)
    if old_status != new_status:
        log_event(
            db,
            actor=actor,
            action=f"recall.status: {old_status} -> {new_status}",
            entity_type="patient",
            entity_id=str(patient.id),
            after_data={"recall_status": new_status},
            request_id=request_id,
            ip_address=ip_address,
        )

    old_type = _stringify(before_data.get("recall_type"))
    new_type = _stringify(patient.recall_type)
    if old_type != new_type:
        log_event(
            db,
            actor=actor,
            action=f"recall.type: {old_type} -> {new_type}",
            entity_type="patient",
            entity_id=str(patient.id),
            after_data={"recall_type": new_type},
            request_id=request_id,
            ip_address=ip_address,
        )

    old_notes = (before_data.get("recall_notes") or "").strip()
    new_notes = (patient.recall_notes or "").strip()
    if old_notes != new_notes:
        log_event(
            db,
            actor=actor,
            action="recall.notes_updated",
            entity_type="patient",
            entity_id=str(patient.id),
            after_data={"recall_notes": bool(new_notes)},
            request_id=request_id,
            ip_address=ip_address,
        )

    old_contacted = before_data.get("recall_last_contacted_at")
    new_contacted = (
        patient.recall_last_contacted_at.isoformat()
        if patient.recall_last_contacted_at
        else None
    )
    if not old_contacted and new_contacted:
        log_event(
            db,
            actor=actor,
            action="recall.contacted",
            entity_type="patient",
            entity_id=str(patient.id),
            after_data={"recall_last_contacted_at": new_contacted},
            request_id=request_id,
            ip_address=ip_address,
        )

def _parse_csv_values(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [value.strip().lower() for value in raw.split(",") if value.strip()]

def _safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    return cleaned


def _normalize_recall_filters(
    status: str | None, recall_type: str | None
) -> tuple[set[str], list[PatientRecallKind], set[PatientRecallStatus]]:
    requested_statuses = set(_parse_csv_values(status))
    if not requested_statuses:
        requested_statuses = {"due", "overdue"}
    allowed_statuses = {
        "upcoming",
        "due",
        "overdue",
        "completed",
        "cancelled",
    }
    requested_statuses = {value for value in requested_statuses if value in allowed_statuses}
    if not requested_statuses:
        requested_statuses = {"due", "overdue"}

    requested_types = set(_parse_csv_values(recall_type))
    allowed_types = {kind.value for kind in PatientRecallKind}
    requested_types = {value for value in requested_types if value in allowed_types}
    requested_type_members = [
        PatientRecallKind._value2member_map_[value] for value in requested_types
    ]

    stored_statuses: set[PatientRecallStatus] = set()
    for value in requested_statuses:
        member = PatientRecallStatus._value2member_map_.get(value)
        if member:
            stored_statuses.add(member)
    if "due" in requested_statuses or "overdue" in requested_statuses:
        stored_statuses.add(PatientRecallStatus.upcoming)

    return requested_statuses, requested_type_members, stored_statuses


def _requested_status_members(requested_statuses: set[str]) -> set[PatientRecallStatus]:
    members: set[PatientRecallStatus] = set()
    for value in requested_statuses:
        member = PatientRecallStatus._value2member_map_.get(value)
        if member:
            members.add(member)
    return members


def _normalize_contact_filters(
    contact_state: str | None,
    last_contact: str | None,
    method: str | None,
    contacted: str | None,
    contacted_within_days: int | None,
    contact_channel: str | None,
) -> tuple[str | None, int | None, int | None, list[PatientRecallCommunicationChannel]]:
    contact_flag = contact_state.lower().strip() if contact_state else None
    if contact_flag == "never":
        contact_flag = "no"
    elif contact_flag == "contacted":
        contact_flag = "yes"
    elif contact_flag not in {"yes", "no"}:
        contact_flag = None

    if contact_flag is None:
        legacy_flag = contacted.lower().strip() if contacted else None
        if legacy_flag in {"yes", "no"}:
            contact_flag = legacy_flag

    within_days = None
    older_than_days = None
    if last_contact in {"7d", "30d"}:
        within_days = 7 if last_contact == "7d" else 30
    elif last_contact == "older30d":
        older_than_days = 30
    elif contacted_within_days and contacted_within_days > 0:
        within_days = contacted_within_days

    requested_channels = set(_parse_csv_values(method or contact_channel))
    allowed_channels = {channel.value for channel in PatientRecallCommunicationChannel}
    requested_channels = {value for value in requested_channels if value in allowed_channels}
    requested_channel_members = [
        PatientRecallCommunicationChannel._value2member_map_[value]
        for value in requested_channels
    ]
    return contact_flag, within_days, older_than_days, requested_channel_members


def _build_last_contact_subquery():
    contact_ts = func.coalesce(
        PatientRecallCommunication.contacted_at,
        PatientRecallCommunication.created_at,
    )
    return (
        select(
            PatientRecallCommunication.id.label("comm_id"),
            PatientRecallCommunication.recall_id.label("recall_id"),
            contact_ts.label("contacted_at"),
            PatientRecallCommunication.channel.label("channel"),
            PatientRecallCommunication.notes.label("notes"),
            PatientRecallCommunication.other_detail.label("other_detail"),
            PatientRecallCommunication.outcome.label("outcome"),
            func.row_number()
            .over(
                partition_by=PatientRecallCommunication.recall_id,
                order_by=(
                    contact_ts.desc(),
                    PatientRecallCommunication.id.desc(),
                ),
            )
            .label("rn"),
        )
        .subquery()
    )


def _export_count_cache_key(
    *,
    start: date | None,
    end: date | None,
    status: str | None,
    recall_type: str | None,
    contact_state: str | None,
    last_contact: str | None,
    method: str | None,
    contacted: str | None,
    contacted_within_days: int | None,
    contact_channel: str | None,
) -> tuple:
    global _export_count_cache_epoch
    requested_statuses, requested_type_members, _stored_statuses = _normalize_recall_filters(
        status, recall_type
    )
    contact_flag, within_days, older_than_days, channels = _normalize_contact_filters(
        contact_state,
        last_contact,
        method,
        contacted,
        contacted_within_days,
        contact_channel,
    )
    status_key = tuple(sorted(requested_statuses))
    type_key = tuple(sorted(kind.value for kind in requested_type_members))
    channel_key = tuple(sorted(channel.value for channel in channels))
    return (
        _export_count_cache_epoch,
        start.isoformat() if start else None,
        end.isoformat() if end else None,
        status_key,
        type_key,
        contact_flag,
        within_days,
        older_than_days,
        channel_key,
    )


def _export_count_cache_get(key: tuple) -> int | None:
    entry = _export_count_cache.get(key)
    if not entry:
        return None
    timestamp, value = entry
    if (time.monotonic() - timestamp) > EXPORT_COUNT_CACHE_TTL_SECONDS:
        _export_count_cache.pop(key, None)
        return None
    _export_count_cache.move_to_end(key)
    return value


def _export_count_cache_set(key: tuple, value: int) -> None:
    _export_count_cache[key] = (time.monotonic(), value)
    _export_count_cache.move_to_end(key)
    while len(_export_count_cache) > EXPORT_COUNT_CACHE_MAX:
        _export_count_cache.popitem(last=False)


def bump_export_count_cache_epoch(reason: str) -> None:
    global _export_count_cache_epoch
    _export_count_cache_epoch += 1
    _export_count_cache.clear()
    logger.info(
        "export_count_cache_invalidate epoch=%d reason=%s",
        _export_count_cache_epoch,
        reason,
    )


def _resolved_status_expr(today: date):
    return case(
        (
            PatientRecall.status.in_(
                [
                    PatientRecallStatus.completed,
                    PatientRecallStatus.cancelled,
                    PatientRecallStatus.due,
                    PatientRecallStatus.overdue,
                ]
            ),
            PatientRecall.status,
        ),
        (PatientRecall.due_date.is_(None), PatientRecall.status),
        (PatientRecall.due_date < today, PatientRecallStatus.overdue),
        (PatientRecall.due_date <= today, PatientRecallStatus.due),
        else_=PatientRecall.status,
    )


def _apply_contact_filters(
    stmt,
    *,
    last_contact_subq,
    contact_flag: str | None,
    within_days: int | None,
    older_than_days: int | None,
    channels: list[PatientRecallCommunicationChannel],
):
    if contact_flag == "no":
        if within_days or older_than_days or channels:
            return stmt.where(false())
        return stmt.where(last_contact_subq.c.comm_id.is_(None))
    if contact_flag == "yes":
        stmt = stmt.where(last_contact_subq.c.comm_id.is_not(None))
    if within_days:
        threshold = datetime.now(timezone.utc) - timedelta(days=within_days)
        stmt = stmt.where(last_contact_subq.c.contacted_at >= threshold)
    if older_than_days:
        threshold = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        stmt = stmt.where(last_contact_subq.c.contacted_at < threshold)
    if channels:
        stmt = stmt.where(last_contact_subq.c.channel.in_(channels))
    return stmt


def _build_export_stmt(
    *,
    start: date | None,
    end: date | None,
    status: str | None,
    recall_type: str | None,
    contact_state: str | None,
    last_contact: str | None,
    method: str | None,
    contacted: str | None,
    contacted_within_days: int | None,
    contact_channel: str | None,
):
    requested_statuses, requested_type_members, stored_statuses = _normalize_recall_filters(
        status, recall_type
    )
    requested_status_members = _requested_status_members(requested_statuses)
    contact_flag, within_days, older_than_days, channels = _normalize_contact_filters(
        contact_state,
        last_contact,
        method,
        contacted,
        contacted_within_days,
        contact_channel,
    )
    last_contact_subq = _build_last_contact_subquery()
    stmt = _build_recall_query(
        start=start,
        end=end,
        stored_statuses=stored_statuses,
        requested_type_members=requested_type_members,
        limit=None,
        offset=None,
        last_contact_subq=last_contact_subq,
    )
    stmt = _apply_contact_filters(
        stmt,
        last_contact_subq=last_contact_subq,
        contact_flag=contact_flag,
        within_days=within_days,
        older_than_days=older_than_days,
        channels=channels,
    )
    resolved_status = _resolved_status_expr(date.today())
    if requested_status_members:
        stmt = stmt.where(resolved_status.in_(requested_status_members))
    return stmt, requested_statuses


def _build_recall_query(
    *,
    start: date | None,
    end: date | None,
    stored_statuses: set[PatientRecallStatus],
    requested_type_members: list[PatientRecallKind],
    limit: int | None,
    offset: int | None,
    last_contact_subq=None,
):
    if last_contact_subq is not None:
        stmt = (
            select(
                PatientRecall,
                Patient,
                last_contact_subq.c.contacted_at.label("last_contacted_at"),
                last_contact_subq.c.channel.label("last_contact_channel"),
                last_contact_subq.c.notes.label("last_contact_note"),
                last_contact_subq.c.other_detail.label("last_contact_other_detail"),
                last_contact_subq.c.outcome.label("last_contact_outcome"),
            )
            .join(Patient, PatientRecall.patient_id == Patient.id)
            .join(
                last_contact_subq,
                (last_contact_subq.c.recall_id == PatientRecall.id)
                & (last_contact_subq.c.rn == 1),
                isouter=True,
            )
        )
    else:
        stmt = select(PatientRecall, Patient).join(
            Patient, PatientRecall.patient_id == Patient.id
        )
    stmt = (
        stmt.where(Patient.deleted_at.is_(None))
        .order_by(PatientRecall.due_date.asc(), PatientRecall.id.asc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    if offset is not None:
        stmt = stmt.offset(offset)
    if stored_statuses:
        stmt = stmt.where(PatientRecall.status.in_(stored_statuses))
    if requested_type_members:
        stmt = stmt.where(PatientRecall.kind.in_(requested_type_members))
    if start:
        stmt = stmt.where(PatientRecall.due_date >= start)
    if end:
        stmt = stmt.where(PatientRecall.due_date <= end)
    return stmt


def _load_recall_dashboard_row(db: Session, recall_id: int) -> RecallDashboardRow:
    last_contact_subq = _build_last_contact_subquery()
    stmt = (
        select(
            PatientRecall,
            Patient,
            last_contact_subq.c.contacted_at.label("last_contacted_at"),
            last_contact_subq.c.channel.label("last_contact_channel"),
            last_contact_subq.c.notes.label("last_contact_note"),
            last_contact_subq.c.other_detail.label("last_contact_other_detail"),
            last_contact_subq.c.outcome.label("last_contact_outcome"),
        )
        .join(Patient, PatientRecall.patient_id == Patient.id)
        .join(
            last_contact_subq,
            (last_contact_subq.c.recall_id == PatientRecall.id)
            & (last_contact_subq.c.rn == 1),
            isouter=True,
        )
        .where(PatientRecall.id == recall_id)
        .where(Patient.deleted_at.is_(None))
    )
    row = db.execute(stmt).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recall not found")
    (
        recall,
        patient,
        last_contacted_at,
        last_contact_channel,
        last_contact_note,
        last_contact_other_detail,
        last_contact_outcome,
    ) = row
    resolved_status = resolve_recall_status(recall)
    return RecallDashboardRow(
        id=recall.id,
        patient_id=patient.id,
        first_name=patient.first_name,
        last_name=patient.last_name,
        recall_kind=recall.kind,
        due_date=recall.due_date,
        status=resolved_status,
        notes=recall.notes,
        completed_at=recall.completed_at,
        last_contacted_at=last_contacted_at,
        last_contact_channel=last_contact_channel,
        last_contact_method=last_contact_channel,
        last_contact_note=last_contact_note,
        last_contact_other_detail=last_contact_other_detail,
        last_contact_outcome=last_contact_outcome,
    )


@router.get("", response_model=list[RecallDashboardRow])
def list_recalls(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    status: str | None = Query(default=None),
    recall_type: str | None = Query(default=None, alias="type"),
    contact_state: str | None = Query(default=None),
    last_contact: str | None = Query(default=None),
    method: str | None = Query(default=None),
    contacted: str | None = Query(default=None),
    contacted_within_days: int | None = Query(default=None, ge=1, le=3650),
    contact_channel: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    start_time = time.perf_counter()
    requested_statuses, requested_type_members, stored_statuses = _normalize_recall_filters(
        status, recall_type
    )
    contact_flag, within_days, older_than_days, channels = _normalize_contact_filters(
        contact_state,
        last_contact,
        method,
        contacted,
        contacted_within_days,
        contact_channel,
    )
    last_contact_subq = _build_last_contact_subquery()
    stmt = _build_recall_query(
        start=start,
        end=end,
        stored_statuses=stored_statuses,
        requested_type_members=requested_type_members,
        limit=limit,
        offset=offset,
        last_contact_subq=last_contact_subq,
    )
    stmt = _apply_contact_filters(
        stmt,
        last_contact_subq=last_contact_subq,
        contact_flag=contact_flag,
        within_days=within_days,
        older_than_days=older_than_days,
        channels=channels,
    )

    results = db.execute(stmt).all()
    output: list[RecallDashboardRow] = []
    for (
        recall,
        patient,
        last_contacted_at,
        last_contact_channel,
        last_contact_note,
        last_contact_other_detail,
        last_contact_outcome,
    ) in results:
        resolved_status = resolve_recall_status(recall)
        if resolved_status.value not in requested_statuses:
            continue
        output.append(
            RecallDashboardRow(
                id=recall.id,
                patient_id=patient.id,
                first_name=patient.first_name,
                last_name=patient.last_name,
                recall_kind=recall.kind,
                due_date=recall.due_date,
                status=resolved_status,
                notes=recall.notes,
                completed_at=recall.completed_at,
                last_contacted_at=last_contacted_at,
                last_contact_channel=last_contact_channel,
                last_contact_method=last_contact_channel,
                last_contact_note=last_contact_note,
                last_contact_other_detail=last_contact_other_detail,
                last_contact_outcome=last_contact_outcome,
            )
        )
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info("perf: recalls_list_ms=%.2f rows=%d", elapsed_ms, len(output))
    return output


@router.post("/{recall_id}/contact", response_model=RecallDashboardRow)
def log_recall_contact(
    recall_id: int,
    payload: RecallContactCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    recall = db.get(PatientRecall, recall_id)
    if not recall:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recall not found")
    if (
        payload.method == PatientRecallCommunicationChannel.other
        and not (payload.other_detail or "").strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Other detail is required when method is other.",
        )

    entry = PatientRecallCommunication(
        patient_id=recall.patient_id,
        recall_id=recall.id,
        channel=payload.method,
        direction=PatientRecallCommunicationDirection.outbound,
        status=PatientRecallCommunicationStatus.sent,
        notes=payload.note,
        other_detail=payload.other_detail,
        outcome=payload.outcome,
        contacted_at=payload.contacted_at or datetime.now(timezone.utc),
        created_by_user_id=user.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    bump_export_count_cache_epoch("recalls.log_recall_contact")
    return _load_recall_dashboard_row(db, recall_id)


@router.get("/export.csv")
def export_recalls_csv(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    status: str | None = Query(default=None),
    recall_type: str | None = Query(default=None, alias="type"),
    contact_state: str | None = Query(default=None),
    last_contact: str | None = Query(default=None),
    method: str | None = Query(default=None),
    contacted: str | None = Query(default=None),
    contacted_within_days: int | None = Query(default=None, ge=1, le=3650),
    contact_channel: str | None = Query(default=None),
    page_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    start_time = time.perf_counter()
    stmt, _ = _build_export_stmt(
        start=start,
        end=end,
        status=status,
        recall_type=recall_type,
        contact_state=contact_state,
        last_contact=last_contact,
        method=method,
        contacted=contacted,
        contacted_within_days=contacted_within_days,
        contact_channel=contact_channel,
    )

    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = db.execute(count_stmt).scalar_one()
    if not page_only and total > MAX_EXPORT_ROWS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Too many recalls to export ({total}). Narrow your filters.",
        )
    if page_only:
        stmt = stmt.limit(limit).offset(offset)
    results = db.execute(stmt).all()
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "patient_id",
            "patient_name",
            "recall_type",
            "due_date",
            "status",
            "phone",
            "last_contacted_at",
            "last_contact_channel",
        ]
    )
    for recall, patient, last_contacted_at, last_contact_channel in results:
        resolved_status_value = resolve_recall_status(recall).value
        writer.writerow(
            [
                patient.id,
                f"{patient.last_name}, {patient.first_name}",
                recall.kind.value,
                recall.due_date.isoformat(),
                resolved_status_value,
                patient.phone or "",
                last_contacted_at.isoformat() if last_contacted_at else "",
                last_contact_channel.value if last_contact_channel else "",
            ]
        )
    filename = f"recalls-{date.today().isoformat()}.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info("perf: recalls_export_csv_ms=%.2f rows=%d", elapsed_ms, len(results))
    return Response(content=buffer.getvalue(), media_type="text/csv", headers=headers)


@router.get("/export_count")
def export_recalls_count(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    status: str | None = Query(default=None),
    recall_type: str | None = Query(default=None, alias="type"),
    contact_state: str | None = Query(default=None),
    last_contact: str | None = Query(default=None),
    method: str | None = Query(default=None),
    contacted: str | None = Query(default=None),
    contacted_within_days: int | None = Query(default=None, ge=1, le=3650),
    contact_channel: str | None = Query(default=None),
):
    start_time = time.perf_counter()
    cache_key = _export_count_cache_key(
        start=start,
        end=end,
        status=status,
        recall_type=recall_type,
        contact_state=contact_state,
        last_contact=last_contact,
        method=method,
        contacted=contacted,
        contacted_within_days=contacted_within_days,
        contact_channel=contact_channel,
    )
    cached = _export_count_cache_get(cache_key)
    if cached is not None:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "perf: recalls_export_count_ms=%.2f cache=hit count=%d", elapsed_ms, cached
        )
        return {"count": cached}

    stmt, _requested_statuses = _build_export_stmt(
        start=start,
        end=end,
        status=status,
        recall_type=recall_type,
        contact_state=contact_state,
        last_contact=last_contact,
        method=method,
        contacted=contacted,
        contacted_within_days=contacted_within_days,
        contact_channel=contact_channel,
    )
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = db.execute(count_stmt).scalar_one()
    _export_count_cache_set(cache_key, total)
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "perf: recalls_export_count_ms=%.2f cache=miss count=%d", elapsed_ms, total
    )
    return {"count": total}


@router.get("/letters.zip")
def export_recall_letters_zip(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    status: str | None = Query(default=None),
    recall_type: str | None = Query(default=None, alias="type"),
    contact_state: str | None = Query(default=None),
    last_contact: str | None = Query(default=None),
    method: str | None = Query(default=None),
    contacted: str | None = Query(default=None),
    contacted_within_days: int | None = Query(default=None, ge=1, le=3650),
    contact_channel: str | None = Query(default=None),
    page_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    start_time = time.perf_counter()
    stmt, _ = _build_export_stmt(
        start=start,
        end=end,
        status=status,
        recall_type=recall_type,
        contact_state=contact_state,
        last_contact=last_contact,
        method=method,
        contacted=contacted,
        contacted_within_days=contacted_within_days,
        contact_channel=contact_channel,
    )

    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = db.execute(count_stmt).scalar_one()
    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No recalls match your filters.",
        )
    if not page_only and total > MAX_EXPORT_ROWS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Too many recalls to export ({total}). Narrow your filters.",
        )
    if page_only:
        stmt = stmt.limit(limit).offset(offset)

    results = db.execute(stmt).all()
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for recall, patient, _last_contacted_at, _last_contact_channel in results:
            surname = _safe_filename_part(patient.last_name or "")
            forename = _safe_filename_part(patient.first_name or "")
            due_date = recall.due_date.isoformat()
            if surname or forename:
                name_part = "_".join(part for part in [surname, forename] if part)
                filename = (
                    f"RecallLetter_{name_part}_{patient.id}_{due_date}.pdf"
                )
            else:
                filename = f"RecallLetter_patient-{patient.id}_{due_date}.pdf"
            pdf_bytes = build_recall_letter_pdf(patient, recall)
            zipf.writestr(filename, pdf_bytes)
            log_recall_communication(
                db,
                patient_id=patient.id,
                recall_id=recall.id,
                channel=PatientRecallCommunicationChannel.letter,
                direction=PatientRecallCommunicationDirection.outbound,
                status=PatientRecallCommunicationStatus.sent,
                notes="Recall letters ZIP generated",
                created_by_user_id=user.id if user else None,
                guard_seconds=60,
            )
    filename = f"recall-letters-{date.today().isoformat()}.zip"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    db.commit()
    bump_export_count_cache_epoch("recalls.export_letters_zip")
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info("perf: recalls_export_zip_ms=%.2f rows=%d", elapsed_ms, len(results))
    return Response(content=buffer.getvalue(), media_type="application/zip", headers=headers)


@router.get("/kpis", response_model=RecallKpiOut)
def recall_kpis(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
):
    today = date.today()
    range_end = end or today
    range_start = start or (range_end - timedelta(days=30))

    base_filters = [
        Patient.deleted_at.is_(None),
        Patient.recall_due_date.is_not(None),
        Patient.recall_due_date >= range_start,
        Patient.recall_due_date <= range_end,
    ]

    counts_stmt = select(
        func.coalesce(
            func.sum(
                case(
                    (Patient.recall_status == RecallStatus.due, 1),
                    else_=0,
                )
            ),
            0,
        ).label("due"),
        func.coalesce(
            func.sum(
                case(
                    (
                        (Patient.recall_status == RecallStatus.due)
                        & (Patient.recall_due_date < today),
                        1,
                    ),
                    else_=0,
                )
            ),
            0,
        ).label("overdue"),
        func.coalesce(
            func.sum(
                case(
                    (
                        (Patient.recall_status == RecallStatus.contacted)
                        & (Patient.recall_last_contacted_at.is_not(None))
                        & (func.date(Patient.recall_last_contacted_at) >= range_start)
                        & (func.date(Patient.recall_last_contacted_at) <= range_end),
                        1,
                    ),
                    else_=0,
                )
            ),
            0,
        ).label("contacted"),
        func.coalesce(
            func.sum(
                case(
                    (Patient.recall_status == RecallStatus.booked, 1),
                    else_=0,
                )
            ),
            0,
        ).label("booked"),
        func.coalesce(
            func.sum(
                case(
                    (Patient.recall_status == RecallStatus.not_required, 1),
                    else_=0,
                )
            ),
            0,
        ).label("declined"),
    ).where(*base_filters)

    due, overdue, contacted, booked, declined = db.execute(counts_stmt).one()

    denominator = max(due + overdue, 0)
    contacted_rate = (contacted / denominator) if denominator else 0.0
    booked_denominator = contacted + booked
    booked_rate = (booked / booked_denominator) if booked_denominator else 0.0

    return RecallKpiOut(
        range={"from_date": range_start, "to_date": range_end},
        counts={
            "due": due,
            "overdue": overdue,
            "contacted": contacted,
            "booked": booked,
            "declined": declined,
        },
        rates={
            "contacted_rate": contacted_rate,
            "booked_rate": booked_rate,
        },
    )


@router.patch("/{patient_id}", response_model=PatientRecallSettingsOut)
def update_recall(
    patient_id: int,
    payload: RecallUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    before_data = snapshot_model(patient)
    if payload.interval_months is not None:
        patient.recall_interval_months = payload.interval_months
    if payload.due_date is not None:
        patient.recall_due_date = payload.due_date
    if payload.status is not None:
        patient.recall_status = payload.status
    if payload.recall_type is not None:
        patient.recall_type = payload.recall_type
    if payload.notes is not None:
        patient.recall_notes = payload.notes
    if payload.last_contacted_at is not None:
        patient.recall_last_contacted_at = payload.last_contacted_at
    elif payload.status == RecallStatus.contacted and not patient.recall_last_contacted_at:
        patient.recall_last_contacted_at = datetime.now(timezone.utc)

    if patient.recall_due_date and not patient.recall_status:
        patient.recall_status = RecallStatus.due
    if not patient.recall_due_date:
        patient.recall_status = None

    patient.recall_last_set_at = datetime.now(timezone.utc)
    patient.recall_last_set_by_user_id = user.id
    patient.updated_by_user_id = user.id
    patient.updated_at = datetime.now(timezone.utc)
    db.add(patient)
    _log_recall_timeline(
        db,
        actor=user,
        patient=patient,
        before_data=before_data or {},
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(patient)
    bump_export_count_cache_epoch("recalls.update_recall")
    return PatientRecallSettingsOut(
        id=patient.id,
        first_name=patient.first_name,
        last_name=patient.last_name,
        phone=patient.phone,
        postcode=patient.postcode,
        recall_interval_months=patient.recall_interval_months,
        recall_due_date=patient.recall_due_date,
        recall_status=patient.recall_status,
        recall_type=patient.recall_type,
        recall_last_contacted_at=patient.recall_last_contacted_at,
        recall_notes=patient.recall_notes,
        recall_last_set_at=patient.recall_last_set_at,
        balance_pence=None,
    )


@router.post("/{patient_id}/generate-document", response_model=PatientDocumentOut)
def generate_recall_document(
    patient_id: int,
    payload: PatientDocumentCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str | None = Header(default=None),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    template = db.get(DocumentTemplate, payload.template_id)
    if not template or template.deleted_at is not None or not template.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    title_input = payload.title or template.name
    rendered_title, title_unknown = render_template_with_warnings(title_input, patient)
    rendered, content_unknown = render_template_with_warnings(template.content, patient)
    unknown_fields = sorted({*title_unknown, *content_unknown})

    document = PatientDocument(
        patient_id=patient_id,
        template_id=template.id,
        title=rendered_title,
        rendered_content=rendered,
        created_by_user_id=user.id,
    )
    db.add(document)
    db.flush()
    log_event(
        db,
        actor=user,
        action="patient_document.created",
        entity_type="patient_document",
        entity_id=str(document.id),
        after_data={
            "patient_id": document.patient_id,
            "template_id": document.template_id,
            "title": document.title,
            "source": "recalls",
        },
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    log_event(
        db,
        actor=user,
        action="recall.letter_generated",
        entity_type="patient",
        entity_id=str(patient.id),
        after_data={
            "patient_document_id": document.id,
            "template_id": template.id,
            "pdf_available": True,
        },
        request_id=request_id,
        ip_address=request.client.host if request else None,
    )
    db.commit()
    db.refresh(document)
    output = PatientDocumentOut.model_validate(document)
    return output.model_copy(update={"unknown_fields": unknown_fields})
