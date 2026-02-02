from __future__ import annotations

import argparse
import json
from pathlib import Path

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


def select_cohort(
    *,
    domains: list[str],
    date_from: str,
    date_to: str,
    limit: int,
    mode: str,
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

    if not domains:
        final_codes: list[int] = []
    elif mode == "union":
        merged = set().union(*(set(domain_codes[d]) for d in domains))
        final_codes = sorted(merged)[:limit]
    else:
        merged = set(domain_codes[domains[0]])
        for domain in domains[1:]:
            merged &= set(domain_codes[domain])
        final_codes = sorted(merged)[:limit]

    return {
        "domains": domains,
        "mode": mode,
        "date_from": date_from,
        "date_to": date_to,
        "limit": limit,
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
    parser.add_argument("--output", required=True, help="Path to output CSV file.")
    args = parser.parse_args()

    domains = _parse_domains_csv(args.domains)
    report = select_cohort(
        domains=domains,
        date_from=args.date_from,
        date_to=args.date_to,
        limit=args.limit,
        mode=args.mode,
    )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(",".join(str(code) for code in report["patient_codes"]) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"output={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
