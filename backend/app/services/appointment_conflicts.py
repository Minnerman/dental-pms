from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models.appointment import AppointmentStatus

__all__ = [
    "APPOINTMENT_CONFLICT_NON_BLOCKING_STATUSES",
    "AppointmentConflictCandidate",
    "AppointmentConflictPolicyError",
    "ExistingAppointmentConflict",
    "appointment_conflicts_with_existing",
    "appointment_intervals_overlap",
    "appointment_status_blocks_conflict",
]


APPOINTMENT_CONFLICT_NON_BLOCKING_STATUSES = frozenset(
    {
        AppointmentStatus.cancelled,
        AppointmentStatus.no_show,
    }
)


class AppointmentConflictPolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class AppointmentConflictCandidate:
    starts_at: datetime
    ends_at: datetime
    clinician_user_id: int | None = None
    patient_id: int | None = None


@dataclass(frozen=True)
class ExistingAppointmentConflict:
    starts_at: datetime
    ends_at: datetime
    status: AppointmentStatus | str
    clinician_user_id: int | None = None
    patient_id: int | None = None
    deleted: bool = False


def appointment_conflicts_with_existing(
    candidate: AppointmentConflictCandidate,
    existing: ExistingAppointmentConflict,
) -> bool:
    """Match the core update-route overlap semantics without DB access.

    The current core query is clinician-scoped, ignores soft-deleted rows, and
    treats cancelled/no-show appointments as non-blocking. Candidate status is
    intentionally outside this predicate; callers decide whether a candidate
    should run conflict checks before applying it.
    """

    _validate_window(candidate.starts_at, candidate.ends_at, label="candidate")
    _validate_window(existing.starts_at, existing.ends_at, label="existing")

    if existing.deleted:
        return False
    if not appointment_status_blocks_conflict(existing.status):
        return False
    if not candidate.clinician_user_id or not existing.clinician_user_id:
        return False
    if candidate.clinician_user_id != existing.clinician_user_id:
        return False
    return appointment_intervals_overlap(
        candidate.starts_at,
        candidate.ends_at,
        existing.starts_at,
        existing.ends_at,
    )


def appointment_intervals_overlap(
    candidate_starts_at: datetime,
    candidate_ends_at: datetime,
    existing_starts_at: datetime,
    existing_ends_at: datetime,
) -> bool:
    _validate_window(candidate_starts_at, candidate_ends_at, label="candidate")
    _validate_window(existing_starts_at, existing_ends_at, label="existing")
    return (
        existing_starts_at < candidate_ends_at
        and existing_ends_at > candidate_starts_at
    )


def appointment_status_blocks_conflict(status: AppointmentStatus | str | None) -> bool:
    if status is None:
        raise AppointmentConflictPolicyError("existing appointment status is required.")
    try:
        normalized = (
            status
            if isinstance(status, AppointmentStatus)
            else AppointmentStatus(str(status))
        )
    except ValueError as exc:
        raise AppointmentConflictPolicyError(
            f"unknown appointment status: {status!r}"
        ) from exc
    return normalized not in APPOINTMENT_CONFLICT_NON_BLOCKING_STATUSES


def _validate_window(
    starts_at: datetime | None,
    ends_at: datetime | None,
    *,
    label: str,
) -> None:
    if starts_at is None:
        raise AppointmentConflictPolicyError(f"{label} starts_at is required.")
    if ends_at is None:
        raise AppointmentConflictPolicyError(f"{label} ends_at is required.")
    if not _is_timezone_aware(starts_at):
        raise AppointmentConflictPolicyError(
            f"{label} starts_at must be timezone-aware."
        )
    if not _is_timezone_aware(ends_at):
        raise AppointmentConflictPolicyError(
            f"{label} ends_at must be timezone-aware."
        )
    if ends_at <= starts_at:
        raise AppointmentConflictPolicyError(
            f"{label} ends_at must be after starts_at."
        )


def _is_timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None
