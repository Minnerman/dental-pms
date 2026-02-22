from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.patient import Patient
from app.services.r4_import.sqlserver_source import R4SqlServerConfig


DEFAULT_DATE_FROM = "2017-01-01"
DEFAULT_DATE_TO = "2026-02-01"


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_rows(payload: object) -> list[dict[str, object]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = payload.get("patients")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    raise RuntimeError("Proof payload must be a JSON array or an object with a 'patients' array.")


def _extract_legacy_codes(rows: list[dict[str, object]]) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    for row in rows:
        raw = row.get("legacy_patient_code")
        if not isinstance(raw, int):
            continue
        if raw in seen:
            continue
        seen.add(raw)
        out.append(raw)
    if not out:
        raise RuntimeError("No legacy_patient_code values found in proof payload.")
    return out


def _run_import(args: list[str]) -> None:
    cmd = [sys.executable, "-m", "app.scripts.r4_import", *args]
    completed = subprocess.run(cmd)
    if completed.returncode != 0:
        raise RuntimeError(f"r4_import failed ({completed.returncode}): {' '.join(cmd)}")


def _map_patient_ids(legacy_codes: list[int]) -> dict[int, int]:
    legacy_ids = [str(code) for code in legacy_codes]
    with SessionLocal() as session:
        rows = session.execute(
            select(Patient.id, Patient.legacy_id).where(Patient.legacy_id.in_(legacy_ids))
        ).all()

    mapped: dict[int, int] = {}
    for patient_id, legacy_id in rows:
        if legacy_id is None:
            continue
        try:
            mapped[int(legacy_id)] = int(patient_id)
        except ValueError:
            continue
    return mapped


def _write_proof_payload(
    payload: object,
    *,
    proof_out: Path,
    patient_id_map: dict[int, int],
) -> tuple[int, list[int]]:
    rows = _extract_rows(payload)
    updated = 0
    missing_codes: list[int] = []
    missing_seen: set[int] = set()
    for row in rows:
        raw = row.get("legacy_patient_code")
        if not isinstance(raw, int):
            continue
        patient_id = patient_id_map.get(raw)
        if patient_id is None:
            if raw not in missing_seen:
                missing_seen.add(raw)
                missing_codes.append(raw)
            continue
        if row.get("patient_id") != patient_id:
            row["patient_id"] = patient_id
            updated += 1

    proof_out.parent.mkdir(parents=True, exist_ok=True)
    proof_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return updated, sorted(missing_codes)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Ensure completed_treatment_findings proof patients exist locally, import their "
            "findings via the read-only R4 path, and refresh proof JSON patient_id values."
        )
    )
    parser.add_argument("--proof-in", type=Path, required=True)
    parser.add_argument("--proof-out", type=Path, required=True)
    parser.add_argument("--date-from", default=DEFAULT_DATE_FROM)
    parser.add_argument("--date-to", default=DEFAULT_DATE_TO)
    parser.add_argument("--row-limit", type=int, default=50000)
    args = parser.parse_args()

    cfg = R4SqlServerConfig.from_env()
    cfg.require_enabled()
    cfg.require_readonly()

    proof_payload = _load_json(args.proof_in)
    rows = _extract_rows(proof_payload)
    legacy_codes = _extract_legacy_codes(rows)
    patient_codes_arg = ",".join(str(code) for code in legacy_codes)

    _run_import(
        [
            "--source",
            "sqlserver",
            "--entity",
            "patients",
            "--apply",
            "--confirm",
            "APPLY",
            "--patient-codes",
            patient_codes_arg,
        ]
    )
    _run_import(
        [
            "--source",
            "sqlserver",
            "--entity",
            "charting_canonical",
            "--apply",
            "--confirm",
            "APPLY",
            "--patient-codes",
            patient_codes_arg,
            "--charting-from",
            str(args.date_from),
            "--charting-to",
            str(args.date_to),
            "--domains",
            "completed_treatment_findings",
            "--limit",
            str(max(1, int(args.row_limit))),
        ]
    )

    patient_id_map = _map_patient_ids(legacy_codes)
    updated_count, missing_codes = _write_proof_payload(
        proof_payload,
        proof_out=args.proof_out,
        patient_id_map=patient_id_map,
    )
    if missing_codes:
        raise RuntimeError(
            "Unable to map patient_id for proof legacy codes after import: "
            + ",".join(str(code) for code in missing_codes)
        )

    print(
        json.dumps(
            {
                "proof_in": str(args.proof_in),
                "proof_out": str(args.proof_out),
                "legacy_codes_count": len(legacy_codes),
                "legacy_codes": legacy_codes,
                "updated_patient_ids": updated_count,
                "date_from": str(args.date_from),
                "date_to": str(args.date_to),
                "row_limit": int(args.row_limit),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
