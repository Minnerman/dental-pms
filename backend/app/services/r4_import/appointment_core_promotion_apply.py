from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Iterable, Mapping

from app.models.appointment import Appointment, AppointmentLocationType, AppointmentStatus
from app.services.appointment_conflicts import (
    AppointmentConflictCandidate,
    AppointmentConflictPolicyError,
    ExistingAppointmentConflict,
    appointment_conflicts_with_existing,
    appointment_status_blocks_conflict,
)
from app.services.r4_import.appointment_datetime_policy import (
    R4AppointmentDateTimePolicyError,
    map_r4_appointment_datetime,
)
from app.services.r4_import.appointment_promotion_dryrun import (
    ensure_scratch_database_url,
)
from app.services.r4_import.appointment_promotion_plan import (
    R4AppointmentPromotionPlanAction,
    build_appointment_promotion_plan,
)

__all__ = [
    "GUARDED_CORE_PROMOTION_CONFIRMATION",
    "GuardedCoreAppointmentPromotionApplyCandidate",
    "GuardedCoreAppointmentPromotionApplyError",
    "GuardedCoreAppointmentPromotionApplyPlan",
    "GuardedCoreAppointmentPromotionApplyRow",
    "GuardedCoreAppointmentPromotionApplyRowAction",
    "build_guarded_core_appointment_promotion_apply_plan",
    "build_scratch_core_appointment_models_for_guarded_apply",
]


GUARDED_CORE_PROMOTION_CONFIRMATION = "SCRATCH_APPLY"


class GuardedCoreAppointmentPromotionApplyError(RuntimeError):
    pass


class GuardedCoreAppointmentPromotionApplyRowAction(str, Enum):
    CREATE = "create"
    REFUSE = "refuse"
    SKIP = "skip"


@dataclass(frozen=True)
class GuardedCoreAppointmentPromotionApplyCandidate:
    legacy_source: str
    legacy_id: str
    legacy_patient_code: str | None
    source_legacy_appointment_id: int
    patient_id: int
    clinician_user_id: int | None
    starts_at: datetime
    ends_at: datetime
    status: AppointmentStatus
    appointment_type: str | None
    location_type: AppointmentLocationType
    location: str | None
    location_text: str | None

    def appointment_kwargs(self, *, actor_id: int) -> dict[str, object]:
        return {
            "legacy_source": self.legacy_source,
            "legacy_id": self.legacy_id,
            "legacy_patient_code": self.legacy_patient_code,
            "patient_id": self.patient_id,
            "clinician_user_id": self.clinician_user_id,
            "starts_at": self.starts_at,
            "ends_at": self.ends_at,
            "status": self.status,
            "appointment_type": self.appointment_type,
            "location": self.location,
            "location_type": self.location_type,
            "location_text": self.location_text,
            "is_domiciliary": False,
            "created_by_user_id": actor_id,
            "updated_by_user_id": actor_id,
        }


@dataclass(frozen=True)
class GuardedCoreAppointmentPromotionApplyRow:
    legacy_appointment_id: int
    action: GuardedCoreAppointmentPromotionApplyRowAction
    reason: str
    patient_id: int | None
    clinician_user_id: int | None
    status: AppointmentStatus | None
    candidate: GuardedCoreAppointmentPromotionApplyCandidate | None = None


