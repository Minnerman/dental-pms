from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Iterable, Mapping

from app.models.appointment import AppointmentStatus
from app.services.r4_import.appointment_status_policy import (
    R4AppointmentPolicyCategory,
    R4AppointmentPromotionDecision,
    R4AppointmentStatusMapping,
    map_r4_appointment_status,
)

__all__ = [
    "R4AppointmentPromotionPlan",
    "R4AppointmentPromotionPlanAction",
    "R4AppointmentPromotionPlanInput",
    "R4AppointmentPromotionPlanRow",
    "build_appointment_promotion_plan",
]


class R4AppointmentPromotionPlanAction(str, Enum):
    PROMOTE = "promote"
    EXCLUDE = "exclude"
    MANUAL_REVIEW = "manual_review"
    NULL_PATIENT_READ_ONLY = "null_patient_read_only"
    PATIENT_UNMAPPED = "patient_unmapped"
    CLINICIAN_UNRESOLVED = "clinician_unresolved"


@dataclass(frozen=True)
class R4AppointmentPromotionPlanInput:
    legacy_appointment_id: int
    patient_code: int | str | None
    starts_at: datetime
    ends_at: datetime | None = None
    clinician_code: int | str | None = None
    status: str | None = None
    cancelled: bool | int | str | None = None
    clinic_code: int | str | None = None
    appointment_type: str | None = None
    appt_flag: int | str | None = None


@dataclass(frozen=True)
class R4AppointmentPromotionPlanRow:
    legacy_appointment_id: int
    action: R4AppointmentPromotionPlanAction
    reason: str
    patient_code: int | str | None
    patient_id: int | None
    clinician_code: int | str | None
    clinician_user_id: int | None
    starts_at: datetime
    ends_at: datetime | None
    core_status: AppointmentStatus | None
    policy_decision: R4AppointmentPromotionDecision
    policy_category: R4AppointmentPolicyCategory
    status_mapping: R4AppointmentStatusMapping
    appointment_type: str | None = None
    clinic_code: int | str | None = None

    @property
    def can_promote(self) -> bool:
        return self.action == R4AppointmentPromotionPlanAction.PROMOTE


@dataclass(frozen=True)
class R4AppointmentPromotionPlan:
    rows: tuple[R4AppointmentPromotionPlanRow, ...]
    action_counts: dict[str, int]
    reason_counts: dict[str, int]
    policy_category_counts: dict[str, int]
    core_status_counts: dict[str, int]
    samples_by_reason: dict[str, tuple[int, ...]]

    @property
    def total(self) -> int:
        return len(self.rows)

    @property
    def promote_rows(self) -> tuple[R4AppointmentPromotionPlanRow, ...]:
        return tuple(
            row
            for row in self.rows
            if row.action == R4AppointmentPromotionPlanAction.PROMOTE
        )


def build_appointment_promotion_plan(
    rows: Iterable[Any],
    *,
    patient_mapping: Mapping[int | str, int] | None = None,
    appointment_patient_links: Mapping[int | str, int] | None = None,
    clinician_user_mapping: Mapping[int | str, int] | None = None,
    require_clinician_user_mapping: bool = False,
    sample_limit: int = 10,
) -> R4AppointmentPromotionPlan:
    if sample_limit < 1:
        raise RuntimeError("sample_limit must be at least 1.")

    patient_mapping = patient_mapping or {}
    appointment_patient_links = appointment_patient_links or {}
    clinician_user_mapping = clinician_user_mapping or {}

    patient_lookup = _normalize_mapping(patient_mapping)
    appointment_link_lookup = _normalize_mapping(appointment_patient_links)
    clinician_lookup = _normalize_mapping(clinician_user_mapping)

    planned_rows: list[R4AppointmentPromotionPlanRow] = []
    action_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    policy_category_counts: Counter[str] = Counter()
    core_status_counts: Counter[str] = Counter()
    samples_by_reason: dict[str, list[int]] = defaultdict(list)

    for raw_row in rows:
        row = _coerce_input(raw_row)
        status_mapping = map_r4_appointment_status(
            status=row.status,
            cancelled=row.cancelled,
            appt_flag=row.appt_flag,
            patient_code=row.patient_code,
            clinician_code=row.clinician_code,
            clinic_code=row.clinic_code,
            allow_live_in_progress=False,
        )
        patient_id = _resolve_patient_id(
            row,
            patient_lookup=patient_lookup,
            appointment_link_lookup=appointment_link_lookup,
        )
        clinician_user_id = _resolve_clinician_user_id(row, clinician_lookup)
        action, reason = _classify_row(
            row,
            status_mapping=status_mapping,
            patient_id=patient_id,
            clinician_user_id=clinician_user_id,
            require_clinician_user_mapping=require_clinician_user_mapping,
        )
        planned = R4AppointmentPromotionPlanRow(
            legacy_appointment_id=row.legacy_appointment_id,
            action=action,
            reason=reason,
            patient_code=row.patient_code,
            patient_id=patient_id,
            clinician_code=row.clinician_code,
            clinician_user_id=clinician_user_id,
            starts_at=row.starts_at,
            ends_at=row.ends_at,
            core_status=(
                status_mapping.core_status
                if action == R4AppointmentPromotionPlanAction.PROMOTE
                else None
            ),
            policy_decision=status_mapping.decision,
            policy_category=status_mapping.category,
            status_mapping=status_mapping,
            appointment_type=row.appointment_type,
            clinic_code=row.clinic_code,
        )
        planned_rows.append(planned)

        action_counts[action.value] += 1
        reason_counts[reason] += 1
        policy_category_counts[status_mapping.category.value] += 1
        if planned.core_status is not None:
            core_status_counts[planned.core_status.value] += 1
        samples = samples_by_reason[reason]
        if len(samples) < sample_limit:
            samples.append(row.legacy_appointment_id)

    return R4AppointmentPromotionPlan(
        rows=tuple(planned_rows),
        action_counts=dict(sorted(action_counts.items())),
        reason_counts=dict(sorted(reason_counts.items())),
        policy_category_counts=dict(sorted(policy_category_counts.items())),
        core_status_counts=dict(sorted(core_status_counts.items())),
        samples_by_reason={
            reason: tuple(ids) for reason, ids in sorted(samples_by_reason.items())
        },
    )


