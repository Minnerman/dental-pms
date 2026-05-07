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
)


SYNTHETIC_MANIFEST_ID = "ob-synthetic-20260507-000001"
SYNTHETIC_REPO_SHA = "synthetic-proof-sha"
SYNTHETIC_EXPECTED_TOTAL = "7.34"
SYNTHETIC_ELIGIBLE_COUNT = 2


def synthetic_patient_stats_row(patient_code: str, balance: str) -> dict[str, str]:
    return {
        "PatientCode": patient_code,
        "Balance": balance,
        "TreatmentBalance": balance,
        "SundriesBalance": "0.00",
        "NHSBalance": "0.00",
        "PrivateBalance": balance,
        "DPBBalance": "0.00",
        "AgeDebtor30To60": "0.00",
        "AgeDebtor60To90": "0.00",
        "AgeDebtor90Plus": "0.00",
    }


def write_synthetic_report(tmp_path: Path) -> Path:
    report = build_opening_balance_snapshot_dry_run_report(
        [
            synthetic_patient_stats_row("TEST-R4OB-001", "12.34"),
            synthetic_patient_stats_row("TEST-R4OB-002", "-5.00"),
        ],
        {"TEST-R4OB-001": 901, "TEST-R4OB-002": 902},
        generated_at=datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc),
        repo_sha=SYNTHETIC_REPO_SHA,
        sample_limit=10,
        dry_run_parameters={
            "mapping_source": "synthetic_tmp_path_mapping",
            "source_kind": "synthetic_non_r4",
        },
    )
    report["before_finance_counts"] = {
        "patient_ledger_entries": 0,
        "invoices": 0,
        "payments": 0,
    }
    path = tmp_path / "synthetic_opening_balance_dryrun_report.json"
    path.write_text(json.dumps(report, sort_keys=True), encoding="utf-8")
    return path


def scratch_database_path(tmp_path: Path) -> Path:
    return tmp_path / "dental_pms_opening_balance_synthetic_scratch_test.sqlite"


def scratch_database_url(tmp_path: Path) -> str:
    return f"sqlite:///{scratch_database_path(tmp_path)}"


def create_synthetic_scratch_database(database_url: str):
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
        session.add(
            User(
                id=1,
                email="synthetic-proof-operator@example.invalid",
                full_name="Synthetic Proof Operator",
                hashed_password="not-used",
            )
        )
        session.flush()
        session.add_all(
            [
                Patient(
                    id=901,
                    first_name="TEST-R4OB-001",
                    last_name="SYNTHETIC",
                    created_by_user_id=1,
                    updated_by_user_id=1,
                ),
                Patient(
                    id=902,
                    first_name="TEST-R4OB-002",
                    last_name="SYNTHETIC",
                    created_by_user_id=1,
                    updated_by_user_id=1,
                ),
            ]
        )
        session.commit()
    return engine, SessionLocal


def base_cli_args(
    *,
    report_path: Path,
    database_url: str,
    output_json: Path,
) -> list[str]:
    return [
        "--dry-run-report-json",
        str(report_path),
        "--database-url",
        database_url,
        "--manifest-id",
        SYNTHETIC_MANIFEST_ID,
        "--output-json",
        str(output_json),
        "--expected-report-sha256",
        compute_sha256(report_path),
        "--expected-total-balance",
        SYNTHETIC_EXPECTED_TOTAL,
        "--expected-eligible-count",
        str(SYNTHETIC_ELIGIBLE_COUNT),
        "--expected-repo-sha",
        SYNTHETIC_REPO_SHA,
    ]


def assert_no_personal_fields_logged(payload: object) -> None:
    rendered = json.dumps(payload, sort_keys=True).lower()
    for forbidden in ("first_name", "last_name", "address", "dob", "phone"):
        assert forbidden not in rendered


