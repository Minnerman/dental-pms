from __future__ import annotations

import pytest

from app.models.appointment import AppointmentStatus
from app.services.r4_import.appointment_status_policy import (
    R4AppointmentPolicyCategory,
    R4AppointmentPromotionDecision,
    map_r4_appointment_status,
)


def _map(
    *,
    status: str | None,
    appt_flag: int | str | None,
    cancelled: bool | int | str | None = False,
    patient_code: int | str | None = 1001,
    clinician_code: int | str | None = 10000047,
    clinic_code: int | str | None = 1,
    allow_live_in_progress: bool = False,
):
    return map_r4_appointment_status(
        status=status,
        cancelled=cancelled,
        appt_flag=appt_flag,
        patient_code=patient_code,
        clinician_code=clinician_code,
        clinic_code=clinic_code,
        allow_live_in_progress=allow_live_in_progress,
    )


@pytest.mark.parametrize(
    ("status", "appt_flag", "category", "core_status"),
    [
        (
            "Complete",
            1,
            R4AppointmentPolicyCategory.COMPLETED_CANDIDATE,
            AppointmentStatus.completed,
        ),
        (
            "Cancelled",
            2,
            R4AppointmentPolicyCategory.CANCELLED_CANDIDATE,
            AppointmentStatus.cancelled,
        ),
        (
            "Late Cancellation",
            9,
            R4AppointmentPolicyCategory.CANCELLED_CANDIDATE,
            AppointmentStatus.cancelled,
        ),
        (
            "Did Not Attend",
            3,
            R4AppointmentPolicyCategory.NO_SHOW_CANDIDATE,
            AppointmentStatus.no_show,
        ),
        (
            "Pending",
            6,
            R4AppointmentPolicyCategory.BOOKED_CANDIDATE,
            AppointmentStatus.booked,
        ),
    ],
)
def test_observed_statuses_with_direct_core_candidates(
    status: str,
    appt_flag: int,
    category: R4AppointmentPolicyCategory,
    core_status: AppointmentStatus,
):
    result = _map(status=status, appt_flag=appt_flag)

    assert result.decision == R4AppointmentPromotionDecision.PROMOTE_CANDIDATE
    assert result.category == category
    assert result.core_status == core_status
    assert result.can_promote is True
    assert result.fail_closed is False
    assert result.requires_clinician_mapping is True
    assert result.clinic_policy == "source_clinic_only"


def test_cancelled_true_takes_precedence_over_active_pending_status():
    result = _map(status="Pending", appt_flag=6, cancelled="1")

    assert result.decision == R4AppointmentPromotionDecision.PROMOTE_CANDIDATE
    assert result.category == R4AppointmentPolicyCategory.CANCELLED_CANDIDATE
    assert result.core_status == AppointmentStatus.cancelled
    assert result.reason == "cancelled_true_precedence"


def test_deleted_rows_are_excluded_from_core_diary_promotion():
    result = _map(status="Deleted", appt_flag=5)

    assert result.decision == R4AppointmentPromotionDecision.EXCLUDE
    assert result.category == R4AppointmentPolicyCategory.DELETED_EXCLUDED
    assert result.core_status is None
    assert result.can_promote is False
    assert result.fail_closed is True


def test_left_surgery_requires_confirmation_before_completed_mapping():
    result = _map(status="Left Surgery", appt_flag=11)

    assert result.decision == R4AppointmentPromotionDecision.MANUAL_REVIEW
    assert result.category == R4AppointmentPolicyCategory.COMPLETED_CONFIRMATION_NEEDED
    assert result.core_status == AppointmentStatus.completed
    assert result.can_promote is False
    assert result.fail_closed is True


def test_postponed_is_inactive_cancelled_candidate_but_requires_review():
    result = _map(status="Postponed", appt_flag=10)

    assert result.decision == R4AppointmentPromotionDecision.MANUAL_REVIEW
    assert result.category == R4AppointmentPolicyCategory.INACTIVE_CANCELLED_CANDIDATE
    assert result.core_status == AppointmentStatus.cancelled
    assert result.can_promote is False


