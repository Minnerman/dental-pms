from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.models.appointment import AppointmentStatus
from app.services.r4_import.status import normalize_status

__all__ = [
    "R4AppointmentPolicyCategory",
    "R4AppointmentPromotionDecision",
    "R4AppointmentStatusMapping",
    "map_r4_appointment_status",
]


class R4AppointmentPromotionDecision(str, Enum):
    PROMOTE_CANDIDATE = "promote_candidate"
    READ_ONLY_ONLY = "read_only_only"
    EXCLUDE = "exclude"
    MANUAL_REVIEW = "manual_review"


class R4AppointmentPolicyCategory(str, Enum):
    BOOKED_CANDIDATE = "booked_candidate"
    CANCELLED_CANDIDATE = "cancelled_candidate"
    COMPLETED_CANDIDATE = "completed_candidate"
    COMPLETED_CONFIRMATION_NEEDED = "completed_confirmation_needed"
    CONFLICTING_STATUS_FLAG = "conflicting_status_flag"
    DELETED_EXCLUDED = "deleted_excluded"
    INACTIVE_CANCELLED_CANDIDATE = "inactive_cancelled_candidate"
    IN_PROGRESS_CURRENT_ONLY = "in_progress_current_only"
    NO_SHOW_CANDIDATE = "no_show_candidate"
    NULL_PATIENT_READ_ONLY = "null_patient_read_only"
    STANDBY_MANUAL_REVIEW = "standby_manual_review"
    UNKNOWN_FAIL_CLOSED = "unknown_fail_closed"
    WAITING_MANUAL_REVIEW = "waiting_manual_review"


@dataclass(frozen=True)
class R4AppointmentStatusMapping:
    decision: R4AppointmentPromotionDecision
    category: R4AppointmentPolicyCategory
    core_status: AppointmentStatus | None
    reason: str
    normalized_status: str | None
    appt_flag: int | None
    cancelled: bool
    patient_code_present: bool
    clinician_code_present: bool
    requires_clinician_mapping: bool
    clinic_code: int | str | None
    clinic_policy: str
    fail_closed: bool

    @property
    def can_promote(self) -> bool:
        return (
            self.decision == R4AppointmentPromotionDecision.PROMOTE_CANDIDATE
            and not self.fail_closed
        )


_STATUS_KEYS = {
    "complete": "complete",
    "cancelled": "cancelled",
    "deleted": "deleted",
    "did not attend": "no_show",
    "pending": "pending",
    "left surgery": "left_surgery",
    "postponed": "postponed",
    "late cancellation": "late_cancellation",
    "in surgery": "in_surgery",
    "waiting": "waiting",
    "on standby": "standby",
}

_FLAG_KEYS = {
    1: "complete",
    2: "cancelled",
    3: "no_show",
    4: "standby",
    5: "deleted",
    6: "pending",
    7: "waiting",
    8: "in_surgery",
    9: "late_cancellation",
    10: "postponed",
    11: "left_surgery",
}


