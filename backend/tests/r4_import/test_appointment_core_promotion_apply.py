from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app.models.appointment import AppointmentLocationType, AppointmentStatus
from app.services.appointment_conflicts import ExistingAppointmentConflict
from app.services.r4_import.appointment_core_promotion_apply import (
    GUARDED_CORE_PROMOTION_CONFIRMATION,
    GuardedCoreAppointmentPromotionApplyError,
    GuardedCoreAppointmentPromotionApplyRowAction,
    build_guarded_core_appointment_promotion_apply_plan,
    build_scratch_core_appointment_models_for_guarded_apply,
)
from app.services.r4_import.appointment_promotion_plan import (
    R4AppointmentPromotionPlanInput,
)


SCRATCH_DATABASE_URL = (
    "postgresql+psycopg://dental_pms:secret@db:5432/"
    "dental_pms_core_promotion_scratch"
)


def _row(
    appointment_id: int,
    *,
    patient_code: int | str | None = 1001,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    status: str | None = "Pending",
    appt_flag: int | str | None = 6,
    cancelled: bool | int | str | None = False,
    clinician_code: int | str | None = 47,
) -> R4AppointmentPromotionPlanInput:
    return R4AppointmentPromotionPlanInput(
        legacy_appointment_id=appointment_id,
        patient_code=patient_code,
        starts_at=starts_at or datetime(2026, 1, 15, 9, 0),
        ends_at=ends_at or datetime(2026, 1, 15, 9, 30),
        clinician_code=clinician_code,
        status=status,
        cancelled=cancelled,
        clinic_code=1,
        appointment_type="R4 appointment",
        appt_flag=appt_flag,
    )


def _dryrun_report(
    *,
    status_candidates: int = 1,
    patient_linked: int | None = None,
    clinician_resolved: int | None = None,
    unchanged: bool = True,
) -> dict[str, object]:
    patient_linked = status_candidates if patient_linked is None else patient_linked
    clinician_resolved = (
        patient_linked if clinician_resolved is None else clinician_resolved
    )
    return {
        "report_only": True,
        "core_write_intent": "none",
        "core_appointments": {"before": 0, "after": 0, "unchanged": unchanged},
        "promotion_candidate_counts": {
            "status_policy_promote_candidates": status_candidates,
            "patient_linked_promote_candidates": patient_linked,
            "clinician_resolved_promote_candidates": clinician_resolved,
        },
    }


def _build_plan(
    rows,
    *,
    dryrun_report: dict[str, object] | None = None,
    database_url: str = SCRATCH_DATABASE_URL,
    confirm: str = GUARDED_CORE_PROMOTION_CONFIRMATION,
    patient_mapping: dict[int | str, int] | None = None,
    clinician_user_mapping: dict[int | str, int] | None = None,
    require_clinician_user_mapping: bool = False,
    existing_core_appointments=(),
    existing_core_legacy_ids=(),
):
    return build_guarded_core_appointment_promotion_apply_plan(
        rows,
        database_url=database_url,
        confirm=confirm,
        dryrun_report=dryrun_report or _dryrun_report(status_candidates=len(rows)),
        patient_mapping=patient_mapping or {1001: 501},
        clinician_user_mapping=clinician_user_mapping,
        require_clinician_user_mapping=require_clinician_user_mapping,
        existing_core_appointments=existing_core_appointments,
        existing_core_legacy_ids=existing_core_legacy_ids,
        core_appointments_before=10,
    )


def test_guarded_apply_plan_creates_only_eligible_scratch_candidates():
    plan = _build_plan(
        [
            _row(1, status="Complete", appt_flag=1),
            _row(2, status="Cancelled", appt_flag=2, cancelled=True),
            _row(
                3,
                starts_at=datetime(2026, 1, 15, 10, 0),
                ends_at=datetime(2026, 1, 15, 10, 30),
                status="Pending",
                appt_flag=6,
            ),
            _row(4, status="Deleted", appt_flag=5),
            _row(5, patient_code=None),
            _row(6, status="Waiting", appt_flag=7),
        ],
        dryrun_report=_dryrun_report(status_candidates=3),
        clinician_user_mapping={47: 7},
    )

    assert plan.source_database == "dental_pms_core_promotion_scratch"
    assert plan.scratch_only is True
    assert plan.dryrun_report_verified is True
    assert plan.total_considered == 6
    assert plan.action_counts == {"create": 3, "refuse": 3}
    assert plan.reason_counts == {
        "deleted_rows_excluded_from_core_promotion": 1,
        "eligible_for_scratch_core_promotion_apply": 3,
        "null_or_blank_patient_code": 1,
        "waiting_requires_operator_policy": 1,
    }
    assert plan.would_create_count == 3
    assert plan.would_update_count == 0
    assert plan.expected_core_appointments_after == 13
    assert [row.legacy_appointment_id for row in plan.create_rows] == [1, 2, 3]

    created = plan.create_rows[0].candidate
    assert created is not None
    assert created.legacy_source == "r4"
    assert created.legacy_id == "1"
    assert created.legacy_patient_code == "1001"
    assert created.patient_id == 501
    assert created.clinician_user_id == 7
    assert created.starts_at == datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)
    assert created.ends_at == datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc)
    assert created.status == AppointmentStatus.completed
    assert created.location_type == AppointmentLocationType.clinic
    assert created.location == "R4 clinic 1"
    assert created.appointment_kwargs(actor_id=42)["created_by_user_id"] == 42
    models = build_scratch_core_appointment_models_for_guarded_apply(
        plan,
        actor_id=42,
    )
    assert len(models) == 3
    assert models[0].legacy_source == "r4"
    assert models[0].legacy_id == "1"
    assert models[0].patient_id == 501
    assert models[0].created_by_user_id == 42
    json.dumps(plan.as_dict())