@dataclass(frozen=True)
class GuardedCoreAppointmentPromotionApplyPlan:
    source_database: str
    legacy_source: str
    dryrun_report_verified: bool
    confirmation_token: str
    scratch_only: bool
    total_considered: int
    would_create_count: int
    would_update_count: int
    skipped_count: int
    refused_count: int
    core_appointments_before: int
    expected_core_appointments_after: int
    action_counts: dict[str, int]
    reason_counts: dict[str, int]
    promotion_plan_action_counts: dict[str, int]
    promotion_plan_reason_counts: dict[str, int]
    samples_by_reason: dict[str, tuple[int, ...]]
    rows: tuple[GuardedCoreAppointmentPromotionApplyRow, ...]

    @property
    def create_rows(self) -> tuple[GuardedCoreAppointmentPromotionApplyRow, ...]:
        return tuple(
            row
            for row in self.rows
            if row.action == GuardedCoreAppointmentPromotionApplyRowAction.CREATE
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "source_database": self.source_database,
            "legacy_source": self.legacy_source,
            "dryrun_report_verified": self.dryrun_report_verified,
            "confirmation_token": self.confirmation_token,
            "scratch_only": self.scratch_only,
            "total_considered": self.total_considered,
            "would_create_count": self.would_create_count,
            "would_update_count": self.would_update_count,
            "skipped_count": self.skipped_count,
            "refused_count": self.refused_count,
            "core_appointments": {
                "before": self.core_appointments_before,
                "expected_after": self.expected_core_appointments_after,
            },
            "action_counts": self.action_counts,
            "reason_counts": self.reason_counts,
            "promotion_plan_action_counts": self.promotion_plan_action_counts,
            "promotion_plan_reason_counts": self.promotion_plan_reason_counts,
            "samples_by_reason": {
                reason: list(ids) for reason, ids in self.samples_by_reason.items()
            },
            "create_samples": [
                _row_as_dict(row)
                for row in self.create_rows[:10]
                if row.candidate is not None
            ],
        }


