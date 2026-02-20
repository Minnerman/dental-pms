from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.appointment import Appointment, AppointmentLocationType, AppointmentStatus
from app.models.note import Note
from app.models.user import User
from app.schemas.appointment import (
    DiarySnapshotAppointmentOut,
    DiarySnapshotColumnOut,
    DiarySnapshotFlagsOut,
    DiarySnapshotOut,
)

SnapshotView = Literal["day", "week"]

DEFAULT_START_MINUTES = 8 * 60
DEFAULT_END_MINUTES = 18 * 60
TIME_STEP_MINUTES = 10


def _resolve_window(anchor_date: date, view: SnapshotView) -> tuple[date, date]:
    if view == "day":
        return anchor_date, anchor_date
    week_start = anchor_date - timedelta(days=anchor_date.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def _mask_patient_name(full_name: str, patient_id: int | None) -> str:
    parts = [part for part in full_name.split() if part]
    if not parts:
        suffix = str(patient_id) if patient_id is not None else "unknown"
        return f"Patient {suffix}"
    masked = [f"{part[0].upper()}***" for part in parts[:2]]
    return " ".join(masked)


def _patient_display_name(appointment: Appointment, mask_names: bool) -> str:
    patient = appointment.patient
    if not patient:
        return "Unlinked"
    full_name = f"{patient.first_name} {patient.last_name}".strip()
    if not mask_names:
        return full_name or f"Patient {patient.id}"
    return _mask_patient_name(full_name, patient.id)


def _label_for_clinician(appointment: Appointment, user_map: dict[int, User]) -> str | None:
    clinician_user_id = appointment.clinician_user_id
    if not clinician_user_id:
        return appointment.clinician or None
    clinician = user_map.get(clinician_user_id)
    if clinician:
        if clinician.full_name.strip():
            return clinician.full_name.strip()
        return clinician.email
    return appointment.clinician or f"Clinician {clinician_user_id}"


def _location_label(appointment: Appointment) -> str | None:
    if appointment.location and appointment.location.strip():
        return appointment.location.strip()
    if appointment.location_text and appointment.location_text.strip():
        return appointment.location_text.strip()
    return None


def _column_key(
    appointment: Appointment,
) -> tuple[str, Literal["clinician", "chair"], str]:
    if appointment.clinician_user_id:
        key = f"clinician:{appointment.clinician_user_id}"
        return key, "clinician", key
    location = _location_label(appointment)
    if location:
        normalized = location.lower().replace(" ", "_")
        return f"chair:{normalized}", "chair", location
    return "chair:unassigned", "chair", "Unassigned"


def _minutes_from_datetime(value: datetime) -> int:
    localized = value.astimezone(timezone.utc)
    return localized.hour * 60 + localized.minute


def _round_down_to_step(value: int, step: int) -> int:
    return max(0, (value // step) * step)


def _round_up_to_step(value: int, step: int) -> int:
    if value % step == 0:
        return value
    return ((value // step) + 1) * step


def _time_label(minutes: int) -> str:
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def _build_time_blocks(appointments: list[Appointment]) -> list[str]:
    if not appointments:
        start_minutes = DEFAULT_START_MINUTES
        end_minutes = DEFAULT_END_MINUTES
    else:
        start_minutes = min(_minutes_from_datetime(appt.starts_at) for appt in appointments)
        end_minutes = max(_minutes_from_datetime(appt.ends_at) for appt in appointments)
        start_minutes = min(start_minutes, DEFAULT_START_MINUTES)
        end_minutes = max(end_minutes, DEFAULT_END_MINUTES)

    start_minutes = _round_down_to_step(start_minutes, TIME_STEP_MINUTES)
    end_minutes = _round_up_to_step(end_minutes, TIME_STEP_MINUTES)
    if end_minutes <= start_minutes:
        end_minutes = start_minutes + TIME_STEP_MINUTES

    blocks: list[str] = []
    cursor = start_minutes
    while cursor <= end_minutes:
        blocks.append(_time_label(cursor))
        cursor += TIME_STEP_MINUTES
    return blocks


def build_appointments_snapshot(
    db: Session,
    anchor_date: date,
    view: SnapshotView,
    mask_names: bool = True,
) -> DiarySnapshotOut:
    range_start, range_end = _resolve_window(anchor_date, view)
    start_dt = datetime.combine(range_start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(range_end + timedelta(days=1), time.min, tzinfo=timezone.utc)

    stmt = (
        select(Appointment)
        .where(Appointment.deleted_at.is_(None))
        .where(Appointment.patient_id.is_not(None))
        .where(Appointment.starts_at >= start_dt, Appointment.starts_at < end_dt)
        .options(selectinload(Appointment.patient))
        .order_by(Appointment.starts_at.asc(), Appointment.id.asc())
    )
    appointments = list(db.scalars(stmt))

    appointment_ids = [appt.id for appt in appointments]
    note_appointment_ids: set[int] = set()
    if appointment_ids:
        note_stmt = (
            select(Note.appointment_id)
            .where(Note.deleted_at.is_(None))
            .where(Note.appointment_id.in_(appointment_ids))
            .where(Note.appointment_id.is_not(None))
            .group_by(Note.appointment_id)
        )
        note_appointment_ids = {row for row in db.scalars(note_stmt) if row is not None}

    clinician_ids = sorted({appt.clinician_user_id for appt in appointments if appt.clinician_user_id})
    user_map: dict[int, User] = {}
    if clinician_ids:
        clinician_stmt = select(User).where(User.id.in_(clinician_ids))
        user_map = {user.id: user for user in db.scalars(clinician_stmt)}

    columns_by_key: dict[str, DiarySnapshotColumnOut] = {}
    snapshot_items: list[DiarySnapshotAppointmentOut] = []
    summary: dict[str, int] = {
        "total_appointments": len(appointments),
        "total_with_notes": 0,
        "total_with_alerts": 0,
        "location_clinic": 0,
        "location_visit": 0,
    }

    for appointment in appointments:
        key, kind, label_source = _column_key(appointment)
        clinician_label = _label_for_clinician(appointment, user_map)
        if key not in columns_by_key:
            columns_by_key[key] = DiarySnapshotColumnOut(
                key=key,
                label=clinician_label if kind == "clinician" and clinician_label else label_source,
                kind=kind,
                appointment_count=0,
                clinician_user_id=appointment.clinician_user_id if kind == "clinician" else None,
                location=_location_label(appointment) if kind == "chair" else None,
                location_type=appointment.location_type if kind == "chair" else None,
            )

        column = columns_by_key[key]
        column.appointment_count += 1

        has_notes = appointment.id in note_appointment_ids
        has_alerts = appointment.patient_has_alerts
        has_cancel_reason = bool((appointment.cancel_reason or "").strip())

        if has_notes:
            summary["total_with_notes"] += 1
        if has_alerts:
            summary["total_with_alerts"] += 1
        if appointment.location_type == AppointmentLocationType.visit:
            summary["location_visit"] += 1
        else:
            summary["location_clinic"] += 1

        status_key = f"status_{appointment.status.value}"
        summary[status_key] = summary.get(status_key, 0) + 1

        duration_minutes = max(
            0,
            int((appointment.ends_at - appointment.starts_at).total_seconds() // 60),
        )
        snapshot_items.append(
            DiarySnapshotAppointmentOut(
                id=appointment.id,
                starts_at=appointment.starts_at,
                ends_at=appointment.ends_at,
                duration_minutes=duration_minutes,
                status=appointment.status,
                appointment_type=appointment.appointment_type,
                patient_id=appointment.patient_id,
                patient_display_name=_patient_display_name(appointment, mask_names=mask_names),
                clinician_user_id=appointment.clinician_user_id,
                clinician_label=clinician_label,
                location=_location_label(appointment),
                location_type=appointment.location_type,
                is_domiciliary=appointment.is_domiciliary,
                column_key=key,
                flags=DiarySnapshotFlagsOut(
                    has_notes=has_notes,
                    has_patient_alerts=has_alerts,
                    has_cancel_reason=has_cancel_reason,
                ),
            )
        )

    columns = sorted(
        columns_by_key.values(),
        key=lambda item: (0 if item.kind == "clinician" else 1, item.label.lower()),
    )
    summary["total_columns"] = len(columns)

    time_blocks = _build_time_blocks(appointments)
    summary["total_time_blocks"] = len(time_blocks)

    return DiarySnapshotOut(
        date=anchor_date,
        view=view,
        range_start=range_start,
        range_end=range_end,
        columns=columns,
        time_blocks=time_blocks,
        appointments=snapshot_items,
        summary=summary,
    )


def collect_diary_day_metrics(db: Session) -> list[dict[str, int | str | date]]:
    day_expr = func.date(Appointment.starts_at)
    normalized_type = func.lower(func.coalesce(Appointment.appointment_type, ""))
    emergency_expr = case((normalized_type.like("%emerg%"), 1), else_=0)
    block_expr = case((normalized_type.like("%block%"), 1), else_=0)
    disruption_expr = case(
        (
            Appointment.status.in_(
                [AppointmentStatus.cancelled, AppointmentStatus.no_show]
            ),
            1,
        ),
        else_=0,
    )
    chair_expr = func.coalesce(func.nullif(Appointment.location, ""), "UNASSIGNED")

    stmt = (
        select(
            day_expr.label("day"),
            func.count(Appointment.id).label("total"),
            func.count(func.distinct(Appointment.clinician_user_id)).label("clinicians"),
            func.count(func.distinct(chair_expr)).label("chairs"),
            func.sum(emergency_expr).label("emergency_like"),
            func.sum(block_expr).label("block_like"),
            func.sum(disruption_expr).label("disruption_like"),
        )
        .where(Appointment.deleted_at.is_(None))
        .where(Appointment.patient_id.is_not(None))
        .group_by(day_expr)
        .order_by(day_expr.asc())
    )

    metrics: list[dict[str, int | str | date]] = []
    for row in db.execute(stmt):
        day_value = row.day
        if isinstance(day_value, datetime):
            day_key = day_value.date()
        elif isinstance(day_value, date):
            day_key = day_value
        else:
            day_key = datetime.fromisoformat(str(day_value)).date()
        metrics.append(
            {
                "day": day_key,
                "total": int(row.total or 0),
                "clinicians": int(row.clinicians or 0),
                "chairs": int(row.chairs or 0),
                "emergency_like": int(row.emergency_like or 0),
                "block_like": int(row.block_like or 0),
                "disruption_like": int(row.disruption_like or 0),
            }
        )
    return metrics


def select_representative_diary_dates(
    metrics: list[dict[str, int | str | date]],
) -> list[dict[str, int | str | date | bool]]:
    if not metrics:
        return []

    used_days: set[date] = set()
    totals_sorted = sorted(int(item["total"]) for item in metrics)
    median_total = totals_sorted[len(totals_sorted) // 2]

    def pick(
        category: str,
        candidates: list[dict[str, int | str | date]],
        note: str = "",
        fallback: bool = False,
    ) -> dict[str, int | str | date | bool] | None:
        for candidate in candidates:
            day_value = candidate["day"]
            assert isinstance(day_value, date)
            if day_value in used_days:
                continue
            used_days.add(day_value)
            selected: dict[str, int | str | date | bool] = dict(candidate)
            selected["category"] = category
            if note:
                selected["note"] = note
            if fallback:
                selected["fallback"] = True
            return selected
        return None

    by_total_desc = sorted(
        metrics,
        key=lambda item: (int(item["total"]), str(item["day"])),
        reverse=True,
    )
    by_total_asc = sorted(metrics, key=lambda item: (int(item["total"]), str(item["day"])))
    by_median_distance = sorted(
        metrics,
        key=lambda item: (
            abs(int(item["total"]) - median_total),
            -int(item["total"]),
            str(item["day"]),
        ),
    )
    by_mixed_density = sorted(
        metrics,
        key=lambda item: (
            int(item["clinicians"]) + int(item["chairs"]),
            int(item["total"]),
            str(item["day"]),
        ),
        reverse=True,
    )
    by_emergency_signal = sorted(
        metrics,
        key=lambda item: (
            int(item["emergency_like"]) + int(item["block_like"]),
            int(item["disruption_like"]),
            int(item["total"]),
            str(item["day"]),
        ),
        reverse=True,
    )

    selections: list[dict[str, int | str | date | bool]] = []
    for category, candidates, note in [
        ("busy_day", by_total_desc, ""),
        ("medium_day", by_median_distance, ""),
        ("light_day", by_total_asc, ""),
        ("mixed_clinician_chair_day", by_mixed_density, ""),
    ]:
        picked = pick(category, candidates, note=note)
        if picked:
            selections.append(picked)

    top_emergency = by_emergency_signal[0]
    emergency_signal = int(top_emergency["emergency_like"]) + int(top_emergency["block_like"])
    emergency_note = ""
    emergency_fallback = False
    if emergency_signal <= 0:
        emergency_note = (
            "No emergency/block markers found in current DB; selected highest-signal fallback."
        )
        emergency_fallback = True
    emergency_pick = pick(
        "emergency_or_block_day",
        by_emergency_signal,
        note=emergency_note,
        fallback=emergency_fallback,
    )
    if emergency_pick:
        selections.append(emergency_pick)

    if len(selections) < 5:
        remaining = [item for item in by_total_desc if item["day"] not in used_days]
        for candidate in remaining:
            filled = pick("additional_day", [candidate], note="Filled to reach five representative dates.")
            if filled:
                selections.append(filled)
            if len(selections) >= 5:
                break

    return selections[:5]
