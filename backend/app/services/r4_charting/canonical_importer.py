from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
from uuid import UUID
from typing import Iterable, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.r4_charting_canonical import R4ChartingCanonicalRecord
from app.models.r4_patient_mapping import R4PatientMapping
from app.services.r4_import.source import R4Source
from app.services.r4_charting.canonical_types import (
    CanonicalImportStats,
    CanonicalRecordInput,
)


class CanonicalChartingSource(Protocol):
    select_only: bool

    def iter_canonical_records(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[CanonicalRecordInput]:
        raise NotImplementedError

    def collect_canonical_records(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        patient_codes: list[int] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int | None = None,
        domains: list[str] | None = None,
    ) -> tuple[list[CanonicalRecordInput], dict[str, int]]:
        raise NotImplementedError


def _json_sanitize(value):  # type: ignore[no-untyped-def]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if isinstance(value, dict):
        sanitized: dict[str, object] = {}
        for key, val in value.items():
            if isinstance(key, str):
                safe_key = key
            else:
                safe_key = _json_sanitize(key)
                if not isinstance(safe_key, str):
                    safe_key = str(safe_key)
            sanitized[safe_key] = _json_sanitize(val)
        return sanitized
    if isinstance(value, list):
        return [_json_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [_json_sanitize(item) for item in value]
    return value


def _json_roundtrip(value: dict) -> dict:
    return json.loads(
        json.dumps(value, default=_json_sanitize, sort_keys=True, separators=(",", ":"))
    )


def _model_payload(item) -> dict:
    if hasattr(item, "model_dump"):
        try:
            data = item.model_dump(mode="json")
        except TypeError:
            data = item.model_dump()
    else:
        data = item.dict()
    return _json_roundtrip(_json_sanitize(data))


def _coerce_payload(payload):  # type: ignore[no-untyped-def]
    if payload is None:
        return None
    if hasattr(payload, "model_dump"):
        try:
            payload = payload.model_dump(mode="json")
        except TypeError:
            payload = payload.model_dump()
    elif hasattr(payload, "dict"):
        payload = payload.dict()
    return _json_roundtrip(_json_sanitize(payload))


def _compute_content_hash(record: CanonicalRecordInput) -> str:
    payload = _coerce_payload(record.payload) if record.payload is not None else None
    material = {
        "domain": record.domain,
        "r4_source": record.r4_source,
        "r4_source_id": record.r4_source_id,
        "legacy_patient_code": record.legacy_patient_code,
        "recorded_at": _json_sanitize(record.recorded_at),
        "entered_at": _json_sanitize(record.entered_at),
        "tooth": record.tooth,
        "surface": record.surface,
        "code_id": record.code_id,
        "status": record.status,
        "payload": payload,
    }
    raw = json.dumps(material, sort_keys=True, separators=(",", ":"), default=_json_sanitize)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _build_unique_key(
    *,
    domain: str,
    r4_source: str,
    r4_source_id: str,
    patient_id: int | None,
    legacy_patient_code: int | None,
) -> str:
    if legacy_patient_code is not None:
        suffix = str(legacy_patient_code)
    elif patient_id is not None:
        suffix = str(patient_id)
    else:
        suffix = ""
    return f"{domain}|{r4_source}|{r4_source_id}|{suffix}"


def _load_patient_mappings(
    session: Session, patient_codes: set[int]
) -> dict[int, int]:
    mappings: dict[int, int] = {}
    if patient_codes:
        for mapping in session.execute(
            select(R4PatientMapping).where(
                R4PatientMapping.legacy_source == "r4",
                R4PatientMapping.legacy_patient_code.in_(patient_codes),
            )
        ).scalars():
            mappings[int(mapping.legacy_patient_code)] = int(mapping.patient_id)
    return mappings


def _dedupe_records(
    records: list[CanonicalRecordInput],
) -> tuple[list[CanonicalRecordInput], int, list[str]]:
    duplicate_unique_key = 0
    duplicate_examples: list[str] = []
    deduped: list[CanonicalRecordInput] = []
    seen: set[str] = set()
    for record in records:
        unique_key = _build_unique_key(
            domain=record.domain,
            r4_source=record.r4_source,
            r4_source_id=record.r4_source_id,
            patient_id=None,
            legacy_patient_code=record.legacy_patient_code,
        )
        if unique_key in seen:
            duplicate_unique_key += 1
            if len(duplicate_examples) < 5:
                duplicate_examples.append(unique_key)
            continue
        seen.add(unique_key)
        deduped.append(record)
    return deduped, duplicate_unique_key, duplicate_examples


def _ensure_select_only(source: object) -> None:
    if hasattr(source, "ensure_select_only"):
        source.ensure_select_only()
    select_only = getattr(source, "select_only", True)
    if not select_only:
        raise RuntimeError("R4 charting canonical importer requires SELECT-only source.")


def _iter_from_r4_source(
    source: R4Source,
    patients_from: int | None = None,
    patients_to: int | None = None,
    limit: int | None = None,
) -> Iterable[CanonicalRecordInput]:
    for item in source.list_tooth_systems(limit=limit):
        yield CanonicalRecordInput(
            domain="tooth_system",
            r4_source="dbo.ToothSystems",
            r4_source_id=str(item.tooth_system_id),
            legacy_patient_code=None,
            recorded_at=None,
            entered_at=None,
            tooth=None,
            surface=None,
            code_id=None,
            status=None,
            payload=_model_payload(item),
        )

    for item in source.list_tooth_surfaces(limit=limit):
        yield CanonicalRecordInput(
            domain="tooth_surface",
            r4_source="dbo.ToothSurfaces",
            r4_source_id=f"{item.tooth_id}:{item.surface_no}",
            legacy_patient_code=None,
            recorded_at=None,
            entered_at=None,
            tooth=item.tooth_id,
            surface=item.surface_no,
            code_id=None,
            status=None,
            payload=_model_payload(item),
        )

    for item in source.list_chart_healing_actions(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        yield CanonicalRecordInput(
            domain="chart_healing_action",
            r4_source="dbo.ChartHealingActions",
            r4_source_id=str(item.action_id),
            legacy_patient_code=item.patient_code,
            recorded_at=item.action_date,
            entered_at=None,
            tooth=item.tooth,
            surface=item.surface,
            code_id=item.code_id,
            status=item.status,
            payload=_model_payload(item),
        )

    for item in source.list_treatment_plans(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        r4_source_id = f"{item.patient_code}:{item.tp_number}"
        yield CanonicalRecordInput(
            domain="treatment_plan",
            r4_source="dbo.TreatmentPlans",
            r4_source_id=r4_source_id,
            legacy_patient_code=item.patient_code,
            recorded_at=item.creation_date,
            entered_at=item.acceptance_date,
            tooth=None,
            surface=None,
            code_id=None,
            status=None,
            payload=_model_payload(item),
        )

    for item in source.list_treatment_plan_items(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        if item.tp_item_key is not None:
            r4_source_id = str(item.tp_item_key)
        else:
            r4_source_id = f"{item.patient_code}:{item.tp_number}:{item.tp_item}"
        yield CanonicalRecordInput(
            domain="treatment_plan_item",
            r4_source="dbo.TreatmentPlanItems",
            r4_source_id=r4_source_id,
            legacy_patient_code=item.patient_code,
            recorded_at=item.completed_date,
            entered_at=None,
            tooth=item.tooth,
            surface=item.surface,
            code_id=item.code_id,
            status=None,
            payload=_model_payload(item),
        )

    for item in source.list_treatment_plan_reviews(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        r4_source_id = f"{item.patient_code}:{item.tp_number}"
        yield CanonicalRecordInput(
            domain="treatment_plan_review",
            r4_source="dbo.TreatmentPlanReviews",
            r4_source_id=r4_source_id,
            legacy_patient_code=item.patient_code,
            recorded_at=item.last_edit_date,
            entered_at=None,
            tooth=None,
            surface=None,
            code_id=None,
            status=None,
            payload=_model_payload(item),
        )

    for item in source.list_bpe_entries(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        r4_source_id = str(item.bpe_id) if item.bpe_id is not None else "unknown"
        if item.bpe_id is None and item.patient_code is not None:
            r4_source_id = f"{item.patient_code}:{item.recorded_at}"
        yield CanonicalRecordInput(
            domain="bpe_entry",
            r4_source="dbo.BPE",
            r4_source_id=r4_source_id,
            legacy_patient_code=item.patient_code,
            recorded_at=item.recorded_at,
            entered_at=None,
            tooth=None,
            surface=None,
            code_id=None,
            status=None,
            payload=_model_payload(item),
        )

    for item in source.list_bpe_furcations(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        r4_source_id = str(item.furcation_id) if item.furcation_id is not None else "unknown"
        if item.furcation_id is None:
            r4_source_id = f"{item.bpe_id}:{item.tooth}:{item.sextant}:{item.recorded_at}"
        yield CanonicalRecordInput(
            domain="bpe_furcation",
            r4_source="dbo.BPEFurcation",
            r4_source_id=r4_source_id,
            legacy_patient_code=item.patient_code,
            recorded_at=item.recorded_at,
            entered_at=None,
            tooth=item.tooth,
            surface=None,
            code_id=None,
            status=None,
            payload=_model_payload(item),
        )

    for item in source.list_perio_probes(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        if item.trans_id is not None:
            r4_source_id = f"{item.trans_id}:{item.tooth}:{item.probing_point}"
        else:
            r4_source_id = f"{item.patient_code}:{item.tooth}:{item.probing_point}:{item.recorded_at}"
        yield CanonicalRecordInput(
            domain="perio_probe",
            r4_source="dbo.PerioProbe",
            r4_source_id=r4_source_id,
            legacy_patient_code=item.patient_code,
            recorded_at=item.recorded_at,
            entered_at=None,
            tooth=item.tooth,
            surface=None,
            code_id=None,
            status=None,
            payload=_model_payload(item),
        )

    for item in source.list_perio_plaque(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        if item.trans_id is not None:
            r4_source_id = f"{item.trans_id}:{item.tooth}"
        else:
            r4_source_id = f"{item.patient_code}:{item.tooth}:{item.recorded_at}"
        yield CanonicalRecordInput(
            domain="perio_plaque",
            r4_source="dbo.PerioPlaque",
            r4_source_id=r4_source_id,
            legacy_patient_code=item.patient_code,
            recorded_at=item.recorded_at,
            entered_at=None,
            tooth=item.tooth,
            surface=None,
            code_id=None,
            status=None,
            payload=_model_payload(item),
        )

    for item in source.list_patient_notes(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        if item.note_number is not None:
            r4_source_id = f"{item.patient_code}:{item.note_number}"
        else:
            r4_source_id = f"{item.patient_code}:{item.note_date}"
        yield CanonicalRecordInput(
            domain="patient_note",
            r4_source="dbo.PatientNotes",
            r4_source_id=r4_source_id,
            legacy_patient_code=item.patient_code,
            recorded_at=item.note_date,
            entered_at=None,
            tooth=item.tooth,
            surface=item.surface,
            code_id=None,
            status=None,
            payload=_model_payload(item),
        )

    for item in source.list_fixed_notes(limit=limit):
        yield CanonicalRecordInput(
            domain="fixed_note",
            r4_source="dbo.FixedNotes",
            r4_source_id=str(item.fixed_note_code),
            legacy_patient_code=None,
            recorded_at=None,
            entered_at=None,
            tooth=item.tooth,
            surface=item.surface,
            code_id=None,
            status=None,
            payload=_model_payload(item),
        )

    for item in source.list_note_categories(limit=limit):
        yield CanonicalRecordInput(
            domain="note_category",
            r4_source="dbo.NoteCategories",
            r4_source_id=str(item.category_number),
            legacy_patient_code=None,
            recorded_at=None,
            entered_at=None,
            tooth=None,
            surface=None,
            code_id=None,
            status=None,
            payload=_model_payload(item),
        )

    for item in source.list_treatment_notes(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        yield CanonicalRecordInput(
            domain="treatment_note",
            r4_source="dbo.TreatmentNotes",
            r4_source_id=str(item.note_id),
            legacy_patient_code=item.patient_code,
            recorded_at=item.note_date,
            entered_at=None,
            tooth=None,
            surface=None,
            code_id=None,
            status=None,
            payload=_model_payload(item),
        )

    for item in source.list_temporary_notes(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        r4_source_id = str(item.patient_code)
        yield CanonicalRecordInput(
            domain="temporary_note",
            r4_source="dbo.TemporaryNotes",
            r4_source_id=r4_source_id,
            legacy_patient_code=item.patient_code,
            recorded_at=item.legacy_updated_at,
            entered_at=None,
            tooth=None,
            surface=None,
            code_id=None,
            status=None,
            payload=_model_payload(item),
        )

    for item in source.list_old_patient_notes(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        if item.note_number is not None:
            r4_source_id = f"{item.patient_code}:{item.note_number}"
        else:
            r4_source_id = f"{item.patient_code}:{item.note_date}"
        yield CanonicalRecordInput(
            domain="old_patient_note",
            r4_source="dbo.OldPatientNotes",
            r4_source_id=r4_source_id,
            legacy_patient_code=item.patient_code,
            recorded_at=item.note_date,
            entered_at=None,
            tooth=item.tooth,
            surface=item.surface,
            code_id=None,
            status=None,
            payload=_model_payload(item),
        )


def import_r4_charting_canonical(
    session: Session,
    source: CanonicalChartingSource | R4Source,
    *,
    patients_from: int | None = None,
    patients_to: int | None = None,
    patient_codes: list[int] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    domains: list[str] | None = None,
    limit: int | None = None,
    allow_unmapped_patients: bool = False,
) -> CanonicalImportStats:
    _ensure_select_only(source)

    if hasattr(source, "collect_canonical_records"):
        records, _ = _collect_canonical_records(
            source,
            patients_from=patients_from,
            patients_to=patients_to,
            patient_codes=patient_codes,
            date_from=date_from,
            date_to=date_to,
            domains=domains,
            limit=limit,
        )
    elif hasattr(source, "iter_canonical_records"):
        records = list(source.iter_canonical_records(patients_from, patients_to, limit))
    else:
        records = list(_iter_from_r4_source(source, patients_from, patients_to, limit))

    records, _, _ = _dedupe_records(records)
    stats = CanonicalImportStats(total=len(records))
    if not records:
        return stats

    patient_codes = {r.legacy_patient_code for r in records if r.legacy_patient_code is not None}
    mappings = _load_patient_mappings(session, {int(code) for code in patient_codes})

    unique_keys = []
    now = datetime.now(timezone.utc)
    prepared: list[tuple[CanonicalRecordInput, str, int | None, str]] = []
    for record in records:
        patient_id = None
        if record.legacy_patient_code is not None:
            patient_id = mappings.get(int(record.legacy_patient_code))
            if patient_id is None and not allow_unmapped_patients:
                stats.unmapped_patients += 1
                stats.skipped += 1
                continue
        unique_key = _build_unique_key(
            domain=record.domain,
            r4_source=record.r4_source,
            r4_source_id=record.r4_source_id,
            patient_id=patient_id,
            legacy_patient_code=record.legacy_patient_code,
        )
        unique_keys.append(unique_key)
        content_hash = _compute_content_hash(record)
        prepared.append((record, unique_key, patient_id, content_hash))

    existing = {
        row.unique_key: row
        for row in session.execute(
            select(R4ChartingCanonicalRecord).where(
                R4ChartingCanonicalRecord.unique_key.in_(unique_keys)
            )
        ).scalars()
    }

    for record, unique_key, patient_id, content_hash in prepared:
        current = existing.get(unique_key)
        if current is None:
            session.add(
                R4ChartingCanonicalRecord(
                    unique_key=unique_key,
                    domain=record.domain,
                    r4_source=record.r4_source,
                    r4_source_id=record.r4_source_id,
                    legacy_patient_code=record.legacy_patient_code,
                    patient_id=patient_id,
                    recorded_at=record.recorded_at,
                    entered_at=record.entered_at,
                    tooth=record.tooth,
                    surface=record.surface,
                    code_id=record.code_id,
                    status=record.status,
                    payload=_coerce_payload(record.payload),
                    content_hash=content_hash,
                    extracted_at=now,
                )
            )
            stats.created += 1
            continue

        if current.content_hash == content_hash:
            stats.skipped += 1
            continue

        current.domain = record.domain
        current.r4_source = record.r4_source
        current.r4_source_id = record.r4_source_id
        current.legacy_patient_code = record.legacy_patient_code
        current.patient_id = patient_id
        current.recorded_at = record.recorded_at
        current.entered_at = record.entered_at
        current.tooth = record.tooth
        current.surface = record.surface
        current.code_id = record.code_id
        current.status = record.status
        current.payload = _coerce_payload(record.payload)
        current.content_hash = content_hash
        current.extracted_at = now
        stats.updated += 1

    return stats


def _build_canonical_report(
    records: list[CanonicalRecordInput],
    stats: CanonicalImportStats,
    *,
    dropped: dict[str, int] | None = None,
) -> dict[str, object]:
    per_source: dict[str, dict[str, int]] = {}
    missing_source_id = 0
    missing_patient_code = 0
    patient_codes: set[int] = set()
    for record in records:
        bucket = per_source.get(record.r4_source)
        if bucket is None:
            bucket = {"fetched": 0}
            per_source[record.r4_source] = bucket
        bucket["fetched"] += 1
        if not record.r4_source_id or record.r4_source_id == "unknown":
            missing_source_id += 1
        if record.legacy_patient_code is None:
            missing_patient_code += 1
        else:
            patient_codes.add(int(record.legacy_patient_code))
    report: dict[str, object] = {
        "total_records": len(records),
        "distinct_patients": len(patient_codes),
        "missing_source_id": missing_source_id,
        "missing_patient_code": missing_patient_code,
        "by_source": per_source,
        "stats": stats.as_dict(),
    }
    if dropped:
        report["dropped"] = dropped
        warnings: list[str] = []
        undated = dropped.get("undated_included") if isinstance(dropped, dict) else None
        if undated:
            warnings.append(
                "Undated rows included from sources without date columns; date bounds not applied."
            )
        if warnings:
            report["warnings"] = warnings
    return report


def import_r4_charting_canonical_report(
    session: Session,
    source: CanonicalChartingSource | R4Source,
    *,
    patients_from: int | None = None,
    patients_to: int | None = None,
    patient_codes: list[int] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    domains: list[str] | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    allow_unmapped_patients: bool = False,
) -> tuple[CanonicalImportStats, dict[str, object]]:
    _ensure_select_only(source)

    dropped: dict[str, int] | None = None
    if hasattr(source, "collect_canonical_records"):
        records, dropped = _collect_canonical_records(
            source,
            patients_from=patients_from,
            patients_to=patients_to,
            patient_codes=patient_codes,
            date_from=date_from,
            date_to=date_to,
            domains=domains,
            limit=limit,
        )
    elif hasattr(source, "iter_canonical_records"):
        records = list(source.iter_canonical_records(patients_from, patients_to, limit))
    else:
        records = list(_iter_from_r4_source(source, patients_from, patients_to, limit))

    records, duplicate_unique_key, duplicate_examples = _dedupe_records(records)
    stats = CanonicalImportStats(total=len(records))
    unmapped_examples: list[int] = []
    if records and not allow_unmapped_patients:
        patient_codes = {
            int(r.legacy_patient_code)
            for r in records
            if r.legacy_patient_code is not None
        }
        mappings = _load_patient_mappings(session, patient_codes)
        for record in records:
            if record.legacy_patient_code is None:
                continue
            if int(record.legacy_patient_code) not in mappings:
                stats.unmapped_patients += 1
                stats.skipped += 1
                if len(unmapped_examples) < 5:
                    unmapped_examples.append(int(record.legacy_patient_code))
    if dry_run:
        report = _build_canonical_report(records, stats, dropped=dropped)
        if duplicate_unique_key:
            report.setdefault("dropped", {})
            report["dropped"]["duplicate_unique_key"] = duplicate_unique_key
            if duplicate_examples:
                report["dropped"]["duplicate_unique_key_examples"] = duplicate_examples
        if stats.unmapped_patients:
            report.setdefault("dropped", {})
            report["dropped"]["unmapped_patients"] = stats.unmapped_patients
            if unmapped_examples:
                report["dropped"]["unmapped_patient_examples"] = unmapped_examples
        return stats, report

    stats = import_r4_charting_canonical(
        session,
        source,
        patients_from=patients_from,
        patients_to=patients_to,
        patient_codes=patient_codes,
        date_from=date_from,
        date_to=date_to,
        domains=domains,
        limit=limit,
        allow_unmapped_patients=allow_unmapped_patients,
    )
    report = _build_canonical_report(records, stats, dropped=dropped)
    if duplicate_unique_key:
        report.setdefault("dropped", {})
        report["dropped"]["duplicate_unique_key"] = duplicate_unique_key
        if duplicate_examples:
            report["dropped"]["duplicate_unique_key_examples"] = duplicate_examples
    if stats.unmapped_patients:
        report.setdefault("dropped", {})
        report["dropped"]["unmapped_patients"] = stats.unmapped_patients
        if unmapped_examples:
            report["dropped"]["unmapped_patient_examples"] = unmapped_examples
    return stats, report


def _collect_canonical_records(
    source: CanonicalChartingSource | R4Source,
    *,
    patients_from: int | None,
    patients_to: int | None,
    patient_codes: list[int] | None,
    date_from: date | None,
    date_to: date | None,
    domains: list[str] | None,
    limit: int | None,
) -> tuple[list[CanonicalRecordInput], dict[str, int]]:
    if patient_codes is None:
        try:
            return source.collect_canonical_records(
                patients_from=patients_from,
                patients_to=patients_to,
                date_from=date_from,
                date_to=date_to,
                domains=domains,
                limit=limit,
            )
        except TypeError:
            return source.collect_canonical_records(
                patients_from=patients_from,
                patients_to=patients_to,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
            )
    try:
        return source.collect_canonical_records(
            patients_from=patients_from,
            patients_to=patients_to,
            patient_codes=patient_codes,
            date_from=date_from,
            date_to=date_to,
            domains=domains,
            limit=limit,
        )
    except TypeError as exc:
        try:
            return source.collect_canonical_records(
                patients_from=patients_from,
                patients_to=patients_to,
                patient_codes=patient_codes,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
            )
        except TypeError:
            raise RuntimeError(
                "This charting source does not support --patient-codes."
            ) from exc