def build_guarded_core_appointment_promotion_apply_plan(
    rows: Iterable[Any],
    *,
    database_url: str,
    confirm: str,
    dryrun_report: Mapping[str, Any],
    patient_mapping: Mapping[int | str, int] | None = None,
    appointment_patient_links: Mapping[int | str, int] | None = None,
    clinician_user_mapping: Mapping[int | str, int] | None = None,
    require_clinician_user_mapping: bool = False,
    existing_core_appointments: Iterable[ExistingAppointmentConflict] = (),
    existing_core_legacy_ids: Iterable[int | str] = (),
    legacy_source: str = "r4",
    core_appointments_before: int = 0,
    sample_limit: int = 10,
) -> GuardedCoreAppointmentPromotionApplyPlan:
    if confirm != GUARDED_CORE_PROMOTION_CONFIRMATION:
        raise GuardedCoreAppointmentPromotionApplyError(
            "Guarded core appointment promotion requires --confirm SCRATCH_APPLY."
        )
    if sample_limit < 1:
        raise GuardedCoreAppointmentPromotionApplyError(
            "sample_limit must be at least 1."
        )

    source_database = ensure_scratch_database_url(database_url)
    _verify_previous_dryrun_report(
        dryrun_report,
        require_clinician_user_mapping=require_clinician_user_mapping,
    )

    promotion_plan = build_appointment_promotion_plan(
        rows,
        patient_mapping=patient_mapping,
        appointment_patient_links=appointment_patient_links,
        clinician_user_mapping=clinician_user_mapping,
        require_clinician_user_mapping=require_clinician_user_mapping,
        sample_limit=sample_limit,
    )
    _verify_no_unmapped_promote_candidates(promotion_plan.action_counts)
    if require_clinician_user_mapping:
        _verify_no_unresolved_clinicians(promotion_plan.action_counts)

    known_legacy_ids = {
        str(legacy_id).strip()
        for legacy_id in existing_core_legacy_ids
        if str(legacy_id).strip()
    }
    batch_legacy_ids: set[str] = set()
    existing_conflicts = list(existing_core_appointments)
    created_conflicts: list[ExistingAppointmentConflict] = []

    planned_rows: list[GuardedCoreAppointmentPromotionApplyRow] = []
    action_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    samples_by_reason: dict[str, list[int]] = defaultdict(list)

    for row in promotion_plan.rows:
        legacy_id = str(row.legacy_appointment_id)
        if row.action != R4AppointmentPromotionPlanAction.PROMOTE:
            _append_row(
                planned_rows,
                action_counts,
                reason_counts,
                samples_by_reason,
                legacy_appointment_id=row.legacy_appointment_id,
                action=GuardedCoreAppointmentPromotionApplyRowAction.REFUSE,
                reason=row.reason,
                patient_id=row.patient_id,
                clinician_user_id=row.clinician_user_id,
                status=None,
                sample_limit=sample_limit,
            )
            continue

        if legacy_id in known_legacy_ids:
            _append_row(
                planned_rows,
                action_counts,
                reason_counts,
                samples_by_reason,
                legacy_appointment_id=row.legacy_appointment_id,
                action=GuardedCoreAppointmentPromotionApplyRowAction.SKIP,
                reason="legacy_appointment_already_promoted",
                patient_id=row.patient_id,
                clinician_user_id=row.clinician_user_id,
                status=row.core_status,
                sample_limit=sample_limit,
            )
            continue
        if legacy_id in batch_legacy_ids:
            _append_row(
                planned_rows,
                action_counts,
                reason_counts,
                samples_by_reason,
                legacy_appointment_id=row.legacy_appointment_id,
                action=GuardedCoreAppointmentPromotionApplyRowAction.SKIP,
                reason="duplicate_legacy_appointment_in_batch",
                patient_id=row.patient_id,
                clinician_user_id=row.clinician_user_id,
                status=row.core_status,
                sample_limit=sample_limit,
            )
            continue

        if row.patient_id is None or row.core_status is None:
            raise GuardedCoreAppointmentPromotionApplyError(
                "Promotion plan produced an incomplete promote row."
            )
        starts_at = _map_promote_datetime(
            row.starts_at,
            field_name=f"appointment {row.legacy_appointment_id} starts_at",
        )
        ends_at = _map_promote_datetime(
            row.ends_at,
            field_name=f"appointment {row.legacy_appointment_id} ends_at",
        )

        candidate = AppointmentConflictCandidate(
            starts_at=starts_at,
            ends_at=ends_at,
            clinician_user_id=row.clinician_user_id,
            patient_id=row.patient_id,
        )
        if _candidate_status_needs_conflict_check(row.core_status):
            _ensure_candidate_window(candidate, row.legacy_appointment_id)
            if _conflicts_with_any(candidate, [*existing_conflicts, *created_conflicts]):
                _append_row(
                    planned_rows,
                    action_counts,
                    reason_counts,
                    samples_by_reason,
                    legacy_appointment_id=row.legacy_appointment_id,
                    action=GuardedCoreAppointmentPromotionApplyRowAction.REFUSE,
                    reason="existing_core_appointment_conflict",
                    patient_id=row.patient_id,
                    clinician_user_id=row.clinician_user_id,
                    status=row.core_status,
                    sample_limit=sample_limit,
                )
                continue

        core_candidate = GuardedCoreAppointmentPromotionApplyCandidate(
            legacy_source=legacy_source,
            legacy_id=legacy_id,
            legacy_patient_code=_string_or_none(row.patient_code),
            source_legacy_appointment_id=row.legacy_appointment_id,
            patient_id=row.patient_id,
            clinician_user_id=row.clinician_user_id,
            starts_at=starts_at,
            ends_at=ends_at,
            status=row.core_status,
            appointment_type=row.appointment_type,
            location_type=AppointmentLocationType.clinic,
            location=_clinic_location(row.clinic_code),
            location_text=None,
        )
        _append_row(
            planned_rows,
            action_counts,
            reason_counts,
            samples_by_reason,
            legacy_appointment_id=row.legacy_appointment_id,
            action=GuardedCoreAppointmentPromotionApplyRowAction.CREATE,
            reason="eligible_for_scratch_core_promotion_apply",
            patient_id=row.patient_id,
            clinician_user_id=row.clinician_user_id,
            status=row.core_status,
            candidate=core_candidate,
            sample_limit=sample_limit,
        )
        batch_legacy_ids.add(legacy_id)
        if _candidate_status_needs_conflict_check(row.core_status):
            created_conflicts.append(
                ExistingAppointmentConflict(
                    starts_at=starts_at,
                    ends_at=ends_at,
                    status=row.core_status,
                    clinician_user_id=row.clinician_user_id,
                    patient_id=row.patient_id,
                    deleted=False,
                )
            )

    would_create_count = action_counts[
        GuardedCoreAppointmentPromotionApplyRowAction.CREATE.value
    ]
    skipped_count = action_counts[
        GuardedCoreAppointmentPromotionApplyRowAction.SKIP.value
    ]
    refused_count = action_counts[
        GuardedCoreAppointmentPromotionApplyRowAction.REFUSE.value
    ]
    return GuardedCoreAppointmentPromotionApplyPlan(
        source_database=source_database,
        legacy_source=legacy_source,
        dryrun_report_verified=True,
        confirmation_token=GUARDED_CORE_PROMOTION_CONFIRMATION,
        scratch_only=True,
        total_considered=promotion_plan.total,
        would_create_count=would_create_count,
        would_update_count=0,
        skipped_count=skipped_count,
        refused_count=refused_count,
        core_appointments_before=core_appointments_before,
        expected_core_appointments_after=core_appointments_before + would_create_count,
        action_counts=dict(sorted(action_counts.items())),
        reason_counts=dict(sorted(reason_counts.items())),
        promotion_plan_action_counts=promotion_plan.action_counts,
        promotion_plan_reason_counts=promotion_plan.reason_counts,
        samples_by_reason={
            reason: tuple(ids) for reason, ids in sorted(samples_by_reason.items())
        },
        rows=tuple(planned_rows),
    )


