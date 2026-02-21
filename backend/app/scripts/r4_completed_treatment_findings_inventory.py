from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import date
from math import ceil
from pathlib import Path

from app.services.r4_charting.completed_treatment_findings_scout import (
    CompletedTreatmentFindingRow,
    apply_drop_reason_skeleton,
)
from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource
from app.services.tooth_state_classification import classify_tooth_state_type


def _to_int(value) -> int:  # type: ignore[no-untyped-def]
    if value is None:
        return 0
    return int(value)


def _stable_hash_key(patient_code: int, *, seed: int) -> int:
    payload = f"{seed}:{patient_code}".encode("ascii")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=False)


def _select_codes_hashed(codes: set[int], *, seed: int, limit: int | None = None) -> list[int]:
    ordered = sorted(codes, key=lambda code: (_stable_hash_key(code, seed=seed), code))
    if limit is not None:
        return ordered[:limit]
    return ordered


def _load_rows(source: R4SqlServerSource, *, date_from: date, date_to: date) -> list[CompletedTreatmentFindingRow]:
    rows = source.list_completed_treatment_findings(
        patients_from=None,
        patients_to=None,
        date_from=date_from,
        date_to=date_to,
        limit=None,
    )
    return list(rows)


def _top_codes(source: R4SqlServerSource, *, date_from: date, date_to: date, limit: int) -> list[dict[str, object]]:
    rows = source._query(  # noqa: SLF001
        (
            "SELECT TOP (?) "
            "CodeID AS code_id, "
            "Treatment AS treatment_label, "
            "COUNT(1) AS row_count "
            "FROM dbo.vwCompletedTreatmentTransactions WITH (NOLOCK) "
            "WHERE CompletedDate >= ? AND CompletedDate < ? "
            "GROUP BY CodeID, Treatment "
            "ORDER BY COUNT(1) DESC"
        ),
        [limit, date_from, date_to],
    )

    out: list[dict[str, object]] = []
    for row in rows:
        label = (row.get("treatment_label") or "").strip() or None
        out.append(
            {
                "code_id": _to_int(row.get("code_id")) if row.get("code_id") is not None else None,
                "treatment_label": label,
                "row_count": _to_int(row.get("row_count")),
                "classification": classify_tooth_state_type(label),
            }
        )
    return out


def _proof_patients(rows: list[CompletedTreatmentFindingRow], *, seed: int, limit: int = 5) -> list[int]:
    counts: Counter[int] = Counter()
    for row in rows:
        if row.patient_code is None:
            continue
        counts[int(row.patient_code)] += 1
    ranked = sorted(
        counts.items(),
        key=lambda item: (-item[1], _stable_hash_key(item[0], seed=seed), item[0]),
    )
    return [patient_code for patient_code, _ in ranked[:limit]]


def run_inventory(
    *,
    date_from: date,
    date_to: date,
    seed: int,
    cohort_limit: int,
    top_code_limit: int,
) -> dict[str, object]:
    config = R4SqlServerConfig.from_env()
    config.require_enabled()
    config.require_readonly()

    source = R4SqlServerSource(config)
    source.ensure_select_only()

    raw_rows = _load_rows(source, date_from=date_from, date_to=date_to)
    accepted_rows, drop_report = apply_drop_reason_skeleton(raw_rows, date_from=date_from, date_to=date_to)

    raw_patients = {
        int(row.patient_code)
        for row in raw_rows
        if row.patient_code is not None
    }
    accepted_patients = {
        int(row.patient_code)
        for row in accepted_rows
        if row.patient_code is not None
    }

    top_codes = _top_codes(source, date_from=date_from, date_to=date_to, limit=top_code_limit)
    top_code_classification_counts = Counter(
        str(item.get("classification")) for item in top_codes if item.get("classification")
    )

    ordered_codes = _select_codes_hashed(accepted_patients, seed=seed, limit=None)
    selected_codes = ordered_codes[:cohort_limit]

    return {
        "domain": "completed_treatment_findings",
        "source_table": "dbo.vwCompletedTreatmentTransactions",
        "window": {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        },
        "selection": {
            "order": "hashed",
            "seed": seed,
            "cohort_limit": cohort_limit,
            "selected_count": len(selected_codes),
            "selected_patient_codes": selected_codes,
        },
        "summary": {
            "rows_in_window": len(raw_rows),
            "patients_in_window": len(raw_patients),
            "rows_with_tooth": sum(1 for row in raw_rows if row.tooth is not None),
            "rows_with_code_id": sum(1 for row in raw_rows if row.code_id is not None),
            "accepted_rows": len(accepted_rows),
            "accepted_patients": len(accepted_patients),
            "recommended_chunk_size": 200,
            "estimated_chunks": ceil(len(accepted_patients) / 200) if accepted_patients else 0,
            "recommended_seen_ledger": ".run/seen_stage163f_completed_treatment_findings.txt",
        },
        "drop_reasons_skeleton": drop_report.as_dict(),
        "proof_patients": _proof_patients(accepted_rows, seed=seed, limit=5),
        "top_codes": top_codes,
        "top_code_classifications": dict(sorted(top_code_classification_counts.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only inventory scout for Stage 163F candidate domain "
            "completed_treatment_findings (vwCompletedTreatmentTransactions)."
        )
    )
    parser.add_argument("--date-from", required=True, help="Inclusive start date (YYYY-MM-DD).")
    parser.add_argument("--date-to", required=True, help="Exclusive end date (YYYY-MM-DD).")
    parser.add_argument("--seed", type=int, default=17, help="Deterministic hashed ordering seed.")
    parser.add_argument(
        "--cohort-limit",
        type=int,
        default=200,
        help="Max number of selected patient codes to emit in the scout cohort.",
    )
    parser.add_argument(
        "--top-code-limit",
        type=int,
        default=50,
        help="Top grouped code rows to include in the report.",
    )
    parser.add_argument("--output-json", required=True, help="Path to write JSON report.")
    parser.add_argument(
        "--output-csv",
        help="Optional path to write selected patient_code CSV (single column).",
    )
    args = parser.parse_args()

    date_from = date.fromisoformat(args.date_from)
    date_to = date.fromisoformat(args.date_to)
    if date_to <= date_from:
        raise RuntimeError("--date-to must be after --date-from.")

    report = run_inventory(
        date_from=date_from,
        date_to=date_to,
        seed=args.seed,
        cohort_limit=args.cohort_limit,
        top_code_limit=args.top_code_limit,
    )

    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.output_csv:
        output_csv = Path(args.output_csv)
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        selected_codes = report["selection"]["selected_patient_codes"]
        with output_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["patient_code"])
            for code in selected_codes:
                writer.writerow([code])

    print(
        json.dumps(
            {
                "output_json": str(output_json),
                "rows_in_window": report["summary"]["rows_in_window"],
                "accepted_patients": report["summary"]["accepted_patients"],
                "selected_count": report["selection"]["selected_count"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
