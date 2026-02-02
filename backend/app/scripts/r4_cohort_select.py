from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from app.scripts import r4_import as r4_import_script
from app.services.r4_charting.sqlserver_extract import (
    get_distinct_bpe_furcation_patient_codes,
    get_distinct_bpe_patient_codes,
    get_distinct_perioprobe_patient_codes,
)


ALL_DOMAINS = ("perioprobe", "bpe", "bpe_furcation")


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


def _build_domain_codes(
    domain: str,
    *,
    date_from: str,
    date_to: str,
    limit: int,
) -> list[int]:
    if domain == "perioprobe":
        return get_distinct_perioprobe_patient_codes(date_from, date_to, limit=limit)
    if domain == "bpe":
        return get_distinct_bpe_patient_codes(date_from, date_to, limit=limit)
    if domain == "bpe_furcation":
        return get_distinct_bpe_furcation_patient_codes(date_from, date_to, limit=limit)
    raise RuntimeError(f"Unsupported domain: {domain}")


def _parse_exclude_patient_codes_file(path: str | None) -> set[int]:
    if not path:
        return set()
    try:
        return set(r4_import_script._parse_patient_codes_file(path))
    except RuntimeError as exc:
        # Allow empty exclude files to behave as "no exclusions".
        if "no patient codes provided" in str(exc):
            return set()
        raise


def _stable_hash_key(patient_code: int, *, seed: int) -> int:
    payload = f"{seed}:{patient_code}".encode("ascii")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=False)


def _order_patient_codes(codes: list[int], *, order: str, seed: int | None) -> list[int]:
    if order == "asc":
        return sorted(codes)
    if order == "hashed":
        if seed is None:
            raise RuntimeError("--seed is required when --order=hashed.")
        return sorted(codes, key=lambda code: (_stable_hash_key(code, seed=seed), code))
    raise RuntimeError("--order must be one of: asc, hashed.")


def select_cohort(
    *,
    domains: list[str],
    date_from: str,
    date_to: str,
    limit: int,
    mode: str,
    excluded_patient_codes: set[int] | None = None,
    order: str = "asc",
    seed: int | None = None,
) -> dict[str, object]:
    if limit <= 0:
        raise RuntimeError("--limit must be positive.")
    if mode not in {"union", "intersection"}:
        raise RuntimeError("--mode must be one of: union, intersection.")

    domain_codes: dict[str, list[int]] = {}
    domain_errors: dict[str, str] = {}
    for domain in domains:
        try:
            codes = _build_domain_codes(domain, date_from=date_from, date_to=date_to, limit=limit)
            domain_codes[domain] = sorted(set(codes))
        except RuntimeError as exc:
            domain_codes[domain] = []
            domain_errors[domain] = str(exc)

    excluded = excluded_patient_codes or set()
    if not domains:
        merged_codes: list[int] = []
    elif mode == "union":
        merged = set().union(*(set(domain_codes[d]) for d in domains))
        merged_codes = list(merged)
    else:
        merged = set(domain_codes[domains[0]])
        for domain in domains[1:]:
            merged &= set(domain_codes[domain])
        merged_codes = list(merged)

    merged_codes = _order_patient_codes(merged_codes, order=order, seed=seed)

    filtered_codes = [code for code in merged_codes if code not in excluded]
    if excluded and merged_codes and not filtered_codes:
        raise RuntimeError(
            "Exclusion removed all candidate patient codes; adjust "
            "--exclude-patient-codes-file or selection parameters."
        )
    remaining_after_exclude = len(filtered_codes)
    final_codes = filtered_codes[:limit]

    return {
        "domains": domains,
        "mode": mode,
        "date_from": date_from,
        "date_to": date_to,
        "limit": limit,
        "order": order,
        "seed": seed,
        "exclude_count": len(excluded),
        "remaining_after_exclude": remaining_after_exclude,
        "selected_count": len(final_codes),
        "domain_counts": {domain: len(domain_codes[domain]) for domain in domains},
        "domain_errors": domain_errors,
        "cohort_size": len(final_codes),
        "patient_codes": final_codes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Select deterministic R4 patient cohorts with in-window charting data."
    )
    parser.add_argument(
        "--domains",
        default="perioprobe,bpe,bpe_furcation",
        help="Comma-separated subset: perioprobe,bpe,bpe_furcation.",
    )
    parser.add_argument("--date-from", required=True, help="Inclusive start date (YYYY-MM-DD).")
    parser.add_argument("--date-to", required=True, help="Exclusive end date (YYYY-MM-DD).")
    parser.add_argument("--limit", type=int, default=50, help="Maximum cohort size.")
    parser.add_argument(
        "--mode",
        default="union",
        choices=("union", "intersection"),
        help="How to combine per-domain sets (default: union).",
    )
    parser.add_argument(
        "--order",
        default="asc",
        choices=("asc", "hashed"),
        help="How to order merged patient codes before exclusions/limit (default: asc).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Required when --order=hashed; changes deterministic cohort ordering.",
    )
    parser.add_argument(
        "--exclude-patient-codes-file",
        help="Optional path to patient codes file (CSV/newline) to exclude before limit.",
    )
    parser.add_argument("--output", required=True, help="Path to output CSV file.")
    args = parser.parse_args()

    domains = _parse_domains_csv(args.domains)
    excluded_patient_codes = _parse_exclude_patient_codes_file(args.exclude_patient_codes_file)
    report = select_cohort(
        domains=domains,
        date_from=args.date_from,
        date_to=args.date_to,
        limit=args.limit,
        mode=args.mode,
        excluded_patient_codes=excluded_patient_codes,
        order=args.order,
        seed=args.seed,
    )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(",".join(str(code) for code in report["patient_codes"]) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"output={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
