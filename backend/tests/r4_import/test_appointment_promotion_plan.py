from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from app.models.appointment import AppointmentStatus
from app.services.r4_import.appointment_promotion_plan import (
    R4AppointmentPromotionPlanAction,
    R4AppointmentPromotionPlanInput,
    build_appointment_promotion_plan,
)


def _row(
    appointment_id: int,
    *,
    patient_code: int | str | None = 1001,
    status: str | None = "Pending",
    appt_flag: int | str | None = 6,
    cancelled: bool | int | str | None = False,
    clinician_code: int | str | None = 47,
) -> R4AppointmentPromotionPlanInput:
    return R4AppointmentPromotionPlanInput(
        legacy_appointment_id=appointment_id,
        patient_code=patient_code,
        starts_at=datetime(2026, 4, 29, 9, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 4, 29, 9, 30, tzinfo=timezone.utc),
        clinician_code=clinician_code,
        status=status,
        cancelled=cancelled,
        clinic_code=1,
        appointment_type="R4 appointment",
        appt_flag=appt_flag,
    )


def test_plan_promotes_eligible_rows_without_inferring_clinician_user_ids():
    plan = build_appointment_promotion_plan(
        [
            _row(1, status="Complete", appt_flag=1),
            _row(2, status="Cancelled", appt_flag=2),
            _row(3, status="Did Not Attend", appt_flag=3),
            _row(4, status="Pending", appt_flag=6),
        ],
        patient_mapping={1001: 501},
    )

    assert plan.total == 4
    assert plan.action_counts == {"promote": 4}
    assert plan.core_status_counts == {
        "booked": 1,
        "cancelled": 1,
        "completed": 1,
        "no_show": 1,
    }
    assert plan.reason_counts == {"eligible_for_guarded_promotion": 4}
    assert [row.patient_id for row in plan.promote_rows] == [501, 501, 501, 501]
    assert [row.clinician_user_id for row in plan.promote_rows] == [
        None,
        None,
        None,
        None,
    ]


def test_plan_uses_explicit_clinician_mapping_when_supplied():
    plan = build_appointment_promotion_plan(
        [_row(1)],
        patient_mapping={1001: 501},
        clinician_user_mapping={47: 12},
    )

    row = plan.rows[0]
    assert row.action == R4AppointmentPromotionPlanAction.PROMOTE
    assert row.patient_id == 501
    assert row.clinician_user_id == 12
    assert row.core_status == AppointmentStatus.booked


def test_plan_blocks_when_clinician_mapping_is_required_but_missing():
    plan = build_appointment_promotion_plan(
        [_row(1)],
        patient_mapping={1001: 501},
        require_clinician_user_mapping=True,
    )

    row = plan.rows[0]
    assert row.action == R4AppointmentPromotionPlanAction.CLINICIAN_UNRESOLVED
    assert row.reason == "clinician_user_mapping_required"
    assert row.patient_id == 501
    assert row.clinician_user_id is None
    assert row.core_status is None


def test_plan_keeps_null_or_blank_patient_code_read_only():
    plan = build_appointment_promotion_plan(
        [
            _row(1, patient_code=None),
            _row(2, patient_code=" "),
        ],
        patient_mapping={1001: 501},
    )

    assert plan.action_counts == {"null_patient_read_only": 2}
    assert plan.reason_counts == {"null_or_blank_patient_code": 2}
    assert all(row.core_status is None for row in plan.rows)


def test_plan_blocks_missing_patient_mapping_without_core_status():
    plan = build_appointment_promotion_plan(
        [_row(1, patient_code=2002)],
        patient_mapping={1001: 501},
    )

    row = plan.rows[0]
    assert row.action == R4AppointmentPromotionPlanAction.PATIENT_UNMAPPED
    assert row.reason == "patient_mapping_missing"
    assert row.patient_id is None
    assert row.core_status is None


