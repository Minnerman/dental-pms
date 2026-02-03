from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.user import User
from app.services.r4_import.fixture_source import FixtureSource
from app.services.r4_import.importer import import_r4
from app.services.r4_import.appointment_importer import import_r4_appointments
from app.services.r4_import.mapping_quality import PatientMappingQualityReportBuilder
from app.services.r4_import.patient_importer import import_r4_patients
from app.services.r4_import.postgres_verify import verify_patients_window
from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource
from app.services.r4_import.r4_user_importer import import_r4_users
from app.services.r4_import.charting_importer import import_r4_charting
from app.services.r4_charting.canonical_importer import (
    import_r4_charting_canonical,
    import_r4_charting_canonical_report,
)
from app.services.r4_charting.sqlserver_extract import SqlServerChartingExtractor
from app.services.r4_import.treatment_transactions_importer import (
    import_r4_treatment_transactions,
)
from app.services.r4_import.treatment_plan_importer import (
    backfill_r4_treatment_plan_patients,
    import_r4_treatment_plans,
    import_r4_treatments,
    summarize_r4_treatment_plans,
)


def resolve_actor_id(session) -> int:
    actor_id = session.scalar(select(func.min(User.id)))
    if not actor_id:
        raise RuntimeError("No users found; cannot attribute R4 imports.")
    return int(actor_id)


def _parse_date_arg(value: str) -> date:
    return date.fromisoformat(value)


def _parse_patient_code_tokens(tokens: list[str], *, label: str) -> list[int]:
    seen: set[int] = set()
    parsed: list[int] = []
    for token in tokens:
        value = token.strip()
        if not value:
            continue
        try:
            code = int(value)
        except ValueError as exc:
            raise RuntimeError(f"Invalid patient code in {label}: {value}") from exc
        if code in seen:
            continue
        seen.add(code)
        parsed.append(code)
    if not parsed:
        raise RuntimeError(f"Invalid {label} value: no patient codes provided.")
    parsed.sort()
    return parsed


def _parse_patient_codes_csv(raw: str | None) -> list[int] | None:
    if raw is None:
        return None
    tokens = [token for token in raw.split(",")]
    for token in tokens:
        if not token.strip():
            raise RuntimeError("Invalid --patient-codes value: empty token.")
    return _parse_patient_code_tokens(tokens, label="--patient-codes")


def _parse_patient_codes_file(path: str) -> list[int]:
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Unable to read --patient-codes-file: {path}") from exc
    tokens: list[str] = []
    for line in raw.splitlines():
        content = line.split("#", 1)[0]
        if not content.strip():
            continue
        tokens.extend(content.split(","))
    return _parse_patient_code_tokens(tokens, label="--patient-codes-file")


def _parse_patient_codes_arg(
    patient_codes_csv: str | None,
    patient_codes_file: str | None,
) -> list[int] | None:
    if patient_codes_csv and patient_codes_file:
        raise RuntimeError("--patient-codes and --patient-codes-file are mutually exclusive.")
    if patient_codes_file:
        return _parse_patient_codes_file(patient_codes_file)
    return _parse_patient_codes_csv(patient_codes_csv)


_CHARTING_CANONICAL_DOMAINS = {
    "perioprobe",
    "bpe",
    "bpe_furcation",
    "patient_notes",
    "treatment_plans",
    "treatment_notes",
    "treatment_plan_items",
}


def _parse_charting_domains_arg(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    domains: list[str] = []
    seen: set[str] = set()
    for token in raw.split(","):
        domain = token.strip().lower()
        if not domain:
            raise RuntimeError("Invalid --domains value: empty token.")
        if domain not in _CHARTING_CANONICAL_DOMAINS:
            allowed = ",".join(sorted(_CHARTING_CANONICAL_DOMAINS))
            raise RuntimeError(f"Unsupported --domains value: {domain}. Allowed: {allowed}")
        if domain in seen:
            continue
        seen.add(domain)
        domains.append(domain)
    if not domains:
        raise RuntimeError("Invalid --domains value: no domains provided.")
    return domains


def _build_patients_mapping_quality(
    source,
    patients_from: int | None,
    patients_to: int | None,
    patient_codes: list[int] | None,
    limit: int | None,
) -> dict[str, object]:
    report = PatientMappingQualityReportBuilder()
    if patient_codes:
        remaining = limit
        for code in patient_codes:
            if remaining is not None and remaining <= 0:
                break
            for patient in source.stream_patients(
                patients_from=code,
                patients_to=code,
                limit=1,
            ):
                report.ingest(patient)
                if remaining is not None:
                    remaining -= 1
    else:
        for patient in source.stream_patients(
            patients_from=patients_from,
            patients_to=patients_to,
            limit=limit,
        ):
            report.ingest(patient)
    return report.finalize()


def _patient_filter_metadata(
    *,
    patients_from: int | None,
    patients_to: int | None,
    patient_codes: list[int] | None,
) -> dict[str, object]:
    if patient_codes:
        return {
            "patient_filter_mode": "codes",
            "patient_codes_count": len(patient_codes),
            "patient_codes_sample": patient_codes[:10],
        }
    if patients_from is not None or patients_to is not None:
        return {
            "patient_filter_mode": "range",
            "patients_from": patients_from,
            "patients_to": patients_to,
        }
    return {"patient_filter_mode": "none"}


def _validate_patient_filters(
    *,
    patients_from: int | None,
    patients_to: int | None,
    patient_codes: list[int] | None,
) -> None:
    if patient_codes and (patients_from is not None or patients_to is not None):
        raise RuntimeError(
            "--patient-codes/--patient-codes-file cannot be used with --patients-from/--patients-to."
        )


def _write_mapping_quality_file(path: str, payload: dict[str, object]) -> None:
    target = Path(path)
    parent = target.parent
    if parent and not parent.exists():
        raise RuntimeError(f"Mapping quality output directory does not exist: {parent}")
    data = json.dumps(payload, indent=2, sort_keys=True, default=str)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=str(parent) if parent else None,
    ) as handle:
        handle.write(data)
        handle.write("\n")
        tmp_path = handle.name
    os.replace(tmp_path, target)


