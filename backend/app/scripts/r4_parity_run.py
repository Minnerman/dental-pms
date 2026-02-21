from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

from app.db.session import SessionLocal
from app.scripts import (
    r4_import as r4_import_script,
    r4_bpe_parity_pack,
    r4_bpe_furcation_parity_pack,
    r4_chart_healing_actions_parity_pack,
    r4_patient_notes_parity_pack,
    r4_perioprobe_parity_pack,
    r4_restorative_treatments_parity_pack,
    r4_treatment_plans_parity_pack,
    r4_treatment_plan_items_parity_pack,
    r4_treatment_notes_parity_pack,
)


ALL_DOMAINS = (
    "bpe",
    "bpe_furcation",
    "chart_healing_actions",
    "restorative_treatments",
    "perioprobe",
    "patient_notes",
    "treatment_plans",
    "treatment_notes",
    "treatment_plan_items",
)


def _parse_patient_codes_csv(raw: str) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    for token in raw.split(","):
        part = token.strip()
        if not part:
            raise RuntimeError("Invalid --patient-codes value: empty token.")
        try:
            code = int(part)
        except ValueError as exc:
            raise RuntimeError(f"Invalid patient code: {part}") from exc
        if code in seen:
            continue
        seen.add(code)
        out.append(code)
    return out


def _parse_domains_csv(raw: str | None) -> list[str]:
    if not raw:
        return list(ALL_DOMAINS)
    out: list[str] = []
    seen: set[str] = set()
    for token in raw.split(","):
        domain = token.strip().lower()
        if not domain:
            raise RuntimeError("Invalid --domains value: empty token.")
        if domain not in ALL_DOMAINS:
            raise RuntimeError(f"Unsupported domain: {domain}")
        if domain in seen:
            continue
        seen.add(domain)
        out.append(domain)
    return out


def _parse_day(raw: str | None) -> date | None:
    if not raw:
        return None
    return date.fromisoformat(raw)


def _count_has_data(patient: dict[str, object]) -> bool:
    for key in (
        "sqlserver_total_rows",
        "sqlserver_count",
    ):
        value = patient.get(key)
        if isinstance(value, int) and value > 0:
            return True
    return False


def _coerce_match_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        all_value = value.get("all")
        if isinstance(all_value, bool):
            return all_value
    return None


def _summary_from_report(domain: str, report: dict[str, object]) -> dict[str, object]:
    patients = report.get("patients") or []
    if not isinstance(patients, list):
        patients = []

    with_data = [p for p in patients if isinstance(p, dict) and _count_has_data(p)]
    no_data_patients = [p for p in patients if isinstance(p, dict) and not _count_has_data(p)]

    latest_matches: list[bool] = []
    digest_matches: list[bool] = []
    for patient in with_data:
        latest_ok = _coerce_match_bool(patient.get("latest_match"))
        if latest_ok is not None:
            latest_matches.append(latest_ok)
        digest_ok = _coerce_match_bool(patient.get("latest_digest_match"))
        if digest_ok is not None:
            digest_matches.append(digest_ok)
        elif latest_ok is not None:
            # Some parity packs (for example bpe) only expose a single latest comparison.
            digest_matches.append(latest_ok)

    latest_match_count = sum(1 for ok in latest_matches if ok)
    digest_match_count = sum(1 for ok in digest_matches if ok)

    if not with_data:
        status = "no_data"
    elif not latest_matches or not digest_matches:
        status = "fail"
    elif latest_match_count == len(latest_matches) and digest_match_count == len(digest_matches):
        status = "pass"
    else:
        status = "fail"

    return {
        "domain": domain,
        "status": status,
        "patients_total": len(patients),
        "patients_with_data": len(with_data),
        "patients_no_data": len(no_data_patients),
        "latest_match": {
            "matched": latest_match_count,
            "total": len(latest_matches),
        },
        "latest_digest_match": {
            "matched": digest_match_count,
            "total": len(digest_matches),
        },
        "warnings": (
            ([f"No SQL Server rows in bounds for {len(no_data_patients)} patient(s)."] if no_data_patients else [])
            + (["Parity comparisons missing despite patients_with_data > 0."] if with_data and (not latest_matches or not digest_matches) else [])
        ),
    }


