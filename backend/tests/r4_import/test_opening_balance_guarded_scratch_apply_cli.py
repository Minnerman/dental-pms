from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models.appointment import Appointment
from app.models.base import Base
from app.models.invoice import Invoice, Payment
from app.models.ledger import PatientLedgerEntry
from app.models.patient import Patient
from app.models.user import User
from app.scripts import r4_opening_balance_guarded_scratch_apply as apply_script
from app.services.r4_import.opening_balance_snapshot_apply_plan import (
    OPENING_BALANCE_APPLY_CONFIRMATION_TOKEN,
)
from app.services.r4_import.opening_balance_snapshot_dry_run import (
    build_opening_balance_snapshot_dry_run_report,
)
from app.services.r4_import.opening_balance_snapshot_guarded_apply import (
    OpeningBalanceScratchApplyError,
    compute_sha256,
    run_opening_balance_scratch_apply,
)


SCRATCH_MANIFEST_ID = "ob-20260506153000-abcdef123456"


def patient_stats_row(**overrides):
    row = {
        "PatientCode": "P1",
        "Balance": "10.00",
        "TreatmentBalance": "10.00",
        "SundriesBalance": "0.00",
        "NHSBalance": "0.00",
        "PrivateBalance": "10.00",
        "DPBBalance": "0.00",
        "AgeDebtor30To60": "0.00",
        "AgeDebtor60To90": "0.00",
        "AgeDebtor90Plus": "0.00",
    }
    row.update(overrides)
    return row


def write_report(tmp_path: Path, *, sample_limit: int = 10) -> Path:
    report = build_opening_balance_snapshot_dry_run_report(
        [
            patient_stats_row(PatientCode="P1"),
            patient_stats_row(
                PatientCode="P2",
                Balance="-4.25",
                TreatmentBalance="-4.25",
                PrivateBalance="-4.25",
            ),
            patient_stats_row(
                PatientCode="P3",
                Balance="0.00",
                TreatmentBalance="0.00",
                PrivateBalance="0.00",
            ),
        ],
        {"P1": 101, "P2": 102},
        generated_at=datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc),
        repo_sha="test-sha",
        sample_limit=sample_limit,
        dry_run_parameters={"mapping_source": "scratch_patient_mapping.json"},
    )
    report["before_finance_counts"] = {
        "patient_ledger_entries": 0,
        "invoices": 0,
        "payments": 0,
    }
    path = tmp_path / "opening_balance_snapshot_dryrun_report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def scratch_database_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'dental_pms_opening_balance_scratch_test.sqlite'}"


def create_scratch_database(database_url: str):
    engine = create_engine(database_url)
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Patient.__table__,
            Appointment.__table__,
            Invoice.__table__,
            Payment.__table__,
            PatientLedgerEntry.__table__,
        ],
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with SessionLocal() as session:
        user = User(
            id=1,
            email="scratch-operator@example.com",
            full_name="Scratch Operator",
            hashed_password="not-used",
        )
        session.add(user)
        session.flush()
        session.add_all(
            [
                Patient(
                    id=101,
                    first_name="Scratch",
                    last_name="Patient One",
                    created_by_user_id=1,
                    updated_by_user_id=1,
                ),
                Patient(
                    id=102,
                    first_name="Scratch",
                    last_name="Patient Two",
                    created_by_user_id=1,
                    updated_by_user_id=1,
                ),
            ]
        )
        session.commit()
    return engine, SessionLocal


def test_non_scratch_target_is_rejected_before_output(tmp_path):
    report_path = write_report(tmp_path)
    output = tmp_path / "apply.json"

    with pytest.raises(OpeningBalanceScratchApplyError, match="scratch/test"):
        run_opening_balance_scratch_apply(
            dry_run_report_path=report_path,
            database_url="postgresql+psycopg://dental_pms:secret@db:5432/dental_pms",
            manifest_id=SCRATCH_MANIFEST_ID,
            output_json=output,
        )

    assert not output.exists()


def test_production_live_looking_scratch_target_is_rejected(tmp_path):
    report_path = write_report(tmp_path)
    output = tmp_path / "apply.json"

    with pytest.raises(OpeningBalanceScratchApplyError, match="production/live"):
        run_opening_balance_scratch_apply(
            dry_run_report_path=report_path,
            database_url=f"sqlite:///{tmp_path / 'prod_opening_balance_scratch.sqlite'}",
            manifest_id=SCRATCH_MANIFEST_ID,
            output_json=output,
        )

    assert not output.exists()


def test_apply_requires_confirmation_token(tmp_path):
    report_path = write_report(tmp_path)
    output = tmp_path / "apply.json"

    with pytest.raises(SystemExit) as exc:
        apply_script.main(
            [
                "--dry-run-report-json",
                str(report_path),
                "--database-url",
                scratch_database_url(tmp_path),
                "--manifest-id",
                SCRATCH_MANIFEST_ID,
                "--output-json",
                str(output),
                "--apply",
                "--actor-id",
                "1",
            ]
        )

    assert exc.value.code == 2
    assert not output.exists()


