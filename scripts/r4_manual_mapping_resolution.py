#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable


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
from app.services.r4_import.sqlserver_source import (  # noqa: E402
    R4SqlServerConfig,
    R4SqlServerSource,
)


CODE_RE = re.compile(r"^###\s+legacy_patient_code\s+(\d+)\s*$", re.MULTILINE)
UNRESOLVED_RE = re.compile(r"^###\s+legacy_patient_code\s+(\d+)\s*$", re.MULTILINE)

ADDRESS_STOPWORDS = {
    "ROAD",
    "RD",
    "STREET",
    "ST",
    "AVENUE",
    "AVE",
    "FLAT",
    "APARTMENT",
    "HOUSE",
    "BUILDING",
    "THE",
    "OF",
    "LANE",
    "LN",
    "DRIVE",
    "DR",
    "COURT",
    "CT",
    "WAY",
    "PLACE",
    "PL",
    "CLOSE",
    "CL",
    "TERRACE",
    "TER",
}


@dataclass
class Candidate:
    patient_id: int
    legacy_source: str | None
    legacy_id: str | None
    first_name: str | None
    last_name: str | None
    date_of_birth: date | None
    postcode: str | None
    phone: str | None
    email: str | None
    patient_category: str | None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    match_reasons: set[str] = field(default_factory=set)

    def postcode_outward(self) -> str | None:
        return _postcode_outward(self.postcode)

    def phone_digits(self) -> str | None:
        return _phone_digits(self.phone)

    def phone_last6_set(self) -> set[str]:
        digits = self.phone_digits()
        if not digits or len(digits) < 6:
            return set()
        return {digits[-6:]}


@dataclass
class Resolution:
    code: int
    r4_patient: dict[str, Any] | None
    r4_appt_range: dict[str, Any] | None
    existing_mapping: int | None
    candidates: list[Candidate]
    proposed_patient_id: int | None
    confidence: str | None
    rationale: str | None
    pass2_candidates: dict[str, list[Candidate]] = field(default_factory=dict)


def _log(message: str, verbose: bool) -> None:
    if verbose:
        print(message)


def parse_codes(path: Path) -> list[int]:
    text_content = path.read_text(encoding="utf-8")
    codes: list[int] = []
    seen: set[int] = set()
    for match in CODE_RE.finditer(text_content):
        code = int(match.group(1))
        if code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


def parse_unresolved_codes(path: Path) -> list[int]:
    text_content = path.read_text(encoding="utf-8")
    sections = UNRESOLVED_RE.split(text_content)
    # split yields: [preface, code1, section1, code2, section2, ...]
    codes: list[int] = []
    for idx in range(1, len(sections), 2):
        code = int(sections[idx])
        body = sections[idx + 1] if idx + 1 < len(sections) else ""
        if "UNRESOLVED" in body or "none" in body.lower():
            codes.append(code)
    return codes