def _classify_row(
    row: R4AppointmentPromotionPlanInput,
    *,
    status_mapping: R4AppointmentStatusMapping,
    patient_id: int | None,
    clinician_user_id: int | None,
    require_clinician_user_mapping: bool,
) -> tuple[R4AppointmentPromotionPlanAction, str]:
    if status_mapping.decision == R4AppointmentPromotionDecision.READ_ONLY_ONLY:
        return (
            R4AppointmentPromotionPlanAction.NULL_PATIENT_READ_ONLY,
            status_mapping.reason,
        )
    if status_mapping.decision == R4AppointmentPromotionDecision.EXCLUDE:
        return R4AppointmentPromotionPlanAction.EXCLUDE, status_mapping.reason
    if status_mapping.decision == R4AppointmentPromotionDecision.MANUAL_REVIEW:
        return R4AppointmentPromotionPlanAction.MANUAL_REVIEW, status_mapping.reason
    if not status_mapping.can_promote:
        return R4AppointmentPromotionPlanAction.MANUAL_REVIEW, status_mapping.reason
    if patient_id is None:
        return R4AppointmentPromotionPlanAction.PATIENT_UNMAPPED, "patient_mapping_missing"
    if (
        require_clinician_user_mapping
        and _has_value(row.clinician_code)
        and clinician_user_id is None
    ):
        return (
            R4AppointmentPromotionPlanAction.CLINICIAN_UNRESOLVED,
            "clinician_user_mapping_required",
        )
    return R4AppointmentPromotionPlanAction.PROMOTE, "eligible_for_guarded_promotion"


def _resolve_patient_id(
    row: R4AppointmentPromotionPlanInput,
    *,
    patient_lookup: Mapping[str, int],
    appointment_link_lookup: Mapping[str, int],
) -> int | None:
    appointment_linked_id = appointment_link_lookup.get(str(row.legacy_appointment_id))
    if appointment_linked_id is not None:
        return appointment_linked_id
    patient_key = _normalize_key(row.patient_code)
    if patient_key is None:
        return None
    return patient_lookup.get(patient_key)


def _resolve_clinician_user_id(
    row: R4AppointmentPromotionPlanInput,
    clinician_lookup: Mapping[str, int],
) -> int | None:
    clinician_key = _normalize_key(row.clinician_code)
    if clinician_key is None:
        return None
    return clinician_lookup.get(clinician_key)


def _normalize_mapping(mapping: Mapping[int | str, int]) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for key, value in mapping.items():
        normalized_key = _normalize_key(key)
        if normalized_key is not None:
            normalized[normalized_key] = int(value)
    return normalized


def _normalize_key(value: int | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return str(value)


def _has_value(value: int | str | None) -> bool:
    return _normalize_key(value) is not None


def _coerce_input(raw_row: Any) -> R4AppointmentPromotionPlanInput:
    if isinstance(raw_row, R4AppointmentPromotionPlanInput):
        return raw_row
    return R4AppointmentPromotionPlanInput(
        legacy_appointment_id=int(_get_attr(raw_row, "legacy_appointment_id")),
        patient_code=_get_attr(raw_row, "patient_code"),
        starts_at=_get_attr(raw_row, "starts_at"),
        ends_at=_get_attr(raw_row, "ends_at", None),
        clinician_code=_get_attr(raw_row, "clinician_code", None),
        status=_get_attr(raw_row, "status", None),
        cancelled=_get_attr(raw_row, "cancelled", None),
        clinic_code=_get_attr(raw_row, "clinic_code", None),
        appointment_type=_get_attr(raw_row, "appointment_type", None),
        appt_flag=_get_attr(raw_row, "appt_flag", None),
    )


def _get_attr(raw_row: Any, name: str, default: Any = ...):
    if isinstance(raw_row, Mapping):
        if default is ...:
            return raw_row[name]
        return raw_row.get(name, default)
    if default is ...:
        return getattr(raw_row, name)
    return getattr(raw_row, name, default)
