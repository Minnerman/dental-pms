from __future__ import annotations

import json
import sys
from datetime import datetime

import pytest

from app.scripts import r4_appointment_core_promotion_apply as apply_script
from app.services.r4_import.appointment_core_promotion_apply import (
    GUARDED_CORE_PROMOTION_CONFIRMATION,
    build_guarded_core_appointment_promotion_apply_plan,
)
from app.services.r4_import.appointment_promotion_plan import (
    R4AppointmentPromotionPlanInput,
)


SCRATCH_DATABASE_URL = (
    "postgresql+psycopg://dental_pms:secret@db:5432/"
    "dental_pms_core_promotion_scratch"
)


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.flushed = False
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def add_all(self, rows) -> None:
        self.added.extend(rows)

    def flush(self) -> None:
        self.flushed = True

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def _row(appointment_id: int = 1) -> R4AppointmentPromotionPlanInput:
    return R4AppointmentPromotionPlanInput(
        legacy_appointment_id=appointment_id,
        patient_code=1001,
        starts_at=datetime(2026, 1, 15, 9, 0),
        ends_at=datetime(2026, 1, 15, 9, 30),
        clinician_code=47,
        status="Pending",
        cancelled=False,
        clinic_code=1,
        appointment_type="R4 appointment",
        appt_flag=6,
    )


def _dryrun_report(
    *,
    source_database: str = "dental_pms_core_promotion_scratch",
    status_candidates: int = 1,
) -> dict[str, object]:
    return {
        "source_database": source_database,
        "report_only": True,
        "core_write_intent": "none",
        "core_appointments": {"before": 0, "after": 0, "unchanged": True},
        "promotion_candidate_counts": {
            "status_policy_promote_candidates": status_candidates,
            "patient_linked_promote_candidates": status_candidates,
            "clinician_resolved_promote_candidates": status_candidates,
        },
    }


def test_cli_parser_refuses_without_scratch_apply_confirmation(monkeypatch, tmp_path):
    output = tmp_path / "apply.json"
    dryrun = tmp_path / "dryrun.json"
    dryrun.write_text(json.dumps(_dryrun_report()), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "r4_appointment_core_promotion_apply.py",
            "--dryrun-report-json",
            str(dryrun),
            "--output-json",
            str(output),
            "--confirm",
            "APPLY",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        apply_script.main()

    assert exc.value.code == 2
    assert not output.exists()


def test_load_dryrun_report_requires_matching_scratch_database(tmp_path):
    dryrun = tmp_path / "dryrun.json"
    dryrun.write_text(
        json.dumps(_dryrun_report(source_database="other_scratch")),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="source_database does not match"):
        apply_script._load_dryrun_report(
            str(dryrun),
            source_database="dental_pms_core_promotion_scratch",
        )


def test_load_json_mapping_requires_integer_user_ids(tmp_path):
    mapping = tmp_path / "clinicians.json"
    mapping.write_text(json.dumps({"47": "not-an-int"}), encoding="utf-8")

    with pytest.raises(RuntimeError, match="integer PMS user IDs"):
        apply_script._load_json_mapping(str(mapping))


def test_apply_plan_to_session_materializes_only_create_rows():
    plan = build_guarded_core_appointment_promotion_apply_plan(
        [_row(1), _row(2)],
        database_url=SCRATCH_DATABASE_URL,
        confirm=GUARDED_CORE_PROMOTION_CONFIRMATION,
        dryrun_report=_dryrun_report(status_candidates=2),
        patient_mapping={1001: 501},
        existing_core_legacy_ids={"2"},
        core_appointments_before=10,
    )
    session = FakeSession()

    result = apply_script._apply_plan_to_session(session, plan, actor_id=42)

    assert result == {"created": 1, "updated": 0, "skipped": 1, "refused": 0}
    assert session.flushed is True
    assert len(session.added) == 1
    assert session.added[0].legacy_id == "1"
    assert session.added[0].created_by_user_id == 42


def test_run_apply_refuses_default_database_before_opening_session(monkeypatch, tmp_path):
    dryrun = tmp_path / "dryrun.json"
    output = tmp_path / "apply.json"
    dryrun.write_text(json.dumps(_dryrun_report()), encoding="utf-8")
    opened = False

    def open_session():  # pragma: no cover - should never run
        nonlocal opened
        opened = True
        return FakeSession()

    monkeypatch.setattr(
        apply_script.settings,
        "database_url",
        "postgresql+psycopg://dental_pms:secret@db:5432/dental_pms",
    )
    monkeypatch.setattr(apply_script, "SessionLocal", open_session)

    with pytest.raises(RuntimeError, match="requires a scratch/test DATABASE_URL"):
        apply_script.run_apply(
            dryrun_report_json=str(dryrun),
            output_json=str(output),
            confirm=GUARDED_CORE_PROMOTION_CONFIRMATION,
        )

    assert opened is False
    assert not output.exists()


def test_run_apply_writes_json_and_commits_scratch_only(monkeypatch, tmp_path):
    dryrun = tmp_path / "dryrun.json"
    output = tmp_path / "apply.json"
    dryrun.write_text(json.dumps(_dryrun_report()), encoding="utf-8")
    session = FakeSession()
    counts = iter([10, 11])

    monkeypatch.setattr(apply_script.settings, "database_url", SCRATCH_DATABASE_URL)
    monkeypatch.setattr(apply_script, "SessionLocal", lambda: session)
    monkeypatch.setattr(apply_script, "_resolve_actor_id", lambda _session, _actor: 42)
    monkeypatch.setattr(
        apply_script,
        "_count_core_appointments",
        lambda _session: next(counts),
    )
    monkeypatch.setattr(
        apply_script,
        "_load_r4_appointments",
        lambda *_args, **_kwargs: (_row(),),
    )
    monkeypatch.setattr(
        apply_script,
        "_load_patient_mapping",
        lambda *_args: {1001: 501},
    )
    monkeypatch.setattr(
        apply_script,
        "_load_appointment_patient_links",
        lambda *_args: {},
    )
    monkeypatch.setattr(
        apply_script,
        "_load_existing_core_conflicts",
        lambda *_args: (),
    )
    monkeypatch.setattr(
        apply_script,
        "_load_existing_core_legacy_ids",
        lambda *_args: (),
    )

    payload = apply_script.run_apply(
        dryrun_report_json=str(dryrun),
        output_json=str(output),
        confirm=GUARDED_CORE_PROMOTION_CONFIRMATION,
    )

    assert session.committed is True
    assert session.closed is True
    assert len(session.added) == 1
    assert payload["summary"]["source_database"] == "dental_pms_core_promotion_scratch"
    assert payload["summary"]["core_appointments"] == {
        "before": 10,
        "after": 11,
        "delta": 1,
        "expected_after": 11,
    }
    assert payload["summary"]["result_counts"]["created"] == 1
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted["summary"]["result_counts"] == {
        "created": 1,
        "refused": 0,
        "skipped": 0,
        "updated": 0,
    }