def test_guarded_apply_refuses_default_database_url():
    with pytest.raises(
        RuntimeError,
        match="requires a scratch/test DATABASE_URL",
    ):
        _build_plan(
            [_row(1)],
            database_url="postgresql+psycopg://dental_pms:secret@db:5432/dental_pms",
        )


def test_guarded_apply_requires_confirmation_token():
    with pytest.raises(
        GuardedCoreAppointmentPromotionApplyError,
        match="SCRATCH_APPLY",
    ):
        _build_plan([_row(1)], confirm="APPLY")


def test_guarded_apply_requires_previous_no_core_write_dryrun_report():
    report = _dryrun_report()
    report["core_appointments"] = {"before": 0, "after": 1, "unchanged": False}

    with pytest.raises(
        GuardedCoreAppointmentPromotionApplyError,
        match="core appointments unchanged",
    ):
        _build_plan([_row(1)], dryrun_report=report)


def test_guarded_apply_requires_zero_unmapped_promote_candidates_in_dryrun():
    with pytest.raises(
        GuardedCoreAppointmentPromotionApplyError,
        match="unmapped promote candidates",
    ):
        _build_plan(
            [_row(1)],
            dryrun_report=_dryrun_report(status_candidates=1, patient_linked=0),
        )


def test_guarded_apply_fails_closed_when_current_plan_has_unmapped_patient():
    with pytest.raises(
        GuardedCoreAppointmentPromotionApplyError,
        match="zero unmapped promote candidates",
    ):
        _build_plan(
            [_row(1, patient_code=2002)],
            dryrun_report=_dryrun_report(status_candidates=1),
        )


def test_guarded_apply_requires_resolved_clinicians_when_mapping_is_required():
    with pytest.raises(
        GuardedCoreAppointmentPromotionApplyError,
        match="unresolved clinicians",
    ):
        _build_plan(
            [_row(1)],
            dryrun_report=_dryrun_report(
                status_candidates=1,
                patient_linked=1,
                clinician_resolved=0,
            ),
            require_clinician_user_mapping=True,
        )


def test_guarded_apply_fails_closed_for_nonexistent_local_datetime():
    with pytest.raises(
        GuardedCoreAppointmentPromotionApplyError,
        match="not a valid Europe/London local time",
    ):
        _build_plan(
            [
                _row(
                    1,
                    starts_at=datetime(2026, 3, 29, 1, 30),
                    ends_at=datetime(2026, 3, 29, 2, 30),
                )
            ],
        )


def test_guarded_apply_refuses_conflicting_core_appointment_candidates():
    plan = _build_plan(
        [_row(1)],
        clinician_user_mapping={47: 7},
        existing_core_appointments=[
            ExistingAppointmentConflict(
                starts_at=datetime(2026, 1, 15, 9, 15, tzinfo=timezone.utc),
                ends_at=datetime(2026, 1, 15, 9, 45, tzinfo=timezone.utc),
                status=AppointmentStatus.booked,
                clinician_user_id=7,
                patient_id=999,
            )
        ],
    )

    assert plan.action_counts == {"refuse": 1}
    assert plan.would_create_count == 0
    assert plan.refused_count == 1
    assert plan.rows[0].action == GuardedCoreAppointmentPromotionApplyRowAction.REFUSE
    assert plan.rows[0].reason == "existing_core_appointment_conflict"
    assert plan.expected_core_appointments_after == 10


def test_guarded_apply_skips_existing_legacy_ids_for_idempotency():
    plan = _build_plan(
        [
            _row(1),
            _row(2),
        ],
        dryrun_report=_dryrun_report(status_candidates=2),
        existing_core_legacy_ids={"1"},
    )

    assert plan.action_counts == {"create": 1, "skip": 1}
    assert plan.reason_counts == {
        "eligible_for_scratch_core_promotion_apply": 1,
        "legacy_appointment_already_promoted": 1,
    }
    assert plan.skipped_count == 1
    assert plan.would_create_count == 1
    assert [row.legacy_appointment_id for row in plan.create_rows] == [2]


def test_guarded_apply_does_not_conflict_check_cancelled_or_no_show_candidates():
    plan = _build_plan(
        [_row(1, status="Cancelled", appt_flag=2, cancelled=True)],
        clinician_user_mapping={47: 7},
        existing_core_appointments=[
            ExistingAppointmentConflict(
                starts_at=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
                ends_at=datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc),
                status=AppointmentStatus.booked,
                clinician_user_id=7,
                patient_id=999,
            )
        ],
    )

    assert plan.action_counts == {"create": 1}
    assert plan.create_rows[0].candidate is not None
    assert plan.create_rows[0].candidate.status == AppointmentStatus.cancelled
