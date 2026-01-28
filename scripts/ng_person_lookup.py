#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


def _ensure_app_importable() -> None:
    root = Path(__file__).resolve().parents[1]
    candidate_roots = [
        root / "backend",
        root,
        Path("/app"),
    ]
    for base in candidate_roots:
        if (base / "app").is_dir():
            sys.path.insert(0, str(base))
            return
    sys.path.insert(0, str(root))


_ensure_app_importable()

from sqlalchemy import text  # noqa: E402

from app.db.session import engine  # noqa: E402


@dataclass
class LookupRow:
    legacy_patient_code: str
    surname: str
    forenames: str
    dob: str
    postcode: str
    phone_last6: str


def _normalize_postcode(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+", "", value).upper()


def _postcode_outward(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip().upper()
    if not text:
        return None
    if " " in text:
        return text.split()[0]
    return text


def _phone_digits(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D+", "", value)
    return digits if digits else None


def _phone_last6(value: str | None) -> str | None:
    digits = _phone_digits(value)
    if not digits or len(digits) < 6:
        return None
    return digits[-6:]


def _pg_query(sql: str, params: dict[str, object]) -> list[dict[str, object]]:
    with engine.connect() as conn:
        result = conn.execute(text(sql), params)
        return [dict(row._mapping) for row in result.fetchall()]


def _rank_candidates(
    candidates: list[dict[str, object]],
    surname: str,
    dob: str | None,
    postcode: str | None,
    phone_last6: str | None,
) -> list[dict[str, object]]:
    surname_lower = surname.lower()
    postcode_full = _normalize_postcode(postcode) if postcode else None
    postcode_outward = _postcode_outward(postcode) if postcode else None
    ranked: list[dict[str, object]] = []
    for row in candidates:
        row_postcode = _normalize_postcode(str(row.get("postcode") or "")) or None
        row_outward = _postcode_outward(str(row.get("postcode") or "")) or None
        row_phone_last6 = _phone_last6(str(row.get("phone") or ""))
        row_dob = str(row.get("date_of_birth") or "")
        score = 0
        if row.get("last_name") and str(row.get("last_name")).lower() == surname_lower:
            if dob and row_dob == dob:
                score = 4
            elif postcode_full and row_postcode == postcode_full:
                score = 3
            elif postcode_outward and row_outward == postcode_outward:
                score = 2
            elif phone_last6 and row_phone_last6 == phone_last6:
                score = 1
        row["match_score"] = score
        ranked.append(row)
    ranked.sort(key=lambda r: (r.get("match_score", 0), r.get("last_name") or ""), reverse=True)
    return ranked


def _query_candidates(surname: str, limit: int) -> list[dict[str, object]]:
    sql = (
        "SELECT id, legacy_source, legacy_id, first_name, last_name, date_of_birth, "
        "postcode, phone, email "
        "FROM patients WHERE LOWER(last_name) = LOWER(:surname) "
        "ORDER BY id LIMIT :limit"
    )
    return _pg_query(sql, {"surname": surname, "limit": limit})


def _render_table(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "_No candidates found._\n"
    lines = [
        "| patient_id | legacy_source | legacy_id | name | dob | postcode | phone | email | score |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        name = " ".join(
            [str(row.get("first_name") or "").strip(), str(row.get("last_name") or "").strip()]
        ).strip() or "-"
        lines.append(
            "| {pid} | {ls} | {lid} | {name} | {dob} | {pc} | {phone} | {email} | {score} |".format(
                pid=row.get("id"),
                ls=row.get("legacy_source") or "-",
                lid=row.get("legacy_id") or "-",
                name=name,
                dob=row.get("date_of_birth") or "-",
                pc=row.get("postcode") or "-",
                phone=row.get("phone") or "-",
                email=row.get("email") or "-",
                score=row.get("match_score") or 0,
            )
        )
    return "\n".join(lines) + "\n"


def _parse_worklog(path: Path) -> list[LookupRow]:
    text = path.read_text(encoding="utf-8", errors="replace")
    rows: list[LookupRow] = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        if line.strip().startswith("| ---"):
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(parts) < 14:
            continue
        legacy_code = parts[0]
        surname = parts[1]
        forenames = parts[2]
        dob = parts[3]
        postcode = parts[4]
        phone_last6 = parts[7]
        ng_person = parts[8]
        ng_patient = parts[9]
        if not legacy_code or not surname:
            continue
        if ng_person or ng_patient:
            continue
        rows.append(
            LookupRow(
                legacy_patient_code=legacy_code,
                surname=surname,
                forenames=forenames,
                dob=dob,
                postcode=postcode,
                phone_last6=phone_last6,
            )
        )
    return rows


def _run_lookup(
    surname: str,
    dob: str | None,
    postcode: str | None,
    phone: str | None,
    limit: int,
) -> list[dict[str, object]]:
    candidates = _query_candidates(surname, limit)
    return _rank_candidates(
        candidates,
        surname=surname,
        dob=dob,
        postcode=postcode,
        phone_last6=_phone_last6(phone) if phone else None,
    )


def _print_lookup(
    heading: str,
    surname: str,
    dob: str | None,
    postcode: str | None,
    phone: str | None,
    limit: int,
) -> None:
    rows = _run_lookup(surname, dob, postcode, phone, limit)
    print(heading)
    print(f"- surname: {surname}")
    if dob:
        print(f"- dob: {dob}")
    if postcode:
        print(f"- postcode: {postcode}")
    if phone:
        print(f"- phone_last6: {_phone_last6(phone)}")
    print(_render_table(rows).rstrip())
    print("")


def main() -> int:
    parser = argparse.ArgumentParser(description="Lookup NG patient candidates (read-only).")
    parser.add_argument("--surname", help="Surname (required unless using --from-worklog).")
    parser.add_argument("--dob", help="DOB YYYY-MM-DD.")
    parser.add_argument("--postcode", help="Full or outward postcode.")
    parser.add_argument("--phone", help="Phone number (any format).")
    parser.add_argument("--limit", type=int, default=10, help="Limit candidates (default 10).")
    parser.add_argument("--from-worklog", help="Path to worklog markdown.")
    args = parser.parse_args()

    if args.from_worklog:
        path = Path(args.from_worklog)
        if not path.exists():
            raise FileNotFoundError(f"Worklog not found: {path}")
        rows = _parse_worklog(path)
        if not rows:
            print("No worklog rows ready for lookup.")
            return 0
        for row in rows:
            heading = f"### legacy_patient_code {row.legacy_patient_code}"
            _print_lookup(
                heading=heading,
                surname=row.surname,
                dob=row.dob or None,
                postcode=row.postcode or None,
                phone=row.phone_last6 or None,
                limit=args.limit,
            )
        return 0

    if not args.surname:
        raise SystemExit("--surname is required unless --from-worklog is used.")

    _print_lookup(
        heading="### lookup",
        surname=args.surname,
        dob=args.dob,
        postcode=args.postcode,
        phone=args.phone,
        limit=args.limit,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