def _write_stats_file(path: str, payload: dict[str, object]) -> None:
    target = Path(path)
    parent = target.parent
    if parent and not parent.exists():
        raise RuntimeError(f"Stats output directory does not exist: {parent}")
    data = json.dumps(payload, indent=2, sort_keys=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=str(parent) if parent else None,
    ) as handle:
        handle.write(data)
        handle.write("\n")
        tmp_path = handle.name
    os.replace(tmp_path, target)


def _write_report_file(path: str, payload: dict[str, object]) -> None:
    target = Path(path)
    parent = target.parent
    if parent and not parent.exists():
        raise RuntimeError(f"Report output directory does not exist: {parent}")
    data = json.dumps(payload, indent=2, sort_keys=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=str(parent) if parent else None,
    ) as handle:
        handle.write(data)
        handle.write("\n")
        tmp_path = handle.name
    os.replace(tmp_path, target)


def _effective_batch_size(entity: str, requested: int | None) -> int:
    if requested is not None:
        return requested
    if entity == "charting_canonical":
        return 100
    return 1000


def _chunk_patient_codes(codes: list[int], *, batch_size: int) -> list[list[int]]:
    if batch_size <= 0:
        raise RuntimeError("--batch-size must be a positive integer.")
    return [codes[i : i + batch_size] for i in range(0, len(codes), batch_size)]


def _patient_codes_fingerprint(codes: list[int]) -> str:
    material = ",".join(str(code) for code in codes)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _build_run_signature(
    *,
    source: str,
    entity: str,
    charting_from: date | None,
    charting_to: date | None,
    charting_domains: list[str] | None,
    limit: int | None,
    allow_unmapped_patients: bool,
    batch_size: int,
    patient_codes: list[int],
) -> dict[str, object]:
    return {
        "source": source,
        "entity": entity,
        "charting_from": charting_from.isoformat() if charting_from else None,
        "charting_to": charting_to.isoformat() if charting_to else None,
        "charting_domains": charting_domains,
        "limit": limit,
        "allow_unmapped_patients": allow_unmapped_patients,
        "batch_size": batch_size,
        "patient_codes_count": len(patient_codes),
        "patient_codes_first": patient_codes[0] if patient_codes else None,
        "patient_codes_last": patient_codes[-1] if patient_codes else None,
        "patient_codes_hash": _patient_codes_fingerprint(patient_codes),
    }


def _load_state_file(path: str) -> dict[str, object]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"Unable to read --state-file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in --state-file: {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Invalid --state-file payload: {path}")
    return payload


def _write_state_file(path: str, payload: dict[str, object]) -> None:
    _write_report_file(path, payload)


def _validate_resume_state(
    payload: dict[str, object],
    *,
    signature: dict[str, object],
) -> int:
    for key in (
        "source",
        "entity",
        "charting_from",
        "charting_to",
        "charting_domains",
        "limit",
        "allow_unmapped_patients",
        "batch_size",
        "patient_codes_count",
        "patient_codes_hash",
    ):
        expected = signature.get(key)
        got = payload.get(key)
        if expected != got:
            raise RuntimeError(
                f"--resume state mismatch for {key}: state={got!r}, current={expected!r}"
            )
    completed = payload.get("completed_batches", 0)
    if not isinstance(completed, int) or completed < 0:
        raise RuntimeError("Invalid completed_batches in --state-file.")
    return completed


def _int_value(value: object) -> int:
    return int(value) if isinstance(value, int) else 0