def run_parity(
    *,
    patient_codes: list[int],
    domains: list[str],
    date_from: date | None,
    date_to: date | None,
    row_limit: int,
    output_dir: str | None,
) -> dict[str, object]:
    report: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "patient_codes": patient_codes,
        "domains": domains,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "row_limit": row_limit,
        "domain_reports": {},
        "domain_summaries": {},
    }

    output_path: Path | None = None
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

    with SessionLocal() as session:
        for domain in domains:
            if domain == "bpe":
                domain_report = r4_bpe_parity_pack.build_parity_report(
                    session,
                    patient_codes=patient_codes,
                    charting_from=date_from,
                    charting_to=date_to,
                    row_limit=row_limit,
                    include_sqlserver=True,
                )
            elif domain == "bpe_furcation":
                domain_report = r4_bpe_furcation_parity_pack.build_parity_report(
                    session,
                    patient_codes=patient_codes,
                    date_from=date_from,
                    date_to=date_to,
                    row_limit=row_limit,
                    include_sqlserver=True,
                )
            elif domain == "chart_healing_actions":
                domain_report = r4_chart_healing_actions_parity_pack.build_parity_report(
                    session,
                    patient_codes=patient_codes,
                    date_from=date_from,
                    date_to=date_to,
                    row_limit=row_limit,
                    include_sqlserver=True,
                )
            elif domain == "perioprobe":
                domain_report = r4_perioprobe_parity_pack.build_parity_report(
                    session,
                    patient_codes=patient_codes,
                    charting_from=date_from,
                    charting_to=date_to,
                    row_limit=row_limit,
                    include_sqlserver=True,
                )
            elif domain == "restorative_treatments":
                domain_report = r4_restorative_treatments_parity_pack.build_parity_report(
                    session,
                    patient_codes=patient_codes,
                    date_from=date_from,
                    date_to=date_to,
                    row_limit=row_limit,
                    include_sqlserver=True,
                )
            elif domain == "patient_notes":
                domain_report = r4_patient_notes_parity_pack.build_parity_report(
                    session,
                    patient_codes=patient_codes,
                    date_from=date_from,
                    date_to=date_to,
                    row_limit=row_limit,
                    include_sqlserver=True,
                )
            elif domain == "treatment_notes":
                domain_report = r4_treatment_notes_parity_pack.build_parity_report(
                    session,
                    patient_codes=patient_codes,
                    date_from=date_from,
                    date_to=date_to,
                    row_limit=row_limit,
                    include_sqlserver=True,
                )
            elif domain == "treatment_plans":
                domain_report = r4_treatment_plans_parity_pack.build_parity_report(
                    session,
                    patient_codes=patient_codes,
                    date_from=date_from,
                    date_to=date_to,
                    row_limit=row_limit,
                    include_sqlserver=True,
                )
            elif domain == "treatment_plan_items":
                domain_report = r4_treatment_plan_items_parity_pack.build_parity_report(
                    session,
                    patient_codes=patient_codes,
                    date_from=date_from,
                    date_to=date_to,
                    row_limit=row_limit,
                    include_sqlserver=True,
                )
            else:  # pragma: no cover - protected by parser
                raise RuntimeError(f"Unsupported domain: {domain}")

            report["domain_reports"][domain] = domain_report
            report["domain_summaries"][domain] = _summary_from_report(domain, domain_report)
            if output_path is not None:
                (output_path / f"{domain}.json").write_text(
                    json.dumps(domain_report, indent=2), encoding="utf-8"
                )

    summaries = report["domain_summaries"]
    statuses = [summaries[d]["status"] for d in domains]
    has_fail = any(status == "fail" for status in statuses)
    has_data = any(status != "no_data" for status in statuses)

    report["overall"] = {
        "status": "fail" if has_fail else "pass",
        "has_data": has_data,
        "domains_requested": len(domains),
        "domains_failed": sum(1 for status in statuses if status == "fail"),
        "domains_no_data": sum(1 for status in statuses if status == "no_data"),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run consolidated R4 parity packs for selected domains and patients."
    )
    patient_codes_group = parser.add_mutually_exclusive_group(required=True)
    patient_codes_group.add_argument(
        "--patient-codes",
        help="Comma-separated patient codes.",
    )
    patient_codes_group.add_argument(
        "--patient-codes-file",
        help="Path to patient codes file (CSV and/or newline-separated).",
    )
    parser.add_argument("--output-json", required=True, help="Path for combined JSON report.")
    parser.add_argument("--output-dir", help="Optional directory for per-domain JSON reports.")
    parser.add_argument(
        "--domains",
        help=(
            "Comma-separated subset: "
            "bpe,bpe_furcation,chart_healing_actions,perioprobe,patient_notes,treatment_plans,treatment_notes,treatment_plan_items "
            "(default all)."
        ),
    )
    parser.add_argument("--date-from", help="Inclusive start date (YYYY-MM-DD).")
    parser.add_argument("--date-to", help="Inclusive end date (YYYY-MM-DD).")
    parser.add_argument("--row-limit", type=int, default=1000)
    args = parser.parse_args()

    if args.row_limit <= 0:
        raise RuntimeError("--row-limit must be positive.")

    patient_codes = r4_import_script._parse_patient_codes_arg(
        args.patient_codes, args.patient_codes_file
    )
    if patient_codes is None:  # pragma: no cover - mutually exclusive group is required
        raise RuntimeError("Either --patient-codes or --patient-codes-file is required.")
    domains = _parse_domains_csv(args.domains)
    date_from = _parse_day(args.date_from)
    date_to = _parse_day(args.date_to)
    print(
        f"resolved_patient_codes count={len(patient_codes)} "
        f"first={patient_codes[0]} last={patient_codes[-1]}"
    )

    combined = run_parity(
        patient_codes=patient_codes,
        domains=domains,
        date_from=date_from,
        date_to=date_to,
        row_limit=args.row_limit,
        output_dir=args.output_dir,
    )

    out = Path(args.output_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(combined, indent=2), encoding="utf-8")
    print(json.dumps(combined, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
