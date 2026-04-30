from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy.engine.url import make_url

from app.services.r4_import.appointment_status_policy import (
    R4AppointmentPromotionDecision,
    map_r4_appointment_status,
)

__all__ = [
    "R4AppointmentPromotionRow",
    "build_appointment_promotion_dryrun_report",
    "ensure_scratch_database_url",
]


@dataclass(frozen=True)
class R4AppointmentPromotionRow:
    legacy_appointment_id: int
    patient_code: int | None
    starts_at: datetime
    ends_at: datetime | None = None
    clinician_code: int | None = None
    status: str | None = None
    cancelled: bool | None = None
    clinic_code: int | None = None
    appointment_type: str | None = None
    appt_flag: int | None = None


def ensure_scratch_database_url(database_url: str) -> str:
    url = make_url(database_url)
    database = (url.database or "").strip()
    database_key = database.lower()
    if database_key == "dental_pms" or not any(
        marker in database_key for marker in ("scratch", "test")
    ):
        raise RuntimeError(
            "Appointment promotion dry-run requires a scratch/test DATABASE_URL; "
            f"refusing database {database!r}."
        )
    return database


def build_appointment_promotion_dryrun_report(
    rows: Iterable[R4AppointmentPromotionRow],
    *,
    cutover_date: date,
    patient_mapping_codes: set[int] | None = None,
    appointment_link_ids: set[int] | None = None,
    r4_user_codes: set[int] | None = None,
    legacy_source: str = "r4",
    source_database: str | None = None,
    core_appointments_before: int = 0,
    core_appointments_after: int | None = None,
    sample_limit: int = 10,
) -> dict[str, Any]:
    if sample_limit < 1:
        raise RuntimeError("sample_limit must be at least 1.")

    patient_mapping_codes = patient_mapping_codes or set()
    appointment_link_ids = appointment_link_ids or set()
    r4_user_codes = r4_user_codes or set()
    core_appointments_after = (
        core_appointments_before
        if core_appointments_after is None
        else core_appointments_after
    )

    now = datetime.now(timezone.utc).replace(microsecond=0)
    cutover_start = datetime.combine(cutover_date, datetime.min.time())
    cutover_end = cutover_start + timedelta(days=1)
    before_7d = cutover_start - timedelta(days=7)
    after_7d = cutover_end + timedelta(days=7)

    total = 0
    min_start: datetime | None = None
    max_start: datetime | None = None
    past_count = 0
    future_count = 0
    cutover_day_count = 0
    seven_days_before_count = 0
    seven_days_after_count = 0
    null_patient_count = 0
    patient_mapped_count = 0
    patient_unmapped_count = 0
    appointment_linked_count = 0
    clinician_missing_count = 0
    clinician_unresolved_count = 0
    clinician_resolved_count = 0

    decision_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    core_status_counts: Counter[str] = Counter()
    category_time_buckets: dict[str, Counter[str]] = defaultdict(Counter)
    status_distribution: Counter[str] = Counter()
    cancelled_distribution: Counter[str] = Counter()
    appt_flag_distribution: Counter[str] = Counter()
    clinician_distribution: Counter[str] = Counter()
    clinic_distribution: Counter[str] = Counter()

    status_policy_promote_candidates = 0
    patient_linked_promote_candidates = 0
    clinician_resolved_promote_candidates = 0
    clinician_unresolved_on_patient_linked_candidates = 0
    blocked_by_null_patient = 0
    blocked_by_unmapped_patient = 0

    samples: dict[str, list[dict[str, Any]]] = {
        "null_patient": [],
        "unmapped_patient": [],
        "clinician_unresolved": [],
        "manual_review": [],
        "excluded": [],
        "future_promote_candidate": [],
        "cutover_boundary": [],
    }

    for row in rows:
        total += 1
        starts_at = _naive_utc(row.starts_at)
        if min_start is None or starts_at < min_start:
            min_start = starts_at
        if max_start is None or starts_at > max_start:
            max_start = starts_at

        time_bucket = "future" if starts_at >= cutover_start else "past"
        if time_bucket == "future":
            future_count += 1
        else:
            past_count += 1
        if cutover_start <= starts_at < cutover_end:
            cutover_day_count += 1
        if before_7d <= starts_at < cutover_start:
            seven_days_before_count += 1
            _append_sample(samples, "cutover_boundary", row, sample_limit)
        if cutover_end <= starts_at < after_7d:
            seven_days_after_count += 1
            _append_sample(samples, "cutover_boundary", row, sample_limit)

        patient_code_present = row.patient_code is not None
        appointment_linked = row.legacy_appointment_id in appointment_link_ids
        patient_mapped = (
            row.patient_code in patient_mapping_codes
            if row.patient_code is not None
            else False
        )
        patient_resolved = patient_mapped or appointment_linked
        if not patient_code_present:
            null_patient_count += 1
            _append_sample(samples, "null_patient", row, sample_limit)
        elif patient_resolved:
            patient_mapped_count += 1
        else:
            patient_unmapped_count += 1
            _append_sample(samples, "unmapped_patient", row, sample_limit)
        if appointment_linked:
            appointment_linked_count += 1

        clinician_missing = row.clinician_code is None
        clinician_resolved = (
            row.clinician_code in r4_user_codes if row.clinician_code is not None else False
        )
        clinician_unresolved = not clinician_missing and not clinician_resolved
        if clinician_missing:
            clinician_missing_count += 1
        elif clinician_resolved:
            clinician_resolved_count += 1
        else:
            clinician_unresolved_count += 1
            _append_sample(samples, "clinician_unresolved", row, sample_limit)

        mapping = map_r4_appointment_status(
            status=row.status,
            cancelled=row.cancelled,
            appt_flag=row.appt_flag,
            patient_code=row.patient_code,
            clinician_code=row.clinician_code,
            clinic_code=row.clinic_code,
            allow_live_in_progress=False,
        )
        decision_counts[mapping.decision.value] += 1
        category_counts[mapping.category.value] += 1
        category_time_buckets[mapping.category.value][time_bucket] += 1
        if mapping.core_status is not None:
            core_status_counts[mapping.core_status.value] += 1
        if row.status:
            status_distribution[row.status] += 1
        cancelled_distribution[str(bool(row.cancelled)).lower()] += 1
        if row.appt_flag is not None:
            appt_flag_distribution[str(row.appt_flag)] += 1
        if row.clinician_code is not None:
            clinician_distribution[str(row.clinician_code)] += 1
        if row.clinic_code is not None:
            clinic_distribution[str(row.clinic_code)] += 1

        if mapping.decision == R4AppointmentPromotionDecision.MANUAL_REVIEW:
            _append_sample(samples, "manual_review", row, sample_limit)
        elif mapping.decision == R4AppointmentPromotionDecision.EXCLUDE:
            _append_sample(samples, "excluded", row, sample_limit)

        if mapping.can_promote:
            status_policy_promote_candidates += 1
            if patient_resolved:
                patient_linked_promote_candidates += 1
                if clinician_unresolved:
                    clinician_unresolved_on_patient_linked_candidates += 1
                else:
                    clinician_resolved_promote_candidates += 1
                if time_bucket == "future":
                    _append_sample(samples, "future_promote_candidate", row, sample_limit)
            elif not patient_code_present:
                blocked_by_null_patient += 1
            else:
                blocked_by_unmapped_patient += 1

    core_unchanged = core_appointments_before == core_appointments_after
    return {
        "generated_at": now.isoformat(),
        "legacy_source": legacy_source,
        "source_database": source_database,
        "report_only": True,
        "core_write_intent": "none",
        "cutover_date": cutover_date.isoformat(),
        "total_considered": total,
        "date_range": {
            "min_start": _format_dt(min_start),
            "max_start": _format_dt(max_start),
        },
        "time_window_counts": {
            "past": past_count,
            "future": future_count,
            "cutover_day": cutover_day_count,
            "seven_days_before": seven_days_before_count,
            "seven_days_after": seven_days_after_count,
        },
        "policy_counts": {
            "decision": dict(sorted(decision_counts.items())),
            "category": dict(sorted(category_counts.items())),
            "core_status": dict(sorted(core_status_counts.items())),
            "category_time_buckets": {
                key: dict(sorted(counter.items()))
                for key, counter in sorted(category_time_buckets.items())
            },
        },
        "promotion_candidate_counts": {
            "status_policy_promote_candidates": status_policy_promote_candidates,
            "patient_linked_promote_candidates": patient_linked_promote_candidates,
            "clinician_resolved_promote_candidates": (
                clinician_resolved_promote_candidates
            ),
            "clinician_unresolved_on_patient_linked_candidates": (
                clinician_unresolved_on_patient_linked_candidates
            ),
            "blocked_by_null_patient": blocked_by_null_patient,
            "blocked_by_unmapped_patient": blocked_by_unmapped_patient,
        },
        "linkage_counts": {
            "null_patient_code": null_patient_count,
            "patient_mapped_or_manually_linked": patient_mapped_count,
            "patient_unmapped": patient_unmapped_count,
            "manual_appointment_links": appointment_linked_count,
        },
        "clinician_counts": {
            "distinct_clinician_codes": len(clinician_distribution),
            "clinician_missing": clinician_missing_count,
            "clinician_resolved_by_r4_users": clinician_resolved_count,
            "clinician_unresolved": clinician_unresolved_count,
        },
        "clinic_distribution": _top_counts(clinic_distribution),
        "source_distributions": {
            "status": _top_counts(status_distribution),
            "cancelled": _top_counts(cancelled_distribution),
            "appt_flag": _top_counts(appt_flag_distribution),
            "clinician_code": _top_counts(clinician_distribution),
        },
        "core_appointments": {
            "before": core_appointments_before,
            "after": core_appointments_after,
            "unchanged": core_unchanged,
        },
        "samples": samples,
        "risk_flags": _risk_flags(
            patient_unmapped_count=patient_unmapped_count,
            null_patient_count=null_patient_count,
            clinician_unresolved_count=clinician_unresolved_count,
            core_unchanged=core_unchanged,
            manual_review_count=decision_counts[
                R4AppointmentPromotionDecision.MANUAL_REVIEW.value
            ],
        ),
    }