def map_r4_appointment_status(
    *,
    status: str | None,
    cancelled: bool | int | str | None,
    appt_flag: int | str | None,
    patient_code: int | str | None,
    clinician_code: int | str | None = None,
    clinic_code: int | str | None = None,
    allow_live_in_progress: bool = False,
) -> R4AppointmentStatusMapping:
    normalized_status = normalize_status(status)
    normalized_flag, flag_is_valid = _normalize_flag(appt_flag)
    cancelled_value = _normalize_bool(cancelled)
    patient_code_present = _has_value(patient_code)
    clinician_code_present = _has_value(clinician_code)
    common = _common_context(
        normalized_status=normalized_status,
        appt_flag=normalized_flag,
        cancelled=cancelled_value,
        patient_code_present=patient_code_present,
        clinician_code_present=clinician_code_present,
        clinic_code=clinic_code,
    )

    if not patient_code_present:
        return R4AppointmentStatusMapping(
            decision=R4AppointmentPromotionDecision.READ_ONLY_ONLY,
            category=R4AppointmentPolicyCategory.NULL_PATIENT_READ_ONLY,
            core_status=None,
            reason="null_or_blank_patient_code",
            fail_closed=True,
            **common,
        )

    if normalized_status is not None and normalized_status not in _STATUS_KEYS:
        return _fail_closed(common, "unknown_status")
    if not flag_is_valid or (
        normalized_flag is not None and normalized_flag not in _FLAG_KEYS
    ):
        return _fail_closed(common, "unknown_appt_flag")

    status_key = _STATUS_KEYS.get(normalized_status or "")
    flag_key = _FLAG_KEYS.get(normalized_flag) if normalized_flag is not None else None
    if status_key and flag_key and status_key != flag_key:
        return R4AppointmentStatusMapping(
            decision=R4AppointmentPromotionDecision.MANUAL_REVIEW,
            category=R4AppointmentPolicyCategory.CONFLICTING_STATUS_FLAG,
            core_status=None,
            reason="status_appt_flag_conflict",
            fail_closed=True,
            **common,
        )

    key = status_key or flag_key
    if key is None:
        return _fail_closed(common, "missing_status_and_appt_flag")

    if key == "deleted":
        return R4AppointmentStatusMapping(
            decision=R4AppointmentPromotionDecision.EXCLUDE,
            category=R4AppointmentPolicyCategory.DELETED_EXCLUDED,
            core_status=None,
            reason="deleted_rows_excluded_from_core_promotion",
            fail_closed=True,
            **common,
        )

    if cancelled_value:
        return _promotion_candidate(
            common,
            R4AppointmentPolicyCategory.CANCELLED_CANDIDATE,
            AppointmentStatus.cancelled,
            "cancelled_true_precedence",
        )

    if key in {"cancelled", "late_cancellation"}:
        return _promotion_candidate(
            common,
            R4AppointmentPolicyCategory.CANCELLED_CANDIDATE,
            AppointmentStatus.cancelled,
            f"{key}_status_or_flag",
        )
    if key == "no_show":
        return _promotion_candidate(
            common,
            R4AppointmentPolicyCategory.NO_SHOW_CANDIDATE,
            AppointmentStatus.no_show,
            "did_not_attend_status_or_flag",
        )
    if key == "complete":
        return _promotion_candidate(
            common,
            R4AppointmentPolicyCategory.COMPLETED_CANDIDATE,
            AppointmentStatus.completed,
            "complete_status_or_flag",
        )
    if key == "left_surgery":
        return _manual_review(
            common,
            R4AppointmentPolicyCategory.COMPLETED_CONFIRMATION_NEEDED,
            AppointmentStatus.completed,
            "left_surgery_requires_confirmation",
        )
    if key == "postponed":
        return _manual_review(
            common,
            R4AppointmentPolicyCategory.INACTIVE_CANCELLED_CANDIDATE,
            AppointmentStatus.cancelled,
            "postponed_requires_inactive_policy_confirmation",
        )
    if key == "pending":
        return _promotion_candidate(
            common,
            R4AppointmentPolicyCategory.BOOKED_CANDIDATE,
            AppointmentStatus.booked,
            "pending_status_or_flag",
        )
    if key == "waiting":
        return _manual_review(
            common,
            R4AppointmentPolicyCategory.WAITING_MANUAL_REVIEW,
            AppointmentStatus.booked,
            "waiting_requires_operator_policy",
        )
    if key == "standby":
        return _manual_review(
            common,
            R4AppointmentPolicyCategory.STANDBY_MANUAL_REVIEW,
            None,
            "standby_has_no_core_equivalent",
        )
    if key == "in_surgery":
        if allow_live_in_progress:
            return _promotion_candidate(
                common,
                R4AppointmentPolicyCategory.IN_PROGRESS_CURRENT_ONLY,
                AppointmentStatus.in_progress,
                "in_surgery_live_context_allowed",
            )
        return _manual_review(
            common,
            R4AppointmentPolicyCategory.IN_PROGRESS_CURRENT_ONLY,
            AppointmentStatus.in_progress,
            "in_surgery_requires_live_context",
        )

    return _fail_closed(common, "unmapped_policy_key")


def _common_context(
    *,
    normalized_status: str | None,
    appt_flag: int | None,
    cancelled: bool,
    patient_code_present: bool,
    clinician_code_present: bool,
    clinic_code: int | str | None,
) -> dict[str, object]:
    return {
        "normalized_status": normalized_status,
        "appt_flag": appt_flag,
        "cancelled": cancelled,
        "patient_code_present": patient_code_present,
        "clinician_code_present": clinician_code_present,
        "requires_clinician_mapping": clinician_code_present,
        "clinic_code": clinic_code,
        "clinic_policy": (
            "source_clinic_only" if _has_value(clinic_code) else "missing_source_clinic"
        ),
    }


def _promotion_candidate(
    common: dict[str, object],
    category: R4AppointmentPolicyCategory,
    core_status: AppointmentStatus,
    reason: str,
) -> R4AppointmentStatusMapping:
    return R4AppointmentStatusMapping(
        decision=R4AppointmentPromotionDecision.PROMOTE_CANDIDATE,
        category=category,
        core_status=core_status,
        reason=reason,
        fail_closed=False,
        **common,
    )


def _manual_review(
    common: dict[str, object],
    category: R4AppointmentPolicyCategory,
    core_status: AppointmentStatus | None,
    reason: str,
) -> R4AppointmentStatusMapping:
    return R4AppointmentStatusMapping(
        decision=R4AppointmentPromotionDecision.MANUAL_REVIEW,
        category=category,
        core_status=core_status,
        reason=reason,
        fail_closed=True,
        **common,
    )


def _fail_closed(
    common: dict[str, object],
    reason: str,
) -> R4AppointmentStatusMapping:
    return R4AppointmentStatusMapping(
        decision=R4AppointmentPromotionDecision.MANUAL_REVIEW,
        category=R4AppointmentPolicyCategory.UNKNOWN_FAIL_CLOSED,
        core_status=None,
        reason=reason,
        fail_closed=True,
        **common,
    )


def _normalize_flag(value: int | str | None) -> tuple[int | None, bool]:
    if value is None:
        return None, True
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None, True
        try:
            return int(cleaned), True
        except ValueError:
            return None, False
    return int(value), True


def _normalize_bool(value: bool | int | str | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in {"1", "true", "yes", "y"}:
            return True
        if cleaned in {"0", "false", "no", "n", ""}:
            return False
        return True
    return bool(value)


def _has_value(value: int | str | None) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True