def test_in_surgery_fails_closed_without_live_context():
    result = _map(status="In Surgery", appt_flag=8)

    assert result.decision == R4AppointmentPromotionDecision.MANUAL_REVIEW
    assert result.category == R4AppointmentPolicyCategory.IN_PROGRESS_CURRENT_ONLY
    assert result.core_status == AppointmentStatus.in_progress
    assert result.reason == "in_surgery_requires_live_context"
    assert result.can_promote is False


def test_in_surgery_can_be_candidate_only_when_live_context_is_explicit():
    result = _map(status="In Surgery", appt_flag=8, allow_live_in_progress=True)

    assert result.decision == R4AppointmentPromotionDecision.PROMOTE_CANDIDATE
    assert result.category == R4AppointmentPolicyCategory.IN_PROGRESS_CURRENT_ONLY
    assert result.core_status == AppointmentStatus.in_progress
    assert result.reason == "in_surgery_live_context_allowed"
    assert result.can_promote is True


def test_waiting_requires_manual_review_with_booked_candidate():
    result = _map(status="Waiting", appt_flag=7)

    assert result.decision == R4AppointmentPromotionDecision.MANUAL_REVIEW
    assert result.category == R4AppointmentPolicyCategory.WAITING_MANUAL_REVIEW
    assert result.core_status == AppointmentStatus.booked
    assert result.can_promote is False


def test_on_standby_requires_manual_review_without_core_equivalent():
    result = _map(status="On Standby", appt_flag=4)

    assert result.decision == R4AppointmentPromotionDecision.MANUAL_REVIEW
    assert result.category == R4AppointmentPolicyCategory.STANDBY_MANUAL_REVIEW
    assert result.core_status is None
    assert result.can_promote is False


def test_null_or_blank_patient_code_stays_read_only_only():
    result = _map(status="Pending", appt_flag=6, patient_code=" ")

    assert result.decision == R4AppointmentPromotionDecision.READ_ONLY_ONLY
    assert result.category == R4AppointmentPolicyCategory.NULL_PATIENT_READ_ONLY
    assert result.core_status is None
    assert result.patient_code_present is False
    assert result.can_promote is False
    assert result.fail_closed is True


@pytest.mark.parametrize(
    ("status", "appt_flag", "reason"),
    [
        ("Strange", 6, "unknown_status"),
        ("Pending", 99, "unknown_appt_flag"),
        ("Pending", "not-a-flag", "unknown_appt_flag"),
        (None, None, "missing_status_and_appt_flag"),
    ],
)
def test_unknown_or_incomplete_values_fail_closed(
    status: str | None,
    appt_flag: int | str | None,
    reason: str,
):
    result = _map(status=status, appt_flag=appt_flag)

    assert result.decision == R4AppointmentPromotionDecision.MANUAL_REVIEW
    assert result.category == R4AppointmentPolicyCategory.UNKNOWN_FAIL_CLOSED
    assert result.core_status is None
    assert result.reason == reason
    assert result.can_promote is False
    assert result.fail_closed is True


def test_conflicting_status_and_flag_combination_fails_closed():
    result = _map(status="Pending", appt_flag=1)

    assert result.decision == R4AppointmentPromotionDecision.MANUAL_REVIEW
    assert result.category == R4AppointmentPolicyCategory.CONFLICTING_STATUS_FLAG
    assert result.core_status is None
    assert result.reason == "status_appt_flag_conflict"
    assert result.can_promote is False
    assert result.fail_closed is True


def test_clinician_and_clinic_are_preserved_as_source_mapping_inputs():
    result = _map(
        status="Complete",
        appt_flag=1,
        clinician_code=10000047,
        clinic_code=1,
    )

    assert result.clinician_code_present is True
    assert result.requires_clinician_mapping is True
    assert result.clinic_code == 1
    assert result.clinic_policy == "source_clinic_only"
