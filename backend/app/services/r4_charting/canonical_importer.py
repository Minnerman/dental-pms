from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
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
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int | None = None,
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
    return json.loads(json.dumps(value, default=_json_sanitize))


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
    limit: int | None = None,
) -> CanonicalImportStats:
    _ensure_select_only(source)

    if hasattr(source, "collect_canonical_records"):
        records, _ = source.collect_canonical_records(
            patients_from=patients_from,
            patients_to=patients_to,
            date_from=None,
            date_to=None,
            limit=limit,
        )
    elif hasattr(source, "iter_canonical_records"):
        records = list(source.iter_canonical_records(patients_from, patients_to, limit))
    else:
        records = list(_iter_from_r4_source(source, patients_from, patients_to, limit))

    stats = CanonicalImportStats(total=len(records))
    if not records:
        return stats

    patient_codes = {r.legacy_patient_code for r in records if r.legacy_patient_code is not None}
    mappings = {}
    if patient_codes:
        for mapping in session.execute(
            select(R4PatientMapping).where(
                R4PatientMapping.legacy_source == "r4",
                R4PatientMapping.legacy_patient_code.in_(patient_codes),
            )
        ).scalars():
            mappings[int(mapping.legacy_patient_code)] = int(mapping.patient_id)

    unique_keys = []
    now = datetime.now(timezone.utc)
    prepared: list[tuple[CanonicalRecordInput, str, int | None]] = []
    for record in records:
        patient_id = None
        if record.legacy_patient_code is not None:
            patient_id = mappings.get(int(record.legacy_patient_code))
            if patient_id is None:
                stats.unmapped_patients += 1
        unique_key = _build_unique_key(
            domain=record.domain,
            r4_source=record.r4_source,
            r4_source_id=record.r4_source_id,
            patient_id=patient_id,
            legacy_patient_code=record.legacy_patient_code,
        )
        unique_keys.append(unique_key)
        prepared.append((record, unique_key, patient_id))

    existing = {
        row.unique_key: row
        for row in session.execute(
            select(R4ChartingCanonicalRecord).where(
                R4ChartingCanonicalRecord.unique_key.in_(unique_keys)
            )
        ).scalars()
    }

    for record, unique_key, patient_id in prepared:
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
                    extracted_at=now,
                )
            )
            stats.created += 1
            continue

        same = (
            current.domain == record.domain
            and current.r4_source == record.r4_source
            and current.r4_source_id == record.r4_source_id
            and current.legacy_patient_code == record.legacy_patient_code
            and current.patient_id == patient_id
            and current.recorded_at == record.recorded_at
            and current.entered_at == record.entered_at
            and current.tooth == record.tooth
            and current.surface == record.surface
            and current.code_id == record.code_id
            and current.status == record.status
            and current.payload == record.payload
        )
        if same:
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
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> tuple[CanonicalImportStats, dict[str, object]]:
    _ensure_select_only(source)

    dropped: dict[str, int] | None = None
    if hasattr(source, "collect_canonical_records"):
        records, dropped = source.collect_canonical_records(
            patients_from=patients_from,
            patients_to=patients_to,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
    elif hasattr(source, "iter_canonical_records"):
        records = list(source.iter_canonical_records(patients_from, patients_to, limit))
    else:
        records = list(_iter_from_r4_source(source, patients_from, patients_to, limit))

    stats = CanonicalImportStats(total=len(records))
    if dry_run:
        return stats, _build_canonical_report(records, stats, dropped=dropped)

    stats = import_r4_charting_canonical(
        session,
        source,
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    )
    return stats, _build_canonical_report(records, stats, dropped=dropped)