def build_scratch_core_appointment_models_for_guarded_apply(
    plan: GuardedCoreAppointmentPromotionApplyPlan,
    *,
    actor_id: int,
) -> tuple[Appointment, ...]:
    """Materialize Appointment models for an already guarded scratch apply plan.

    The helper only builds in-memory ORM objects. Callers remain responsible for
    adding them to a scratch-only session after repeating the database guard.
    """

    return tuple(
        Appointment(**row.candidate.appointment_kwargs(actor_id=actor_id))
        for row in plan.create_rows
        if row.candidate is not None
    )


def _verify_previous_dryrun_report(
    dryrun_report: Mapping[str, Any],
    *,
    require_clinician_user_mapping: bool,
) -> None:
    if dryrun_report.get("report_only") is not True:
        raise GuardedCoreAppointmentPromotionApplyError(
            "Previous appointment promotion dry-run report must be report-only."
        )
    if dryrun_report.get("core_write_intent") != "none":
        raise GuardedCoreAppointmentPromotionApplyError(
            "Previous appointment promotion dry-run report must have no core write intent."
        )
    core_appointments = dryrun_report.get("core_appointments")
    if not isinstance(core_appointments, Mapping) or (
        core_appointments.get("unchanged") is not True
    ):
        raise GuardedCoreAppointmentPromotionApplyError(
            "Previous appointment promotion dry-run report must prove core appointments unchanged."
        )

    counts = dryrun_report.get("promotion_candidate_counts")
    if not isinstance(counts, Mapping):
        raise GuardedCoreAppointmentPromotionApplyError(
            "Previous appointment promotion dry-run report is missing candidate counts."
        )
    status_candidates = _required_count(counts, "status_policy_promote_candidates")
    patient_linked = _required_count(counts, "patient_linked_promote_candidates")
    if patient_linked != status_candidates:
        raise GuardedCoreAppointmentPromotionApplyError(
            "Previous appointment promotion dry-run report has unmapped promote candidates."
        )
    if require_clinician_user_mapping:
        clinician_resolved = _required_count(
            counts,
            "clinician_resolved_promote_candidates",
        )
        if clinician_resolved != patient_linked:
            raise GuardedCoreAppointmentPromotionApplyError(
                "Previous appointment promotion dry-run report has unresolved clinicians."
            )


def _verify_no_unmapped_promote_candidates(action_counts: Mapping[str, int]) -> None:
    if action_counts.get(R4AppointmentPromotionPlanAction.PATIENT_UNMAPPED.value, 0):
        raise GuardedCoreAppointmentPromotionApplyError(
            "Promotion apply requires zero unmapped promote candidates."
        )


def _verify_no_unresolved_clinicians(action_counts: Mapping[str, int]) -> None:
    if action_counts.get(R4AppointmentPromotionPlanAction.CLINICIAN_UNRESOLVED.value, 0):
        raise GuardedCoreAppointmentPromotionApplyError(
            "Promotion apply requires zero unresolved clinicians when mapping is required."
        )