def _normalize_charting_stats(
    *,
    stats: dict[str, object],
    report: dict[str, object],
) -> dict[str, object]:
    dropped = report.get("dropped")
    if not isinstance(dropped, dict):
        dropped = {}
    candidates_total = _int_value(report.get("total_records"))
    candidates_total += _int_value(dropped.get("out_of_range"))
    candidates_total += _int_value(dropped.get("missing_date"))
    candidates_total += _int_value(dropped.get("duplicate_unique_key"))

    by_source = report.get("by_source")
    if not isinstance(by_source, dict):
        by_source = {}

    normalized: dict[str, object] = {
        "total": _int_value(stats.get("total")),
        "created": _int_value(stats.get("created")),
        "updated": _int_value(stats.get("updated")),
        "skipped": _int_value(stats.get("skipped")),
        "unmapped_patients": _int_value(stats.get("unmapped_patients")),
        "candidates_total": candidates_total,
        "imported_created_total": _int_value(stats.get("created")),
        "imported_updated_total": _int_value(stats.get("updated")),
        "skipped_total": _int_value(stats.get("skipped")),
        "dropped_out_of_range_total": _int_value(dropped.get("out_of_range")),
        "dropped_missing_date_total": _int_value(dropped.get("missing_date")),
        "undated_included_total": _int_value(dropped.get("undated_included")),
        "unmapped_patients_total": _int_value(stats.get("unmapped_patients")),
        "by_source_fetched": by_source,
    }
    return normalized


def _merge_by_source(
    aggregate: dict[str, dict[str, int]],
    current: dict[str, object] | None,
) -> None:
    if not isinstance(current, dict):
        return
    for source_name, payload in current.items():
        if not isinstance(payload, dict):
            continue
        fetched = _int_value(payload.get("fetched"))
        bucket = aggregate.setdefault(source_name, {"fetched": 0})
        bucket["fetched"] += fetched


def _finalize_charting_report(
    report: dict[str, object],
    *,
    source: str,
    entity: str,
    patients_from: int | None,
    patients_to: int | None,
    patient_codes: list[int] | None,
    charting_from: date | None,
    charting_to: date | None,
    charting_domains: list[str] | None,
    limit: int | None,
    mode: str,
) -> dict[str, object]:
    stats = report.get("stats") or {}
    dropped = report.get("dropped") or {}
    totals = {
        "total_records": _int_value(report.get("total_records")),
        "distinct_patients": _int_value(report.get("distinct_patients")),
        "missing_source_id": _int_value(report.get("missing_source_id")),
        "missing_patient_code": _int_value(report.get("missing_patient_code")),
        "created": _int_value(stats.get("created")),
        "updated": _int_value(stats.get("updated")),
        "skipped": _int_value(stats.get("skipped")),
        "unmapped_patients": _int_value(stats.get("unmapped_patients")),
        "candidates_total": _int_value(report.get("total_records"))
        + _int_value(dropped.get("out_of_range"))
        + _int_value(dropped.get("missing_date"))
        + _int_value(dropped.get("duplicate_unique_key")),
        "imported_created_total": _int_value(stats.get("created")),
        "imported_updated_total": _int_value(stats.get("updated")),
        "skipped_total": _int_value(stats.get("skipped")),
        "dropped_out_of_range_total": _int_value(dropped.get("out_of_range")),
        "dropped_missing_date_total": _int_value(dropped.get("missing_date")),
        "undated_included_total": _int_value(dropped.get("undated_included")),
        "unmapped_patients_total": _int_value(stats.get("unmapped_patients")),
    }
    report.update(
        {
            "mode": mode,
            "source": source,
            "entity": entity,
            "charting_from": charting_from.isoformat() if charting_from else None,
            "charting_to": charting_to.isoformat() if charting_to else None,
            "domains": charting_domains,
            "limit": limit,
            "totals": totals,
            **_patient_filter_metadata(
                patients_from=patients_from,
                patients_to=patients_to,
                patient_codes=patient_codes,
            ),
        }
    )
    return report


def _maybe_write_mapping_quality(
    path: str | None,
    mapping_quality: dict[str, object] | None,
    patients_from: int | None,
    patients_to: int | None,
    patient_codes: list[int] | None = None,
) -> None:
    if not path:
        return
    if mapping_quality is None:
        raise RuntimeError("Mapping quality output requested, but no report was generated.")
    payload = {
        "entity": "patients",
        "window": _patient_filter_metadata(
            patients_from=patients_from,
            patients_to=patients_to,
            patient_codes=patient_codes,
        ),
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "mapping_quality": mapping_quality,
    }
    _write_mapping_quality_file(path, payload)


def _maybe_write_stats(
    path: str | None,
    entity: str,
    stats: dict[str, object],
    patients_from: int | None,
    patients_to: int | None,
    patient_codes: list[int] | None = None,
    appts_from: date | None = None,
    appts_to: date | None = None,
) -> None:
    if not path:
        return
    if entity == "appointments":
        window = {
            "appts_from": appts_from.isoformat() if appts_from else None,
            "appts_to": appts_to.isoformat() if appts_to else None,
        }
    else:
        window = _patient_filter_metadata(
            patients_from=patients_from,
            patients_to=patients_to,
            patient_codes=patient_codes,
        )
    payload = {
        "entity": entity,
        "window": window,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "stats": stats,
    }
    _write_stats_file(path, payload)