def test_plan_allows_manual_appointment_link_to_resolve_patient():
    plan = build_appointment_promotion_plan(
        [_row(1, patient_code=2002)],
        patient_mapping={1001: 501},
        appointment_patient_links={1: 777},
    )

    row = plan.rows[0]
    assert row.action == R4AppointmentPromotionPlanAction.PROMOTE
    assert row.patient_id == 777
    assert row.reason == "eligible_for_guarded_promotion"


def test_plan_excludes_deleted_rows():
    plan = build_appointment_promotion_plan(
        [_row(1, status="Deleted", appt_flag=5)],
        patient_mapping={1001: 501},
    )

    row = plan.rows[0]
    assert row.action == R4AppointmentPromotionPlanAction.EXCLUDE
    assert row.reason == "deleted_rows_excluded_from_core_promotion"
    assert row.core_status is None


def test_plan_keeps_manual_review_statuses_out_of_promotion():
    plan = build_appointment_promotion_plan(
        [
            _row(1, status="Left Surgery", appt_flag=11),
            _row(2, status="Waiting", appt_flag=7),
            _row(3, status="In Surgery", appt_flag=8),
        ],
        patient_mapping={1001: 501},
    )

    assert plan.action_counts == {"manual_review": 3}
    assert plan.reason_counts == {
        "in_surgery_requires_live_context": 1,
        "left_surgery_requires_confirmation": 1,
        "waiting_requires_operator_policy": 1,
    }
    assert all(row.core_status is None for row in plan.rows)


def test_plan_fails_closed_for_unknown_status_or_flag():
    plan = build_appointment_promotion_plan(
        [
            _row(1, status="Strange", appt_flag=6),
            _row(2, status="Pending", appt_flag=99),
        ],
        patient_mapping={1001: 501},
    )

    assert plan.action_counts == {"manual_review": 2}
    assert plan.reason_counts == {
        "unknown_appt_flag": 1,
        "unknown_status": 1,
    }
    assert all(row.core_status is None for row in plan.rows)


def test_plan_fails_closed_for_conflicting_status_flag_combination():
    plan = build_appointment_promotion_plan(
        [_row(1, status="Pending", appt_flag=1)],
        patient_mapping={1001: 501},
    )

    row = plan.rows[0]
    assert row.action == R4AppointmentPromotionPlanAction.MANUAL_REVIEW
    assert row.reason == "status_appt_flag_conflict"
    assert row.core_status is None


def test_plan_aggregates_counts_and_reason_samples():
    plan = build_appointment_promotion_plan(
        [
            _row(1, status="Complete", appt_flag=1),
            _row(2, patient_code=None),
            _row(3, patient_code=2002),
            _row(4, status="Deleted", appt_flag=5),
            _row(5, status="Waiting", appt_flag=7),
        ],
        patient_mapping={1001: 501},
        sample_limit=1,
    )

    assert plan.action_counts == {
        "exclude": 1,
        "manual_review": 1,
        "null_patient_read_only": 1,
        "patient_unmapped": 1,
        "promote": 1,
    }
    assert plan.reason_counts == {
        "deleted_rows_excluded_from_core_promotion": 1,
        "eligible_for_guarded_promotion": 1,
        "null_or_blank_patient_code": 1,
        "patient_mapping_missing": 1,
        "waiting_requires_operator_policy": 1,
    }
    assert Counter(plan.policy_category_counts) == Counter(
        {
            "completed_candidate": 1,
            "deleted_excluded": 1,
            "null_patient_read_only": 1,
            "waiting_manual_review": 1,
            "booked_candidate": 1,
        }
    )
    assert plan.samples_by_reason == {
        "deleted_rows_excluded_from_core_promotion": (4,),
        "eligible_for_guarded_promotion": (1,),
        "null_or_blank_patient_code": (2,),
        "patient_mapping_missing": (3,),
        "waiting_requires_operator_policy": (5,),
    }