def test_bounded_synthetic_guarded_scratch_apply_cli_execution_proof(
    tmp_path,
    capsys,
):
    report_path = write_synthetic_report(tmp_path)
    database_url = scratch_database_url(tmp_path)

    validation_output = tmp_path / "validation_summary.json"
    assert (
        apply_script.main(
            base_cli_args(
                report_path=report_path,
                database_url=database_url,
                output_json=validation_output,
            )
        )
        == 0
    )
    validation_stdout = json.loads(capsys.readouterr().out)

    assert validation_output.exists()
    assert not scratch_database_path(tmp_path).exists()
    assert validation_stdout["apply_requested"] is False
    assert validation_stdout["result_counts"] == {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "refused": 0,
    }
    assert_no_personal_fields_logged(validation_stdout)

    unsafe_output = tmp_path / "unsafe_target.json"
    with pytest.raises(OpeningBalanceScratchApplyError, match="scratch/test"):
        apply_script.main(
            base_cli_args(
                report_path=report_path,
                database_url=f"sqlite:///{tmp_path / 'dental_pms'}",
                output_json=unsafe_output,
            )
        )
    assert not unsafe_output.exists()
    capsys.readouterr()

    mismatch_cases = [
        (
            ["--expected-report-sha256", "0" * 64],
            "SHA256 mismatch",
        ),
        (
            ["--expected-total-balance", "99.99"],
            "total balance mismatch",
        ),
        (
            ["--expected-eligible-count", "99"],
            "eligible count mismatch",
        ),
    ]
    for index, (override_args, match) in enumerate(mismatch_cases, start=1):
        args = base_cli_args(
            report_path=report_path,
            database_url=database_url,
            output_json=tmp_path / f"identity_mismatch_{index}.json",
        )
        option = override_args[0]
        option_index = args.index(option)
        args[option_index + 1] = override_args[1]
        with pytest.raises(OpeningBalanceScratchApplyError, match=match):
            apply_script.main(args)
        capsys.readouterr()

    engine, SessionLocal = create_synthetic_scratch_database(database_url)
    first_output = tmp_path / "first_apply_summary.json"
    apply_args = base_cli_args(
        report_path=report_path,
        database_url=database_url,
        output_json=first_output,
    ) + [
        "--apply",
        "--confirm",
        OPENING_BALANCE_APPLY_CONFIRMATION_TOKEN,
        "--actor-id",
        "1",
    ]
    assert apply_script.main(apply_args) == 0
    first_stdout = json.loads(capsys.readouterr().out)

    assert first_output.exists()
    assert first_stdout["apply_requested"] is True
    assert first_stdout["result_counts"] == {
        "created": 2,
        "updated": 0,
        "skipped": 0,
        "refused": 0,
    }
    assert first_stdout["finance_counts"]["before"] == {
        "patient_ledger_entries": 0,
        "invoices": 0,
        "payments": 0,
    }
    assert first_stdout["finance_counts"]["after"] == {
        "patient_ledger_entries": 2,
        "invoices": 0,
        "payments": 0,
    }

    second_output = tmp_path / "second_apply_summary.json"
    second_args = base_cli_args(
        report_path=report_path,
        database_url=database_url,
        output_json=second_output,
    ) + [
        "--apply",
        "--confirm",
        OPENING_BALANCE_APPLY_CONFIRMATION_TOKEN,
        "--actor-id",
        "1",
    ]
    assert apply_script.main(second_args) == 0
    second_stdout = json.loads(capsys.readouterr().out)

    assert second_output.exists()
    assert second_stdout["result_counts"] == {
        "created": 0,
        "updated": 0,
        "skipped": 2,
        "refused": 0,
    }
    assert second_stdout["finance_counts"]["after"] == {
        "patient_ledger_entries": 2,
        "invoices": 0,
        "payments": 0,
    }

    with SessionLocal() as session:
        ledger_rows = session.execute(
            select(PatientLedgerEntry).order_by(PatientLedgerEntry.reference)
        ).scalars().all()
        assert [row.reference for row in ledger_rows] == [
            f"R4OB:{SYNTHETIC_MANIFEST_ID}:TEST-R4OB-001",
            f"R4OB:{SYNTHETIC_MANIFEST_ID}:TEST-R4OB-002",
        ]
        assert [row.amount_pence for row in ledger_rows] == [1234, -500]
        assert [row.patient_id for row in ledger_rows] == [901, 902]
        assert all(row.related_invoice_id is None for row in ledger_rows)
        assert session.query(PatientLedgerEntry).count() == 2
        assert session.query(Invoice).count() == 0
        assert session.query(Payment).count() == 0

    proof_summary = {
        "manifest_id": SYNTHETIC_MANIFEST_ID,
        "synthetic_row_count": SYNTHETIC_ELIGIBLE_COUNT,
        "expected_total": SYNTHETIC_EXPECTED_TOTAL,
        "first_run_counts": first_stdout["result_counts"],
        "second_run_counts": second_stdout["result_counts"],
        "target_type": "local SQLite scratch/test under pytest tmp_path",
        "no_real_pms_database": True,
        "no_r4_access": True,
        "no_real_patient_data": True,
        "finance_import_ready": False,
    }
    proof_summary_path = tmp_path / "synthetic_proof_summary.json"
    proof_summary_path.write_text(
        json.dumps(proof_summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    assert proof_summary["first_run_counts"]["created"] == 2
    assert proof_summary["second_run_counts"]["skipped"] == 2
    assert_no_personal_fields_logged(proof_summary)
    engine.dispose()