def _run_charting_canonical_batched(
    *,
    session,
    source: object,
    source_name: str,
    entity: str,
    patient_codes: list[int],
    patients_from: int | None,
    patients_to: int | None,
    charting_from: date | None,
    charting_to: date | None,
    charting_domains: list[str] | None,
    limit: int | None,
    allow_unmapped_patients: bool,
    batch_size: int,
    state_file: str | None,
    resume: bool,
    stop_after_batches: int | None,
) -> tuple[dict[str, object], dict[str, object]]:
    batches = _chunk_patient_codes(patient_codes, batch_size=batch_size)
    signature = _build_run_signature(
        source=source_name,
        entity=entity,
        charting_from=charting_from,
        charting_to=charting_to,
        charting_domains=charting_domains,
        limit=limit,
        allow_unmapped_patients=allow_unmapped_patients,
        batch_size=batch_size,
        patient_codes=patient_codes,
    )

    start_batch = 0
    if resume:
        if not state_file:
            raise RuntimeError("--resume requires --state-file.")
        state_payload = _load_state_file(state_file)
        start_batch = _validate_resume_state(state_payload, signature=signature)
    elif state_file:
        state_payload = {
            **signature,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "total_batches": len(batches),
            "completed_batches": 0,
            "last_completed_patient_code": None,
        }
        _write_state_file(state_file, state_payload)

    aggregate_old = {
        "total": 0,
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "unmapped_patients": 0,
    }
    aggregate_new = {
        "candidates_total": 0,
        "imported_created_total": 0,
        "imported_updated_total": 0,
        "skipped_total": 0,
        "dropped_out_of_range_total": 0,
        "dropped_missing_date_total": 0,
        "undated_included_total": 0,
        "unmapped_patients_total": 0,
    }
    aggregate_by_source: dict[str, dict[str, int]] = {}
    aggregate_dropped: dict[str, int] = {}
    batch_reports: list[dict[str, object]] = []
    seen_patients: set[int] = set()

    completed_batches = start_batch
    for batch_index in range(start_batch, len(batches)):
        batch_codes = batches[batch_index]
        stats_obj, report = import_r4_charting_canonical_report(
            session,
            source,
            patients_from=patients_from,
            patients_to=patients_to,
            patient_codes=batch_codes,
            date_from=charting_from,
            date_to=charting_to,
            domains=charting_domains,
            limit=limit,
            dry_run=False,
            allow_unmapped_patients=allow_unmapped_patients,
        )
        stats = stats_obj.as_dict()
        normalized = _normalize_charting_stats(stats=stats, report=report)

        for key in aggregate_old:
            aggregate_old[key] += _int_value(stats.get(key))
        for key in aggregate_new:
            aggregate_new[key] += _int_value(normalized.get(key))
        _merge_by_source(aggregate_by_source, normalized.get("by_source_fetched"))

        dropped = report.get("dropped")
        if isinstance(dropped, dict):
            for key, value in dropped.items():
                if isinstance(value, int):
                    aggregate_dropped[key] = aggregate_dropped.get(key, 0) + value

        seen_patients.update(batch_codes)
        batch_reports.append(
            {
                "batch_index": batch_index,
                "patient_codes_count": len(batch_codes),
                "patient_codes_first": batch_codes[0] if batch_codes else None,
                "patient_codes_last": batch_codes[-1] if batch_codes else None,
                "stats": normalized,
            }
        )
        session.commit()
        completed_batches = batch_index + 1

        if state_file:
            state_payload = {
                **signature,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "total_batches": len(batches),
                "completed_batches": completed_batches,
                "last_completed_patient_code": batch_codes[-1] if batch_codes else None,
            }
            _write_state_file(state_file, state_payload)

        if stop_after_batches is not None and completed_batches >= stop_after_batches:
            break

    final_stats: dict[str, object] = {
        **aggregate_old,
        **aggregate_new,
        "by_source_fetched": aggregate_by_source,
        "batches_total": len(batches),
        "batches_completed": completed_batches,
    }

    final_report: dict[str, object] = {
        "total_records": aggregate_old["total"],
        "distinct_patients": len(seen_patients),
        "missing_source_id": 0,
        "missing_patient_code": 0,
        "by_source": aggregate_by_source,
        "stats": {
            "total": aggregate_old["total"],
            "created": aggregate_old["created"],
            "updated": aggregate_old["updated"],
            "skipped": aggregate_old["skipped"],
            "unmapped_patients": aggregate_old["unmapped_patients"],
        },
        "dropped": aggregate_dropped,
        "batches": batch_reports,
    }
    if completed_batches < len(batches):
        final_report["resume_incomplete"] = True
        final_report["warnings"] = [
            f"Run stopped after {completed_batches} of {len(batches)} batches."
        ]
    final_report = _finalize_charting_report(
        final_report,
        source=source_name,
        entity=entity,
        patients_from=patients_from,
        patients_to=patients_to,
        patient_codes=patient_codes,
        charting_from=charting_from,
        charting_to=charting_to,
        charting_domains=charting_domains,
        limit=limit,
        mode="apply",
    )
    return final_stats, final_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Import R4 data into the PMS.")
    parser.add_argument(
        "--source",
        default="fixtures",
        choices=("fixtures", "sqlserver"),
        help="Import source (fixtures or sqlserver).",
    )
    parser.add_argument(
        "--entity",
        default="patients_appts",
        choices=(
            "patients",
            "patients_appts",
            "appointments",
            "treatments",
            "treatment_transactions",
            "users",
            "treatment_plans",
            "treatment_plans_summary",
            "treatment_plans_backfill_patient_ids",
            "charting",
            "charting_canonical",
        ),
        help="Entity to import (default: patients_appts).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="For SQL Server source, run a read-only connectivity check and stats summary.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply SQL Server data to Postgres via the importer (explicitly gated).",
    )
    parser.add_argument(
        "--confirm",
        default="",
        help="Safety latch for apply mode (must be 'APPLY').",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit rows for dry-run samples (or apply if specified).",
    )
    parser.add_argument(
        "--date-floor",
        type=_parse_date_arg,
        default=None,
        help="Exclude dates before this floor when reporting dry-run date ranges.",
    )
    parser.add_argument(
        "--charting-from",
        dest="charting_from",
        type=_parse_date_arg,
        default=None,
        help="Filter charting rows from YYYY-MM-DD (inclusive).",
    )
    parser.add_argument(
        "--charting-to",
        dest="charting_to",
        type=_parse_date_arg,
        default=None,
        help="Filter charting rows to YYYY-MM-DD (inclusive).",
    )
    parser.add_argument(
        "--domains",
        dest="domains",
        default=None,
        help=(
            "Optional comma-separated charting canonical domains "
            "(perioprobe,bpe,bpe_furcation,patient_notes,treatment_plans,treatment_notes,treatment_plan_items)."
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Batch size for patient-scoped/bulk imports.",
    )
    parser.add_argument(
        "--sleep-ms",
        type=int,
        default=0,
        help="Optional sleep per batch in milliseconds (default: 0).",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=5000,
        help="Progress update frequency in items/plans (default: 5000).",
    )
    parser.add_argument(
        "--mapping-quality-out",
        dest="mapping_quality_out",
        default=None,
        help="Write patients mapping quality JSON to PATH (patients entity only).",
    )
    parser.add_argument(
        "--stats-out",
        dest="stats_out",
        default=None,
        help="Write final import stats JSON to PATH (apply/fixture runs).",
    )
    parser.add_argument(
        "--output-json",
        dest="output_json",
        default=None,
        help="Write charting canonical report JSON to PATH.",
    )
    parser.add_argument(
        "--run-summary-out",
        dest="run_summary_out",
        default=None,
        help="Write batch run summary JSON to PATH (charting_canonical only).",
    )
    parser.add_argument(
        "--verify-postgres",
        action="store_true",
        help="Verify patients in Postgres for a window (no SQL Server connection).",
    )
    parser.add_argument(
        "--allow-unmapped-patients",
        action="store_true",
        help="Allow charting imports for patients without mappings (default: false).",
    )
    parser.add_argument(
        "--connect-timeout-seconds",
        type=int,
        default=None,
        help="Override SQL Server connection timeout in seconds (sqlserver source only).",
    )
    parser.add_argument(
        "--patients-from",
        dest="patients_from",
        type=int,
        default=None,
        help="Filter treatment plans/items from patient code (inclusive).",
    )
    parser.add_argument(
        "--patients-to",
        dest="patients_to",
        type=int,
        default=None,
        help="Filter treatment plans/items to patient code (inclusive).",
    )
    parser.add_argument(
        "--patient-codes",
        dest="patient_codes",
        default=None,
        help="Comma-separated patient codes for exact cohort selection.",
    )
    parser.add_argument(
        "--patient-codes-file",
        dest="patient_codes_file",
        default=None,
        help="Path to CSV/newline patient code list.",
    )
    parser.add_argument(
        "--state-file",
        dest="state_file",
        default=None,
        help="State file path for batch resume progress.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from --state-file for batched imports.",
    )
    parser.add_argument(
        "--stop-after-batches",
        type=int,
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--tp-from",
        dest="tp_from",
        type=int,
        default=None,
        help="Filter treatment plans/items from TP number (inclusive).",
    )
    parser.add_argument(
        "--tp-to",
        dest="tp_to",
        type=int,
        default=None,
        help="Filter treatment plans/items to TP number (inclusive).",
    )
    parser.add_argument(
        "--appts-from",
        dest="appts_from",
        type=_parse_date_arg,
        default=None,
        help="Filter appointments from YYYY-MM-DD (inclusive).",
    )
    parser.add_argument(
        "--appts-to",
        dest="appts_to",
        type=_parse_date_arg,
        default=None,
        help="Filter appointments to YYYY-MM-DD (inclusive).",
    )
    args = parser.parse_args()
    try:
        patient_codes = _parse_patient_codes_arg(args.patient_codes, args.patient_codes_file)
        charting_domains = _parse_charting_domains_arg(args.domains)
        _validate_patient_filters(
            patients_from=args.patients_from,
            patients_to=args.patients_to,
            patient_codes=patient_codes,
        )
    except RuntimeError as exc:
        print(str(exc))
        return 2

    if args.mapping_quality_out and args.entity != "patients":
        print("--mapping-quality-out is only supported for --entity patients.")
        return 2
    if args.output_json and args.entity != "charting_canonical":
        print("--output-json is only supported for --entity charting_canonical.")
        return 2
    if args.run_summary_out and args.entity != "charting_canonical":
        print("--run-summary-out is only supported for --entity charting_canonical.")
        return 2
    if charting_domains is not None and args.entity != "charting_canonical":
        print("--domains is only supported for --entity charting_canonical.")
        return 2
    if args.verify_postgres and args.entity != "patients":
        print("--verify-postgres is only supported for --entity patients.")
        return 2
    if args.connect_timeout_seconds is not None and args.connect_timeout_seconds <= 0:
        print("--connect-timeout-seconds must be a positive integer.")
        return 2
    if args.batch_size is not None and args.batch_size <= 0:
        print("--batch-size must be a positive integer.")
        return 2
    if args.resume and not args.state_file:
        print("--resume requires --state-file.")
        return 2
    if args.resume and (args.entity != "charting_canonical" or not patient_codes):
        print("--resume is only supported for --entity charting_canonical with patient codes.")
        return 2
    if args.state_file and args.entity != "charting_canonical":
        print("--state-file is only supported for --entity charting_canonical.")
        return 2
    if args.stop_after_batches is not None and args.stop_after_batches <= 0:
        print("--stop-after-batches must be a positive integer.")
        return 2

    effective_batch_size = _effective_batch_size(args.entity, args.batch_size)

    if args.verify_postgres:
        session = SessionLocal()
        try:
            summary = verify_patients_window(
                session,
                patients_from=args.patients_from,
                patients_to=args.patients_to,
            )
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 0
        finally:
            session.close()

    if args.entity == "treatment_plans_backfill_patient_ids":
        if not args.apply or args.confirm != "APPLY":
            print("Refusing to backfill without --apply --confirm APPLY.")
            return 2
        session = SessionLocal()
        try:
            actor_id = resolve_actor_id(session)
            stats = backfill_r4_treatment_plan_patients(session, actor_id)
            session.commit()
            print(json.dumps(stats.as_dict(), indent=2, sort_keys=True))
            return 0
        finally:
            session.close()

    if args.entity == "treatment_plans_summary":
        session = SessionLocal()
        try:
            summary = summarize_r4_treatment_plans(session)
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 0
        finally:
            session.close()

    if args.source == "sqlserver":
        if args.apply and args.dry_run:
            print("Choose either --apply or --dry-run (default is dry-run).")
            return 2
        if args.apply and args.confirm != "APPLY":
            print("Refusing to apply without --confirm APPLY.")
            return 2
        try:
            config = R4SqlServerConfig.from_env()
            if args.connect_timeout_seconds is not None:
                config.timeout_seconds = args.connect_timeout_seconds
            config.require_enabled()
            source = R4SqlServerSource(config)
            if args.apply:
                session = SessionLocal()
                try:
                    actor_id = resolve_actor_id(session)
                    if args.entity == "patients":
                        stats = import_r4_patients(
                            session,
                            source,
                            actor_id,
                            legacy_source="r4",
                            patients_from=args.patients_from,
                            patients_to=args.patients_to,
                            patient_codes=patient_codes,
                            limit=args.limit,
                            progress_every=args.progress_every,
                        )
                    elif args.entity == "patients_appts":
                        stats = import_r4(
                            session,
                            source,
                            actor_id,
                            legacy_source="r4",
                            appts_from=args.appts_from,
                            appts_to=args.appts_to,
                            limit=None,
                        )
                    elif args.entity == "appointments":
                        stats = import_r4_appointments(
                            session,
                            source,
                            actor_id,
                            legacy_source="r4",
                            date_from=args.appts_from,
                            date_to=args.appts_to,
                            limit=args.limit,
                        )
                    elif args.entity == "treatments":
                        stats = import_r4_treatments(
                            session,
                            source,
                            actor_id,
                            legacy_source="r4",
                            limit=args.limit,
                        )
                    elif args.entity == "users":
                        stats = import_r4_users(
                            session,
                            source,
                            actor_id,
                            legacy_source="r4",
                            limit=args.limit,
                        )
                    elif args.entity == "treatment_transactions":
                        stats = import_r4_treatment_transactions(
                            session,
                            source,
                            actor_id,
                            legacy_source="r4",
                            patients_from=args.patients_from,
                            patients_to=args.patients_to,
                            limit=args.limit,
                            progress_every=args.progress_every,
                        )
                    elif args.entity == "charting":
                        stats = import_r4_charting(
                            session,
                            source,
                            actor_id,
                            legacy_source="r4",
                            patients_from=args.patients_from,
                            patients_to=args.patients_to,
                            limit=args.limit,
                        )
                    elif args.entity == "charting_canonical":
                        extractor = SqlServerChartingExtractor(config)
                        if patient_codes:
                            stats_payload, report = _run_charting_canonical_batched(
                                session=session,
                                source=extractor,
                                source_name="sqlserver",
                                entity="charting_canonical",
                                patient_codes=patient_codes,
                                patients_from=args.patients_from,
                                patients_to=args.patients_to,
                                charting_from=args.charting_from,
                                charting_to=args.charting_to,
                                charting_domains=charting_domains,
                                limit=args.limit,
                                allow_unmapped_patients=args.allow_unmapped_patients,
                                batch_size=effective_batch_size,
                                state_file=args.state_file,
                                resume=args.resume,
                                stop_after_batches=args.stop_after_batches,
                            )
                            stats = None
                        else:
                            stats, report = import_r4_charting_canonical_report(
                                session,
                                extractor,
                                patients_from=args.patients_from,
                                patients_to=args.patients_to,
                                patient_codes=patient_codes,
                                date_from=args.charting_from,
                                date_to=args.charting_to,
                                domains=charting_domains,
                                limit=args.limit,
                                dry_run=False,
                                allow_unmapped_patients=args.allow_unmapped_patients,
                            )
                            stats_payload = _normalize_charting_stats(
                                stats=stats.as_dict(),
                                report=report,
                            )
                            report = _finalize_charting_report(
                                report,
                                source="sqlserver",
                                entity="charting_canonical",
                                patients_from=args.patients_from,
                                patients_to=args.patients_to,
                                patient_codes=patient_codes,
                                charting_from=args.charting_from,
                                charting_to=args.charting_to,
                                charting_domains=charting_domains,
                                limit=args.limit,
                                mode="apply",
                            )
                        if args.output_json:
                            _write_report_file(args.output_json, report)
                        if args.run_summary_out:
                            _write_report_file(args.run_summary_out, report)
                    else:
                        stats = import_r4_treatment_plans(
                            session,
                            source,
                            actor_id,
                            legacy_source="r4",
                            patients_from=args.patients_from,
                            patients_to=args.patients_to,
                            tp_from=args.tp_from,
                            tp_to=args.tp_to,
                            limit=args.limit,
                            batch_size=effective_batch_size,
                            sleep_ms=args.sleep_ms,
                            progress_every=args.progress_every,
                            progress_enabled=True,
                        )
                    session.commit()
                finally:
                    session.close()
                if args.entity == "patients":
                    _maybe_write_mapping_quality(
                        args.mapping_quality_out,
                        stats.mapping_quality,
                        args.patients_from,
                        args.patients_to,
                        patient_codes=patient_codes,
                    )
                stats_out_payload = (
                    stats_payload if args.entity == "charting_canonical" else stats.as_dict()
                )
                _maybe_write_stats(
                    args.stats_out,
                    args.entity,
                    stats_out_payload,
                    args.patients_from,
                    args.patients_to,
                    patient_codes,
                    args.appts_from,
                    args.appts_to,
                )
                print(json.dumps(stats_out_payload, indent=2, sort_keys=True))
                return 0
            if args.entity == "patients":
                summary = source.dry_run_summary_patients(
                    limit=args.limit or 10,
                    patients_from=args.patients_from,
                    patients_to=args.patients_to,
                )
                if args.mapping_quality_out:
                    mapping_quality = _build_patients_mapping_quality(
                        source,
                        patients_from=args.patients_from,
                        patients_to=args.patients_to,
                        patient_codes=patient_codes,
                        limit=None,
                    )
                    _maybe_write_mapping_quality(
                        args.mapping_quality_out,
                        mapping_quality,
                        args.patients_from,
                        args.patients_to,
                        patient_codes=patient_codes,
                    )
            elif args.entity == "patients_appts":
                summary = source.dry_run_summary(
                    limit=args.limit or 10,
                    date_from=args.appts_from,
                    date_to=args.appts_to,
                )
            elif args.entity == "appointments":
                summary = source.dry_run_summary_appointments(
                    limit=args.limit or 10,
                    date_from=args.appts_from,
                    date_to=args.appts_to,
                )
            elif args.entity == "treatments":
                summary = source.dry_run_summary_treatments(limit=args.limit or 10)
            elif args.entity == "users":
                summary = source.dry_run_summary_users(limit=args.limit or 10)
            elif args.entity == "treatment_transactions":
                summary = source.dry_run_summary_treatment_transactions(
                    limit=args.limit or 10,
                    patients_from=args.patients_from,
                    patients_to=args.patients_to,
                    date_floor=args.date_floor,
                )
            elif args.entity == "charting":
                summary = source.dry_run_summary_charting(
                    limit=args.limit or 10,
                    patients_from=args.patients_from,
                    patients_to=args.patients_to,
                )
            elif args.entity == "charting_canonical":
                session = SessionLocal()
                try:
                    extractor = SqlServerChartingExtractor(config)
                    stats, report = import_r4_charting_canonical_report(
                        session,
                        extractor,
                        patients_from=args.patients_from,
                        patients_to=args.patients_to,
                        patient_codes=patient_codes,
                        date_from=args.charting_from,
                        date_to=args.charting_to,
                        domains=charting_domains,
                        limit=args.limit,
                        dry_run=True,
                        allow_unmapped_patients=args.allow_unmapped_patients,
                    )
                    report = _finalize_charting_report(
                        report,
                        source="sqlserver",
                        entity="charting_canonical",
                        patients_from=args.patients_from,
                        patients_to=args.patients_to,
                        patient_codes=patient_codes,
                        charting_from=args.charting_from,
                        charting_to=args.charting_to,
                        charting_domains=charting_domains,
                        limit=args.limit,
                        mode="dry_run",
                    )
                    summary = report
                    if args.output_json:
                        _write_report_file(args.output_json, report)
                    if args.run_summary_out:
                        _write_report_file(args.run_summary_out, report)
                finally:
                    session.close()
            else:
                summary = source.dry_run_summary_treatment_plans(
                    limit=args.limit or 10,
                    patients_from=args.patients_from,
                    patients_to=args.patients_to,
                    tp_from=args.tp_from,
                    tp_to=args.tp_to,
                )
        except RuntimeError as exc:
            print(str(exc))
            return 2
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    if args.dry_run or args.apply:
        print("--dry-run/--apply are only supported with --source sqlserver.")
        return 2

    session = SessionLocal()
    try:
        actor_id = resolve_actor_id(session)
        source = FixtureSource()
        if args.entity == "patients":
            stats = import_r4_patients(
                session,
                source,
                actor_id,
                patients_from=args.patients_from,
                patients_to=args.patients_to,
                patient_codes=patient_codes,
                limit=args.limit,
                progress_every=args.progress_every,
            )
        elif args.entity == "patients_appts":
            stats = import_r4(session, source, actor_id)
        elif args.entity == "appointments":
            stats = import_r4_appointments(
                session,
                source,
                actor_id,
                date_from=args.appts_from,
                date_to=args.appts_to,
                limit=args.limit,
            )
        elif args.entity == "treatments":
            stats = import_r4_treatments(session, source, actor_id)
        elif args.entity == "users":
            stats = import_r4_users(session, source, actor_id)
        elif args.entity == "treatment_transactions":
            stats = import_r4_treatment_transactions(
                session,
                source,
                actor_id,
                patients_from=args.patients_from,
                patients_to=args.patients_to,
                limit=args.limit,
                progress_every=args.progress_every,
            )
        elif args.entity == "charting":
            stats = import_r4_charting(
                session,
                source,
                actor_id,
                patients_from=args.patients_from,
                patients_to=args.patients_to,
                limit=args.limit,
            )
        elif args.entity == "charting_canonical":
            if patient_codes:
                stats_payload, report = _run_charting_canonical_batched(
                    session=session,
                    source=source,
                    source_name="fixtures",
                    entity="charting_canonical",
                    patient_codes=patient_codes,
                    patients_from=args.patients_from,
                    patients_to=args.patients_to,
                    charting_from=args.charting_from,
                    charting_to=args.charting_to,
                    charting_domains=charting_domains,
                    limit=args.limit,
                    allow_unmapped_patients=args.allow_unmapped_patients,
                    batch_size=effective_batch_size,
                    state_file=args.state_file,
                    resume=args.resume,
                    stop_after_batches=args.stop_after_batches,
                )
                stats = None
            else:
                stats, report = import_r4_charting_canonical_report(
                    session,
                    source,
                    patients_from=args.patients_from,
                    patients_to=args.patients_to,
                    patient_codes=patient_codes,
                    date_from=args.charting_from,
                    date_to=args.charting_to,
                    domains=charting_domains,
                    limit=args.limit,
                    dry_run=False,
                    allow_unmapped_patients=args.allow_unmapped_patients,
                )
                stats_payload = _normalize_charting_stats(
                    stats=stats.as_dict(),
                    report=report,
                )
                report = _finalize_charting_report(
                    report,
                    source="fixtures",
                    entity="charting_canonical",
                    patients_from=args.patients_from,
                    patients_to=args.patients_to,
                    patient_codes=patient_codes,
                    charting_from=args.charting_from,
                    charting_to=args.charting_to,
                    charting_domains=charting_domains,
                    limit=args.limit,
                    mode="apply",
                )
            if args.output_json:
                _write_report_file(args.output_json, report)
            if args.run_summary_out:
                _write_report_file(args.run_summary_out, report)
        else:
            stats = import_r4_treatment_plans(
                session,
                source,
                actor_id,
                patients_from=args.patients_from,
                patients_to=args.patients_to,
                tp_from=args.tp_from,
                tp_to=args.tp_to,
                limit=args.limit,
                batch_size=effective_batch_size,
                sleep_ms=args.sleep_ms,
                progress_every=args.progress_every,
                progress_enabled=False,
            )
        session.commit()
        if args.entity == "patients":
            _maybe_write_mapping_quality(
                args.mapping_quality_out,
                stats.mapping_quality,
                args.patients_from,
                args.patients_to,
                patient_codes=patient_codes,
            )
        stats_out_payload = stats_payload if args.entity == "charting_canonical" else stats.as_dict()
        _maybe_write_stats(
            args.stats_out,
            args.entity,
            stats_out_payload,
            args.patients_from,
            args.patients_to,
            patient_codes,
            args.appts_from,
            args.appts_to,
        )
        print(json.dumps(stats_out_payload, indent=2, sort_keys=True))
        return 0
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
