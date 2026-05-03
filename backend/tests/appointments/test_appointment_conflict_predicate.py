from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.models.appointment import AppointmentStatus
from app.services.appointment_conflicts import (
    AppointmentConflictCandidate,
    AppointmentConflictPolicyError,
    ExistingAppointmentConflict,
    appointment_conflicts_with_existing,
    appointment_intervals_overlap,
    appointment_status_blocks_conflict,
)


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 15, hour, minute, tzinfo=timezone.utc)


def _candidate(
    *,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    clinician_user_id: int | None = 7,
    patient_id: int | None = 100,
) -> AppointmentConflictCandidate:
    return AppointmentConflictCandidate(
        starts_at=starts_at or _dt(9, 0),
        ends_at=ends_at or _dt(9, 30),
        clinician_user_id=clinician_user_id,
        patient_id=patient_id,
    )


def _existing(
    *,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    status: AppointmentStatus | str = AppointmentStatus.booked,
    clinician_user_id: int | None = 7,
    patient_id: int | None = 200,
    deleted: bool = False,
) -> ExistingAppointmentConflict:
    return ExistingAppointmentConflict(
        starts_at=starts_at or _dt(9, 15),
        ends_at=ends_at or _dt(9, 45),
        status=status,
        clinician_user_id=clinician_user_id,
        patient_id=patient_id,
        deleted=deleted,
    )


def test_overlapping_intervals_conflict_for_same_clinician():
    assert appointment_conflicts_with_existing(_candidate(), _existing()) is True


def test_exact_same_interval_conflicts():
    existing = _existing(starts_at=_dt(9, 0), ends_at=_dt(9, 30))

    assert appointment_conflicts_with_existing(_candidate(), existing) is True


def test_back_to_back_intervals_do_not_conflict():
    assert (
        appointment_conflicts_with_existing(
            _candidate(starts_at=_dt(9, 0), ends_at=_dt(9, 30)),
            _existing(starts_at=_dt(9, 30), ends_at=_dt(10, 0)),
        )
        is False
    )
    assert (
        appointment_conflicts_with_existing(
            _candidate(starts_at=_dt(9, 30), ends_at=_dt(10, 0)),
            _existing(starts_at=_dt(9, 0), ends_at=_dt(9, 30)),
        )
        is False
    )


def test_non_overlapping_intervals_do_not_conflict():
    assert (
        appointment_intervals_overlap(
            _dt(9, 0),
            _dt(9, 30),
            _dt(10, 0),
            _dt(10, 30),
        )
        is False
    )


@pytest.mark.parametrize(
    "status",
    [
        AppointmentStatus.booked,
        AppointmentStatus.arrived,
        AppointmentStatus.in_progress,
        AppointmentStatus.completed,
    ],
)
def test_blocking_existing_statuses(status: AppointmentStatus):
    assert appointment_status_blocks_conflict(status) is True
    assert (
        appointment_conflicts_with_existing(_candidate(), _existing(status=status))
        is True
    )


@pytest.mark.parametrize(
    "status",
    [
        AppointmentStatus.cancelled,
        AppointmentStatus.no_show,
        "cancelled",
        "no_show",
    ],
)
def test_cancelled_and_no_show_existing_statuses_do_not_block(
    status: AppointmentStatus | str,
):
    assert appointment_status_blocks_conflict(status) is False
    assert (
        appointment_conflicts_with_existing(_candidate(), _existing(status=status))
        is False
    )


def test_deleted_existing_appointment_does_not_block():
    assert (
        appointment_conflicts_with_existing(
            _candidate(),
            _existing(status=AppointmentStatus.booked, deleted=True),
        )
        is False
    )


def test_different_clinician_resources_do_not_conflict():
    assert (
        appointment_conflicts_with_existing(
            _candidate(clinician_user_id=7),
            _existing(clinician_user_id=8),
        )
        is False
    )


def test_missing_clinician_resource_does_not_conflict_to_match_core_query():
    assert (
        appointment_conflicts_with_existing(
            _candidate(clinician_user_id=None),
            _existing(clinician_user_id=7),
        )
        is False
    )
    assert (
        appointment_conflicts_with_existing(
            _candidate(clinician_user_id=7),
            _existing(clinician_user_id=None),
        )
        is False
    )


def test_patient_identity_does_not_change_conflict_predicate():
    candidate = _candidate(patient_id=100)

    assert (
        appointment_conflicts_with_existing(candidate, _existing(patient_id=100))
        is True
    )
    assert (
        appointment_conflicts_with_existing(candidate, _existing(patient_id=200))
        is True
    )


def test_timezone_aware_values_compare_by_instant():
    london = ZoneInfo("Europe/London")
    candidate = _candidate(
        starts_at=datetime(2026, 7, 15, 9, 0, tzinfo=london),
        ends_at=datetime(2026, 7, 15, 10, 0, tzinfo=london),
    )
    existing = _existing(
        starts_at=datetime(2026, 7, 15, 8, 30, tzinfo=timezone.utc),
        ends_at=datetime(2026, 7, 15, 9, 30, tzinfo=timezone.utc),
    )

    assert appointment_conflicts_with_existing(candidate, existing) is True


@pytest.mark.parametrize(
    "candidate, existing, error",
    [
        (
            AppointmentConflictCandidate(  # type: ignore[arg-type]
                starts_at=None,
                ends_at=_dt(9, 30),
                clinician_user_id=7,
            ),
            _existing(),
            "candidate starts_at is required",
        ),
        (
            AppointmentConflictCandidate(  # type: ignore[arg-type]
                starts_at=_dt(9, 0),
                ends_at=None,
                clinician_user_id=7,
            ),
            _existing(),
            "candidate ends_at is required",
        ),
        (
            _candidate(starts_at=datetime(2026, 1, 15, 9, 0)),
            _existing(),
            "candidate starts_at must be timezone-aware",
        ),
        (
            _candidate(starts_at=_dt(10, 0), ends_at=_dt(9, 0)),
            _existing(),
            "candidate ends_at must be after starts_at",
        ),
        (
            _candidate(),
            _existing(ends_at=datetime(2026, 1, 15, 9, 45)),
            "existing ends_at must be timezone-aware",
        ),
        (
            _candidate(),
            _existing(starts_at=_dt(10, 0), ends_at=_dt(9, 0)),
            "existing ends_at must be after starts_at",
        ),
    ],
)
def test_invalid_or_missing_datetime_values_fail_closed(
    candidate: AppointmentConflictCandidate,
    existing: ExistingAppointmentConflict,
    error: str,
):
    with pytest.raises(AppointmentConflictPolicyError, match=error):
        appointment_conflicts_with_existing(candidate, existing)


@pytest.mark.parametrize("status", [None, "unknown", "deleted"])
def test_unknown_or_missing_existing_status_fails_closed(status: str | None):
    with pytest.raises(
        AppointmentConflictPolicyError,
        match="status|required|unknown",
    ):
        appointment_status_blocks_conflict(status)