def test_validate_only_writes_report_but_does_not_create_sqlite_database(tmp_path, capsys):
    report_path = write_report(tmp_path)
    database_path = tmp_path / "dental_pms_opening_balance_scratch_test.sqlite"
    output = tmp_path / "validate.json"

    assert (
        apply_script.main(
            [
                "--dry-run-report-json",
                str(report_path),
                "--database-url",
                f"sqlite:///{database_path}",
                "--manifest-id",
                SCRATCH_MANIFEST_ID,
                "--output-json",
                str(output),
                "--expected-report-sha256",
                compute_sha256(report_path),
                "--expected-total-balance",
                "5.75",
                "--expected-eligible-count",
                "2",
                "--expected-repo-sha",
                "test-sha",
            ]
        )
        == 0
    )

    assert output.exists()
    assert not database_path.exists()
    stdout = json.loads(capsys.readouterr().out)
    assert stdout["apply_requested"] is False
    assert stdout["result_counts"] == {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "refused": 0,
    }


def test_valid_scratch_apply_creates_only_ledger_adjustments_and_no_invoices_or_payments(
    tmp_path,
):
    report_path = write_report(tmp_path)
    database_url = scratch_database_url(tmp_path)
    engine, SessionLocal = create_scratch_database(database_url)
    output = tmp_path / "apply.json"

    payload = run_opening_balance_scratch_apply(
        dry_run_report_path=report_path,
        database_url=database_url,
        manifest_id=SCRATCH_MANIFEST_ID,
        apply=True,
        confirmation_token=OPENING_BALANCE_APPLY_CONFIRMATION_TOKEN,
        actor_id=1,
        output_json=output,
        expected_report_sha256=compute_sha256(report_path),
        expected_total_balance="5.75",
        expected_eligible_count=2,
        expected_repo_sha="test-sha",
    )

    assert payload["summary"]["result_counts"] == {
        "created": 2,
        "updated": 0,
        "skipped": 0,
        "refused": 0,
    }
    assert payload["summary"]["finance_import_ready"] is False
    with SessionLocal() as session:
        ledger_rows = session.execute(
            select(PatientLedgerEntry).order_by(PatientLedgerEntry.reference)
        ).scalars().all()
        assert [row.amount_pence for row in ledger_rows] == [1000, -425]
        assert [row.patient_id for row in ledger_rows] == [101, 102]
        assert all(row.related_invoice_id is None for row in ledger_rows)
        assert session.query(Invoice).count() == 0
        assert session.query(Payment).count() == 0

    assert output.exists()
    engine.dispose()


def test_re_running_same_manifest_is_idempotent_without_duplicate_rows(tmp_path):
    report_path = write_report(tmp_path)
    database_url = scratch_database_url(tmp_path)
    engine, SessionLocal = create_scratch_database(database_url)
    kwargs = {
        "dry_run_report_path": report_path,
        "database_url": database_url,
        "manifest_id": SCRATCH_MANIFEST_ID,
        "apply": True,
        "confirmation_token": OPENING_BALANCE_APPLY_CONFIRMATION_TOKEN,
        "actor_id": 1,
        "expected_report_sha256": compute_sha256(report_path),
        "expected_total_balance": "5.75",
        "expected_eligible_count": 2,
        "expected_repo_sha": "test-sha",
    }

    run_opening_balance_scratch_apply(output_json=tmp_path / "first.json", **kwargs)
    second = run_opening_balance_scratch_apply(
        output_json=tmp_path / "second.json",
        **kwargs,
    )

    assert second["summary"]["result_counts"] == {
        "created": 0,
        "updated": 0,
        "skipped": 2,
        "refused": 0,
    }
    with SessionLocal() as session:
        assert session.query(PatientLedgerEntry).count() == 2

    engine.dispose()


def test_checksum_and_expected_total_mismatches_are_refused(tmp_path):
    report_path = write_report(tmp_path)

    with pytest.raises(OpeningBalanceScratchApplyError, match="SHA256 mismatch"):
        run_opening_balance_scratch_apply(
            dry_run_report_path=report_path,
            database_url=scratch_database_url(tmp_path),
            manifest_id=SCRATCH_MANIFEST_ID,
            output_json=tmp_path / "sha.json",
            expected_report_sha256="0" * 64,
        )

    with pytest.raises(OpeningBalanceScratchApplyError, match="total balance mismatch"):
        run_opening_balance_scratch_apply(
            dry_run_report_path=report_path,
            database_url=scratch_database_url(tmp_path),
            manifest_id=SCRATCH_MANIFEST_ID,
            output_json=tmp_path / "total.json",
            expected_total_balance="100.00",
        )


def test_invalid_artifact_is_refused(tmp_path):
    report_path = tmp_path / "invalid.json"
    report_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(OpeningBalanceScratchApplyError, match="JSON is invalid"):
        run_opening_balance_scratch_apply(
            dry_run_report_path=report_path,
            database_url=scratch_database_url(tmp_path),
            manifest_id=SCRATCH_MANIFEST_ID,
            output_json=tmp_path / "apply.json",
        )


def test_cli_has_no_r4_or_external_service_dependency():
    backend_root = Path(__file__).resolve().parents[2]
    files = [
        backend_root / "app/scripts/r4_opening_balance_guarded_scratch_apply.py",
        backend_root
        / "app/services/r4_import/opening_balance_snapshot_guarded_apply.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)

    assert "R4SqlServerSource" not in combined
    assert "pyodbc" not in combined
    assert "app.db.session" not in combined