def _format_dt(value: Any | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _first_nonempty(value: Any | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _normalize_postcode(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+", "", value).upper()


def _postcode_outward(value: str | None) -> str | None:
    if not value:
        return None
    compact = value.strip().upper()
    if not compact:
        return None
    if " " in compact:
        return compact.split()[0]
    return compact


def _phone_digits(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D+", "", value)
    return digits if digits else None


def _phone_last6_set(*values: str | None) -> set[str]:
    last6: set[str] = set()
    for value in values:
        digits = _phone_digits(value)
        if digits and len(digits) >= 6:
            last6.add(digits[-6:])
    return last6


def _address_tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    cleaned = re.sub(r"[^A-Z0-9]", " ", value.upper())
    tokens = {t for t in cleaned.split() if t and t not in ADDRESS_STOPWORDS}
    return {t for t in tokens if len(t) >= 3 and not t.isdigit()}


def build_sqlserver_source() -> R4SqlServerSource:
    config = R4SqlServerConfig.from_env()
    config.require_enabled()
    return R4SqlServerSource(config)


def _sqlserver_patient_details(source: R4SqlServerSource, code: int) -> dict[str, Any] | None:
    patient_code_col = source._require_column("Patients", ["PatientCode"])
    first_name_col = source._pick_column("Patients", ["FirstName", "Forename"])
    last_name_col = source._pick_column("Patients", ["LastName", "Surname"])
    dob_col = source._pick_column("Patients", ["DOB", "DateOfBirth", "BirthDate"])
    title_col = source._pick_column("Patients", ["Title"])
    phone_col = source._pick_column(
        "Patients",
        ["Phone", "Telephone", "Tel", "HomePhone", "PhoneNumber"],
    )
    mobile_col = source._pick_column("Patients", ["MobileNo", "Mobile", "MobileNumber"])
    work_phone_col = source._pick_column(
        "Patients",
        ["WorkPhone", "WorkTelephone", "WorkTel", "BusinessPhone"],
    )
    email_col = source._pick_column("Patients", ["EMail", "Email", "EmailAddress"])
    postcode_col = source._pick_column(
        "Patients",
        ["Postcode", "PostCode", "PostalCode", "Zip", "ZipCode"],
    )
    address1_col = source._pick_column(
        "Patients",
        ["Address1", "AddressLine1", "AddressLine_1", "AddressLineOne", "Address"],
    )
    address2_col = source._pick_column(
        "Patients",
        ["Address2", "AddressLine2", "AddressLine_2"],
    )
    address3_col = source._pick_column(
        "Patients",
        ["Address3", "AddressLine3", "AddressLine_3"],
    )
    town_col = source._pick_column("Patients", ["Town", "City", "District", "Locality"])
    county_col = source._pick_column("Patients", ["County", "State", "Region"])
    nhs_col = source._pick_column(
        "Patients",
        ["NHSNumber", "NHSNo", "NHSNo.", "NHS_Number", "NHS"],
    )
    chart_col = source._pick_column(
        "Patients",
        ["ChartNo", "ChartNumber", "ChartNo.", "Chart", "ChartNum"],
    )
    external_id_col = source._pick_column(
        "Patients",
        ["ExternalID", "ExternalId", "ExternalRef", "ExternalRefId"],
    )

    select_cols = [f"{patient_code_col} AS patient_code"]
    if first_name_col:
        select_cols.append(f"{first_name_col} AS first_name")
    if last_name_col:
        select_cols.append(f"{last_name_col} AS last_name")
    if dob_col:
        select_cols.append(f"{dob_col} AS date_of_birth")
    if title_col:
        select_cols.append(f"{title_col} AS title")
    if phone_col:
        select_cols.append(f"{phone_col} AS phone")
    if mobile_col:
        select_cols.append(f"{mobile_col} AS mobile")
    if work_phone_col:
        select_cols.append(f"{work_phone_col} AS work_phone")
    if email_col:
        select_cols.append(f"{email_col} AS email")
    if postcode_col:
        select_cols.append(f"{postcode_col} AS postcode")
    if address1_col:
        select_cols.append(f"{address1_col} AS address_line1")
    if address2_col:
        select_cols.append(f"{address2_col} AS address_line2")
    if address3_col:
        select_cols.append(f"{address3_col} AS address_line3")
    if town_col:
        select_cols.append(f"{town_col} AS town")
    if county_col:
        select_cols.append(f"{county_col} AS county")
    if nhs_col:
        select_cols.append(f"{nhs_col} AS nhs_number")
    if chart_col:
        select_cols.append(f"{chart_col} AS chart_number")
    if external_id_col:
        select_cols.append(f"{external_id_col} AS external_id")

    sql = (
        f"SELECT {', '.join(select_cols)} FROM dbo.Patients WITH (NOLOCK) "
        f"WHERE {patient_code_col} = ?"
    )
    rows = source._query(sql, [code])
    if not rows:
        return None
    row = rows[0]
    row["date_of_birth"] = _format_dt(row.get("date_of_birth"))
    row["phone_digits"] = _phone_digits(row.get("phone"))
    row["mobile_digits"] = _phone_digits(row.get("mobile"))
    row["work_phone_digits"] = _phone_digits(row.get("work_phone"))
    row["phone_last6"] = sorted(
        _phone_last6_set(row.get("phone"), row.get("mobile"), row.get("work_phone"))
    )
    row["postcode_outward"] = _postcode_outward(row.get("postcode"))
    address_bits = [
        row.get("address_line1"),
        row.get("address_line2"),
        row.get("address_line3"),
        row.get("town"),
        row.get("county"),
    ]
    row["address_tokens"] = sorted(
        _address_tokens(" ".join([bit for bit in address_bits if bit]))
    )
    return row


def _sqlserver_appt_range(source: R4SqlServerSource, code: int) -> dict[str, Any] | None:
    patient_col = source._require_column("Appts", ["PatientCode"])
    date_col = source._pick_column(
        "Appts",
        ["Date", "ApptDate", "Start", "StartTime", "StartDateTime", "AppointmentDate"],
    )
    if not date_col:
        return None
    sql = (
        f"SELECT MIN({date_col}) AS date_min, MAX({date_col}) AS date_max "
        f"FROM dbo.Appts WITH (NOLOCK) WHERE {patient_col} = ?"
    )
    rows = source._query(sql, [code])
    if not rows:
        return None
    row = rows[0]
    return {
        "date_min": _format_dt(row.get("date_min")),
        "date_max": _format_dt(row.get("date_max")),
    }


def _pg_query(sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        result = conn.execute(text(sql), params)
        return [dict(row._mapping) for row in result.fetchall()]


def _existing_mapping(code: int) -> int | None:
    rows = _pg_query(
        "SELECT patient_id FROM r4_patient_mappings "
        "WHERE legacy_source = 'r4' AND legacy_patient_code = :code",
        {"code": code},
    )
    if not rows:
        return None
    return int(rows[0]["patient_id"])


def _fetch_patient_by_id(patient_id: int) -> Candidate | None:
    rows = _pg_query(
        "SELECT id, legacy_source, legacy_id, first_name, last_name, date_of_birth, "
        "postcode, phone, email, patient_category "
        "FROM patients WHERE id = :pid",
        {"pid": patient_id},
    )
    if not rows:
        return None
    row = rows[0]
    return Candidate(
        patient_id=row["id"],
        legacy_source=row.get("legacy_source"),
        legacy_id=row.get("legacy_id"),
        first_name=row.get("first_name"),
        last_name=row.get("last_name"),
        date_of_birth=row.get("date_of_birth"),
        postcode=row.get("postcode"),
        phone=row.get("phone"),
        email=row.get("email"),
        patient_category=row.get("patient_category"),
    )


def _candidate_rows_from_query(sql: str, params: dict[str, Any], reason: str) -> list[Candidate]:
    rows = _pg_query(sql, params)
    candidates: list[Candidate] = []
    for row in rows:
        candidate = Candidate(
            patient_id=row["id"],
            legacy_source=row.get("legacy_source"),
            legacy_id=row.get("legacy_id"),
            first_name=row.get("first_name"),
            last_name=row.get("last_name"),
            date_of_birth=row.get("date_of_birth"),
            postcode=row.get("postcode"),
            phone=row.get("phone"),
            email=row.get("email"),
            patient_category=row.get("patient_category"),
            address_line1=row.get("address_line1"),
            address_line2=row.get("address_line2"),
            city=row.get("city"),
            match_reasons={reason},
        )
        candidates.append(candidate)
    return candidates


def _ng_candidates(r4_patient: dict[str, Any] | None, code: int) -> list[Candidate]:
    candidates_by_id: dict[int, Candidate] = {}

    legacy_sql = (
        "SELECT id, legacy_source, legacy_id, first_name, last_name, date_of_birth, "
        "postcode, phone, email, patient_category, address_line1, address_line2, city "
        "FROM patients WHERE legacy_id = :code"
    )
    for candidate in _candidate_rows_from_query(legacy_sql, {"code": str(code)}, "legacy_id"):
        candidates_by_id[candidate.patient_id] = candidate

    last_name = _first_nonempty(r4_patient.get("last_name") if r4_patient else None)
    dob = r4_patient.get("date_of_birth") if r4_patient else None
    postcode = _normalize_postcode(_first_nonempty(r4_patient.get("postcode") if r4_patient else None))

    if last_name and dob:
        name_dob_sql = (
            "SELECT id, legacy_source, legacy_id, first_name, last_name, date_of_birth, "
            "postcode, phone, email, patient_category, address_line1, address_line2, city "
            "FROM patients WHERE LOWER(last_name) = LOWER(:last_name) AND date_of_birth = :dob"
        )
        for candidate in _candidate_rows_from_query(
            name_dob_sql,
            {"last_name": last_name, "dob": dob},
            "surname_dob",
        ):
            existing = candidates_by_id.get(candidate.patient_id)
            if existing:
                existing.match_reasons.add("surname_dob")
            else:
                candidates_by_id[candidate.patient_id] = candidate

    if last_name and postcode:
        surname_postcode_sql = (
            "SELECT id, legacy_source, legacy_id, first_name, last_name, date_of_birth, "
            "postcode, phone, email, patient_category, address_line1, address_line2, city "
            "FROM patients WHERE LOWER(last_name) = LOWER(:last_name) "
            "AND UPPER(REPLACE(COALESCE(postcode, ''), ' ', '')) = :postcode"
        )
        for candidate in _candidate_rows_from_query(
            surname_postcode_sql,
            {"last_name": last_name, "postcode": postcode},
            "surname_postcode",
        ):
            existing = candidates_by_id.get(candidate.patient_id)
            if existing:
                existing.match_reasons.add("surname_postcode")
            else:
                candidates_by_id[candidate.patient_id] = candidate

    return list(candidates_by_id.values())


def _ng_candidates_pass2(r4_patient: dict[str, Any] | None) -> dict[str, list[Candidate]]:
    buckets: dict[str, list[Candidate]] = {"rule_a": [], "rule_b": [], "rule_c": []}
    if not r4_patient:
        return buckets

    last_name = _first_nonempty(r4_patient.get("last_name"))
    if not last_name:
        return buckets

    phone_last6 = set(r4_patient.get("phone_last6") or [])
    postcode_outward = r4_patient.get("postcode_outward")
    dob = r4_patient.get("date_of_birth")
    address_tokens = set(r4_patient.get("address_tokens") or [])

    base_sql = (
        "SELECT id, legacy_source, legacy_id, first_name, last_name, date_of_birth, "
        "postcode, phone, email, patient_category, address_line1, address_line2, city "
        "FROM patients WHERE LOWER(last_name) = LOWER(:last_name)"
    )
    rows = _pg_query(base_sql, {"last_name": last_name})
    candidates: list[Candidate] = []
    for row in rows:
        candidates.append(
            Candidate(
                patient_id=row["id"],
                legacy_source=row.get("legacy_source"),
                legacy_id=row.get("legacy_id"),
                first_name=row.get("first_name"),
                last_name=row.get("last_name"),
                date_of_birth=row.get("date_of_birth"),
                postcode=row.get("postcode"),
                phone=row.get("phone"),
                email=row.get("email"),
                patient_category=row.get("patient_category"),
                address_line1=row.get("address_line1"),
                address_line2=row.get("address_line2"),
                city=row.get("city"),
            )
        )

    # Rule A: surname + outward postcode; require DOB match OR phone last6 match to propose.
    if postcode_outward:
        for cand in candidates:
            if cand.postcode_outward() == postcode_outward:
                cand.match_reasons.add("surname_postcode_outward")
                buckets["rule_a"].append(cand)

    # Rule B: surname + phone last6; require DOB match OR outward postcode match to propose.
    if phone_last6:
        for cand in candidates:
            cand_last6 = cand.phone_last6_set()
            if cand_last6 and cand_last6.intersection(phone_last6):
                cand.match_reasons.add("surname_phone_last6")
                buckets["rule_b"].append(cand)

    # Rule C: address token overlap (review-only).
    if address_tokens:
        for cand in candidates:
            cand_address = " ".join(
                [part for part in [cand.address_line1, cand.address_line2, cand.city] if part]
            )
            tokens = _address_tokens(cand_address)
            overlap = address_tokens.intersection(tokens)
            if len(overlap) >= 2:
                cand.match_reasons.add(f"address_overlap({len(overlap)})")
                buckets["rule_c"].append(cand)

    return buckets


def resolve_code(
    source: R4SqlServerSource,
    code: int,
    verbose: bool,
    pass2: bool,
) -> Resolution:
    r4_patient = _sqlserver_patient_details(source, code)
    r4_appt_range = _sqlserver_appt_range(source, code)
    existing_mapping = _existing_mapping(code)

    candidates = _ng_candidates(r4_patient, code)
    pass2_candidates: dict[str, list[Candidate]] = {}
    if pass2:
        pass2_candidates = _ng_candidates_pass2(r4_patient)
    proposed_patient_id: int | None = None
    confidence: str | None = None
    rationale: str | None = None

    if existing_mapping is not None:
        proposed_patient_id = existing_mapping
        confidence = "existing_mapping"
        rationale = "Existing r4_patient_mappings row"
    elif len(candidates) == 1:
        proposed_patient_id = candidates[0].patient_id
        if "legacy_id" in candidates[0].match_reasons:
            confidence = "high"
            rationale = "Matched legacy_id"
        elif "surname_dob" in candidates[0].match_reasons:
            confidence = "medium"
            rationale = "Matched surname + DOB"
        else:
            confidence = "low"
            rationale = "Matched surname + postcode"
    elif len(candidates) > 1:
        confidence = "ambiguous"
        rationale = "Multiple candidate matches"
    else:
        confidence = "none"
        rationale = "No candidate matches"

    if pass2 and proposed_patient_id is None:
        rule_a = pass2_candidates.get("rule_a", [])
        rule_b = pass2_candidates.get("rule_b", [])
        rule_c = pass2_candidates.get("rule_c", [])

        # Rule A: surname + outward postcode, require DOB or phone last6 match.
        if len(rule_a) == 1 and r4_patient:
            cand = rule_a[0]
            dob_match = r4_patient.get("date_of_birth") == cand.date_of_birth
            phone_match = bool(
                set(r4_patient.get("phone_last6") or []).intersection(cand.phone_last6_set())
            )
            if dob_match or phone_match:
                proposed_patient_id = cand.patient_id
                confidence = "high"
                rationale = "Rule A: surname + postcode outward + (DOB or phone last6)"

        # Rule B: surname + phone last6, require DOB or postcode outward match.
        if proposed_patient_id is None and len(rule_b) == 1 and r4_patient:
            cand = rule_b[0]
            dob_match = r4_patient.get("date_of_birth") == cand.date_of_birth
            postcode_match = r4_patient.get("postcode_outward") == cand.postcode_outward()
            if dob_match or postcode_match:
                proposed_patient_id = cand.patient_id
                confidence = "high"
                rationale = "Rule B: surname + phone last6 + (DOB or postcode outward)"

        if proposed_patient_id is None and (rule_a or rule_b or rule_c):
            confidence = "ambiguous" if (rule_a or rule_b) else "none"
            rationale = "Pass2 candidates require manual review"

    _log(
        f"code={code} candidates={len(candidates)} proposed={proposed_patient_id}",
        verbose,
    )

    return Resolution(
        code=code,
        r4_patient=r4_patient,
        r4_appt_range=r4_appt_range,
        existing_mapping=existing_mapping,
        candidates=sorted(candidates, key=lambda c: c.patient_id),
        pass2_candidates=pass2_candidates,
        proposed_patient_id=proposed_patient_id,
        confidence=confidence,
        rationale=rationale,
    )


def _render_candidate_table(candidates: list[Candidate]) -> str:
    if not candidates:
        return "_No candidates found._\n"
    lines = [
        "| patient_id | legacy_source | legacy_id | name | dob | postcode | phone | email | category | match_reason |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for cand in candidates:
        name = " ".join(filter(None, [cand.first_name, cand.last_name])) or "-"
        reasons = ", ".join(sorted(cand.match_reasons)) if cand.match_reasons else "-"
        lines.append(
            "| {pid} | {ls} | {lid} | {name} | {dob} | {pc} | {phone} | {email} | {cat} | {reason} |".format(
                pid=cand.patient_id,
                ls=cand.legacy_source or "-",
                lid=cand.legacy_id or "-",
                name=name,
                dob=cand.date_of_birth or "-",
                pc=cand.postcode or "-",
                phone=cand.phone or "-",
                email=cand.email or "-",
                cat=cand.patient_category or "-",
                reason=reasons,
            )
        )
    return "\n".join(lines) + "\n"


def _render_r4_details(r4_patient: dict[str, Any] | None, r4_appt_range: dict[str, Any] | None) -> str:
    if not r4_patient:
        return "_No matching R4 patient record found._\n"
    parts = []
    parts.append(f"- PatientCode: {r4_patient.get('patient_code')}")
    name = " ".join(
        filter(None, [r4_patient.get("first_name"), r4_patient.get("last_name")])
    )
    if name:
        parts.append(f"- Name: {name}")
    if r4_patient.get("date_of_birth"):
        parts.append(f"- DOB: {r4_patient.get('date_of_birth')}")
    if r4_patient.get("title"):
        parts.append(f"- Title: {r4_patient.get('title')}")
    if r4_patient.get("phone"):
        parts.append(f"- Phone: {r4_patient.get('phone')}")
    if r4_patient.get("mobile"):
        parts.append(f"- Mobile: {r4_patient.get('mobile')}")
    if r4_patient.get("work_phone"):
        parts.append(f"- Work phone: {r4_patient.get('work_phone')}")
    if r4_patient.get("email"):
        parts.append(f"- Email: {r4_patient.get('email')}")
    if r4_patient.get("postcode"):
        parts.append(
            f"- Postcode: {r4_patient.get('postcode')} (outward: {r4_patient.get('postcode_outward')})"
        )
    if r4_patient.get("phone_last6"):
        parts.append(f"- Phone last6: {', '.join(r4_patient.get('phone_last6'))}")
    if r4_patient.get("nhs_number"):
        parts.append(f"- NHS number: {r4_patient.get('nhs_number')}")
    if r4_patient.get("chart_number"):
        parts.append(f"- Chart number: {r4_patient.get('chart_number')}")
    if r4_patient.get("external_id"):
        parts.append(f"- External ID: {r4_patient.get('external_id')}")
    address_bits = [
        r4_patient.get("address_line1"),
        r4_patient.get("address_line2"),
        r4_patient.get("address_line3"),
        r4_patient.get("town"),
        r4_patient.get("county"),
    ]
    address = ", ".join([bit for bit in address_bits if bit])
    if address:
        parts.append(f"- Address: {address}")
    if r4_appt_range:
        parts.append(
            f"- Appt date range: {r4_appt_range.get('date_min')} → {r4_appt_range.get('date_max')}"
        )
    return "\n".join(parts) + "\n"


def _render_proposed(resolution: Resolution) -> str:
    if resolution.existing_mapping is not None:
        return f"- Proposed: patient_id {resolution.proposed_patient_id} (existing mapping)\n"
    if resolution.proposed_patient_id is not None and resolution.confidence not in {"ambiguous", "none"}:
        return (
            f"- Proposed: patient_id {resolution.proposed_patient_id} "
            f"(confidence: {resolution.confidence}; {resolution.rationale})\n"
        )
    return f"- UNRESOLVED ({resolution.rationale})\n"


def generate_report(resolutions: list[Resolution], out_path: Path, pass2: bool) -> str:
    total = len(resolutions)
    resolved = len(
        [
            r
            for r in resolutions
            if r.proposed_patient_id is not None and r.confidence not in {"ambiguous", "none"}
        ]
    )
    ambiguous = len([r for r in resolutions if r.confidence == "ambiguous"])
    no_match = len([r for r in resolutions if r.confidence == "none"])

    title = (
        "# R4 manual mapping resolution report (2026-01-28 PASS2)"
        if pass2
        else "# R4 manual mapping resolution report (2026-01-28)"
    )
    lines = [
        title,
        "",
        "How to review:",
        f"- `rg -n \"legacy_patient_code 1016090\" {out_path}`",
        f"- `less +/legacy_patient_code\\ 1016090 {out_path}`",
        "",
        "Summary:",
        f"- total codes: {total}",
        f"- resolved (single confident match or existing mapping): {resolved}",
        f"- ambiguous (multiple candidates): {ambiguous}",
        f"- no match: {no_match}",
        "",
    ]

    for resolution in resolutions:
        lines.extend(
            [
                f"### legacy_patient_code {resolution.code}",
                "",
                "R4 details:",
                _render_r4_details(resolution.r4_patient, resolution.r4_appt_range).rstrip(),
                "",
                "NG candidates (baseline):",
                _render_candidate_table(resolution.candidates).rstrip(),
            ]
        )
        if pass2:
            lines.extend(
                [
                    "",
                    "NG candidates (Rule A: surname + postcode outward):",
                    _render_candidate_table(resolution.pass2_candidates.get("rule_a", [])).rstrip(),
                    "",
                    "NG candidates (Rule B: surname + phone last6):",
                    _render_candidate_table(resolution.pass2_candidates.get("rule_b", [])).rstrip(),
                    "",
                    "NG candidates (Rule C: address token overlap, review only):",
                    _render_candidate_table(resolution.pass2_candidates.get("rule_c", [])).rstrip(),
                ]
            )
        lines.extend(
            [
                "",
                "Proposed mapping:",
                _render_proposed(resolution).rstrip(),
                "",
            ]
        )

    content = "\n".join(lines).rstrip() + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return content


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve R4 manual mapping candidates against R4 SQL Server and NG Postgres."
    )
    parser.add_argument(
        "--candidates",
        default="docs/r4/R4_MANUAL_MAPPING_CANDIDATES_2026-01-28.md",
        help="Path to candidates markdown.",
    )
    parser.add_argument(
        "--out",
        default="docs/r4/R4_MANUAL_MAPPING_RESOLUTION_2026-01-28.md",
        help="Output markdown path.",
    )
    parser.add_argument(
        "--codes",
        default="",
        help="Optional comma-separated legacy patient codes (overrides candidates file).",
    )
    parser.add_argument(
        "--only-unresolved",
        action="store_true",
        help="Use unresolved codes from the previous report instead of candidates file.",
    )
    parser.add_argument(
        "--previous-report",
        default="docs/r4/R4_MANUAL_MAPPING_RESOLUTION_2026-01-28.md",
        help="Path to previous resolution report for --only-unresolved.",
    )
    parser.add_argument(
        "--pass2",
        action="store_true",
        help="Enable pass2 matching rules (postcode outward/phone/address).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Run without writing output.")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging.")
    args = parser.parse_args()

    candidates_path = Path(args.candidates)
    if args.codes:
        codes = []
        for part in args.codes.split(","):
            part = part.strip()
            if not part:
                continue
            codes.append(int(part))
    elif args.only_unresolved:
        previous_path = Path(args.previous_report)
        if not previous_path.exists():
            raise FileNotFoundError(f"Previous report not found: {previous_path}")
        codes = parse_unresolved_codes(previous_path)
    else:
        if not candidates_path.exists():
            raise FileNotFoundError(f"Candidates file not found: {candidates_path}")
        codes = parse_codes(candidates_path)

    if not codes:
        raise RuntimeError("No legacy_patient_code values found.")

    _log(f"codes extracted: {len(codes)}", args.verbose)

    source = build_sqlserver_source()

    pass2 = args.pass2 or args.only_unresolved
    resolutions: list[Resolution] = []
    for code in codes:
        resolutions.append(resolve_code(source, code, args.verbose, pass2))

    resolved = [
        r
        for r in resolutions
        if r.proposed_patient_id is not None and r.confidence not in {"ambiguous", "none"}
    ]
    ambiguous = [r for r in resolutions if r.confidence == "ambiguous"]
    no_match = [r for r in resolutions if r.confidence == "none"]

    print(f"total={len(resolutions)} resolved={len(resolved)} ambiguous={len(ambiguous)} none={len(no_match)}")

    if resolved:
        sample = random.sample(resolved, k=min(5, len(resolved)))
        print("sample_resolved:")
        for item in sample:
            r4_name = ""
            if item.r4_patient:
                r4_name = " ".join(
                    filter(None, [item.r4_patient.get("first_name"), item.r4_patient.get("last_name")])
                )
            print(
                json.dumps(
                    {
                        "legacy_patient_code": item.code,
                        "r4_name": r4_name or None,
                        "r4_dob": item.r4_patient.get("date_of_birth") if item.r4_patient else None,
                        "proposed_patient_id": item.proposed_patient_id,
                        "confidence": item.confidence,
                        "rationale": item.rationale,
                    },
                    default=str,
                )
            )

    if args.dry_run:
        return 0

    out_path = Path(args.out)
    generate_report(resolutions, out_path, pass2)
    print(f"Wrote report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
