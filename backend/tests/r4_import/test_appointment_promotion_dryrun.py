from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest

from app.services.r4_import.appointment_promotion_dryrun import (
    R4AppointmentPromotionRow,
    build_appointment_promotion_dryrun_report,
    ensure_scratch_database_url,
)


def _row(
    appointment_id: int,
    *,
    patient_code: int | None,
    starts_at: datetime,
    status: str,
    appt_flag: int,
    clinician_code: int | None = 47,
    cancelled: bool | None = False,
) -> R4AppointmentPromotionRow:
    return R4AppointmentPromotionRow(
        legacy_appointment_id=appointment_id,
        patient_code=patient_code,
        starts_at=starts_at,
        clinician_code=clinician_code,
        status=status,
        cancelled=cancelled,
        clinic_code=1,
        appointment_type="R4 appointment",
        appt_flag=appt_flag,
    )


def test_promotion_dryrun_report_classifies_without_core_writes():
    rows = [
        _row(
            1,
            patient_code=1001,
            starts_at=datetime(2026, 4, 28, 9, 0, tzinfo=timezone.utc),
            status="Complete",
            appt_flag=1,
        ),
        _row(
            2,
            patient_code=1001,
            starts_at=datetime(2026, 4, 29, 9, 0, tzinfo=timezone.utc),
            status="Pending",
            appt_flag=6,
        ),
        _row(
            3,
            patient_code=1001,
            starts_at=datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
            status="Cancelled",
            appt_flag=2,
            clinician_code=99,
            cancelled=True,
        ),
        _row(
            4,
            patient_code=1001,
            starts_at=datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc),
            status="Deleted",
            appt_flag=5,
        ),
        _row(
            5,
            patient_code=2002,
            starts_at=datetime(2025, 1, 2, 9, 0, tzinfo=timezone.utc),
            status="Did Not Attend",
            appt_flag=3,
        ),
        _row(
            6,
            patient_code=None,
            starts_at=datetime(2025, 1, 3, 9, 0, tzinfo=timezone.utc),
            status="Pending",
            appt_flag=6,
        ),
        _row(
            7,
            patient_code=1001,
            starts_at=datetime(2025, 1, 4, 9, 0, tzinfo=timezone.utc),
            status="Left Surgery",
            appt_flag=11,
        ),
        _row(
            8,
            patient_code=1001,
            starts_at=datetime(2025, 1, 5, 9, 0, tzinfo=timezone.utc),
            status="Waiting",
            appt_flag=7,
        ),
        _row(
            9,
            patient_code=3003,
            starts_at=datetime(2025, 1, 6, 9, 0, tzinfo=timezone.utc),
            status="Pending",
            appt_flag=6,
            clinician_code=None,
        ),
    ]

    report = build_appointment_promotion_dryrun_report(
        rows,
        cutover_date=date(2026, 4, 29),
        patient_mapping_codes={1001},
        appointment_link_ids={9},
        r4_user_codes={47},
        source_database="dental_pms_appointments_scratch",
        core_appointments_before=0,
        core_appointments_after=0,
        sample_limit=2,
    )

    assert report["report_only"] is True
    assert report["core_write_intent"] == "none"
    assert report["total_considered"] == 9
    assert report["time_window_counts"] == {
        "past": 7,
        "future": 2,
        "cutover_day": 1,
        "seven_days_before": 1,
        "seven_days_after": 1,
    }
    assert report["policy_counts"]["decision"] == {
        "exclude": 1,
        "manual_review": 2,
        "promote_candidate": 5,
        "read_only_only": 1,
    }
    assert report["promotion_candidate_counts"] == {
        "status_policy_promote_candidates": 5,
        "patient_linked_promote_candidates": 4,
        "clinician_resolved_promote_candidates": 3,
        "clinician_unresolved_on_patient_linked_candidates": 1,
        "blocked_by_null_patient": 0,
        "blocked_by_unmapped_patient": 1,
    }
    assert report["linkage_counts"] == {
        "null_patient_code": 1,
        "patient_mapped_or_manually_linked": 7,
        "patient_unmapped": 1,
        "manual_appointment_links": 1,
    }
    assert report["clinician_counts"] == {
        "distinct_clinician_codes": 2,
        "clinician_missing": 1,
        "clinician_resolved_by_r4_users": 7,
        "clinician_unresolved": 1,
    }
    assert report["core_appointments"] == {"before": 0, "after": 0, "unchanged": True}
    assert "clinician_codes_need_mapping_before_core_promotion" in report["risk_flags"]
    assert report["samples"]["null_patient"][0]["legacy_appointment_id"] == 6
    assert report["samples"]["unmapped_patient"][0]["legacy_appointment_id"] == 5
    assert report["samples"]["clinician_unresolved"][0]["legacy_appointment_id"] == 3
    json.dumps(report)


def test_promotion_dryrun_refuses_default_database_url():
    with pytest.raises(RuntimeError, match="requires a scratch/test DATABASE_URL"):
        ensure_scratch_database_url(
            "postgresql+psycopg://dental_pms:secret@localhost:5432/dental_pms"
        )


def test_promotion_dryrun_accepts_scratch_database_url():
    database = ensure_scratch_database_url(
        "postgresql+psycopg://dental_pms:secret@db:5432/dental_pms_appointments_scratch"
    )

    assert database == "dental_pms_appointments_scratch"
