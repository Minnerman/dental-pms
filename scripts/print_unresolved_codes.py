#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def parse_worklog(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    codes: list[str] = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        if line.strip().startswith("| ---"):
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(parts) < 14:
            continue
        legacy_code = parts[0]
        r4_surname = parts[1]
        r4_dob = parts[3]
        r4_postcode = parts[4]
        ng_person = parts[8]
        if not legacy_code:
            continue
        if ng_person:
            continue
        if r4_surname or r4_dob or r4_postcode or legacy_code:
            codes.append(legacy_code)
    return codes


def main() -> int:
    parser = argparse.ArgumentParser(description="Print unresolved legacy codes from worklog.")
    parser.add_argument(
        "--worklog",
        default="docs/r4/R4_MANUAL_MAPPING_WORKLOG_2026-01-28.md",
        help="Path to worklog markdown.",
    )
    args = parser.parse_args()
    path = Path(args.worklog)
    if not path.exists():
        raise FileNotFoundError(f"Worklog not found: {path}")
    codes = parse_worklog(path)
    print("\n".join(codes))
    print(f"\ncount={len(codes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