def _risk_flags(
    *,
    patient_unmapped_count: int,
    null_patient_count: int,
    clinician_unresolved_count: int,
    core_unchanged: bool,
    manual_review_count: int,
) -> list[str]:
    risks: list[str] = []
    if null_patient_count:
        risks.append("null_patient_rows_remain_read_only")
    if patient_unmapped_count:
        risks.append("patient_code_rows_missing_mapping")
    if clinician_unresolved_count:
        risks.append("clinician_codes_need_mapping_before_core_promotion")
    if manual_review_count:
        risks.append("manual_review_status_policy_rows_present")
    if not core_unchanged:
        risks.append("core_appointment_count_changed")
    return risks


def _append_sample(
    samples: dict[str, list[dict[str, Any]]],
    key: str,
    row: R4AppointmentPromotionRow,
    sample_limit: int,
) -> None:
    bucket = samples[key]
    if len(bucket) < sample_limit:
        bucket.append(_row_sample(row))


def _row_sample(row: R4AppointmentPromotionRow) -> dict[str, Any]:
    return {
        "legacy_appointment_id": row.legacy_appointment_id,
        "patient_code": row.patient_code,
        "starts_at": _format_dt(row.starts_at),
        "ends_at": _format_dt(row.ends_at),
        "clinician_code": row.clinician_code,
        "status": row.status,
        "cancelled": row.cancelled,
        "clinic_code": row.clinic_code,
        "appointment_type": row.appointment_type,
        "appt_flag": row.appt_flag,
    }


def _format_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _top_counts(counter: Counter[str], *, limit: int = 20) -> list[dict[str, Any]]:
    return [
        {"value": value, "count": count}
        for value, count in counter.most_common(limit)
    ]