def _required_count(counts: Mapping[str, Any], key: str) -> int:
    value = counts.get(key)
    if value is None:
        raise GuardedCoreAppointmentPromotionApplyError(
            f"Previous appointment promotion dry-run report is missing {key}."
        )
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise GuardedCoreAppointmentPromotionApplyError(
            f"Previous appointment promotion dry-run report has invalid {key}."
        ) from exc


def _append_row(
    rows: list[GuardedCoreAppointmentPromotionApplyRow],
    action_counts: Counter[str],
    reason_counts: Counter[str],
    samples_by_reason: dict[str, list[int]],
    *,
    legacy_appointment_id: int,
    action: GuardedCoreAppointmentPromotionApplyRowAction,
    reason: str,
    patient_id: int | None,
    clinician_user_id: int | None,
    status: AppointmentStatus | None,
    sample_limit: int,
    candidate: GuardedCoreAppointmentPromotionApplyCandidate | None = None,
) -> None:
    rows.append(
        GuardedCoreAppointmentPromotionApplyRow(
            legacy_appointment_id=legacy_appointment_id,
            action=action,
            reason=reason,
            patient_id=patient_id,
            clinician_user_id=clinician_user_id,
            status=status,
            candidate=candidate,
        )
    )
    action_counts[action.value] += 1
    reason_counts[reason] += 1
    samples = samples_by_reason[reason]
    if len(samples) < sample_limit:
        samples.append(legacy_appointment_id)


def _map_promote_datetime(value: datetime | None, *, field_name: str) -> datetime:
    try:
        return map_r4_appointment_datetime(
            value,
            field_name=field_name,
        ).utc_datetime
    except R4AppointmentDateTimePolicyError as exc:
        raise GuardedCoreAppointmentPromotionApplyError(str(exc)) from exc


def _candidate_status_needs_conflict_check(status: AppointmentStatus) -> bool:
    try:
        return appointment_status_blocks_conflict(status)
    except AppointmentConflictPolicyError as exc:
        raise GuardedCoreAppointmentPromotionApplyError(str(exc)) from exc


def _ensure_candidate_window(
    candidate: AppointmentConflictCandidate,
    legacy_appointment_id: int,
) -> None:
    try:
        appointment_status_blocks_conflict(AppointmentStatus.booked)
        # `appointment_conflicts_with_existing` performs the same window
        # validation, but conflict-free empty DBs still need to fail closed.
        if candidate.ends_at <= candidate.starts_at:
            raise AppointmentConflictPolicyError(
                "candidate ends_at must be after starts_at."
            )
    except AppointmentConflictPolicyError as exc:
        raise GuardedCoreAppointmentPromotionApplyError(
            f"appointment {legacy_appointment_id}: {exc}"
        ) from exc


def _conflicts_with_any(
    candidate: AppointmentConflictCandidate,
    existing_appointments: Iterable[ExistingAppointmentConflict],
) -> bool:
    for existing in existing_appointments:
        try:
            if appointment_conflicts_with_existing(candidate, existing):
                return True
        except AppointmentConflictPolicyError as exc:
            raise GuardedCoreAppointmentPromotionApplyError(str(exc)) from exc
    return False


def _clinic_location(clinic_code: int | str | None) -> str | None:
    value = _string_or_none(clinic_code)
    if value is None:
        return None
    return f"R4 clinic {value}"


def _string_or_none(value: int | str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _row_as_dict(row: GuardedCoreAppointmentPromotionApplyRow) -> dict[str, object]:
    candidate = row.candidate
    if candidate is None:
        return {
            "legacy_appointment_id": row.legacy_appointment_id,
            "action": row.action.value,
            "reason": row.reason,
        }
    return {
        "legacy_appointment_id": row.legacy_appointment_id,
        "legacy_source": candidate.legacy_source,
        "legacy_id": candidate.legacy_id,
        "patient_id": candidate.patient_id,
        "clinician_user_id": candidate.clinician_user_id,
        "starts_at": candidate.starts_at.isoformat(),
        "ends_at": candidate.ends_at.isoformat(),
        "status": candidate.status.value,
        "appointment_type": candidate.appointment_type,
        "location": candidate.location,
    }
