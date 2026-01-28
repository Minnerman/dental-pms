from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.r4_charting import (
    R4BPEEntry,
    R4BPEFurcation,
    R4ChartingImportState,
    R4ChartHealingAction,
    R4FixedNote,
    R4NoteCategory,
    R4OldPatientNote,
    R4PatientNote,
    R4PerioPlaque,
    R4PerioProbe,
    R4TemporaryNote,
    R4ToothSurface,
    R4ToothSystem,
    R4TreatmentNote,
)
from app.models.r4_manual_mapping import R4ManualMapping
from app.models.r4_patient_mapping import R4PatientMapping
from app.services.r4_import.mapping_resolver import resolve_patient_id_from_r4_patient_code
from app.services.r4_import.mapping_preflight import (
    ensure_mappings_for_range,
    mapping_exists,
)
from app.services.r4_import.source import R4Source
from app.services.r4_import.types import (
    R4BPEEntry as R4BPEEntryPayload,
    R4BPEFurcation as R4BPEFurcationPayload,
    R4ChartHealingAction as R4ChartHealingActionPayload,
    R4FixedNote as R4FixedNotePayload,
    R4NoteCategory as R4NoteCategoryPayload,
    R4OldPatientNote as R4OldPatientNotePayload,
    R4PatientNote as R4PatientNotePayload,
    R4PerioPlaque as R4PerioPlaquePayload,
    R4PerioProbe as R4PerioProbePayload,
    R4TemporaryNote as R4TemporaryNotePayload,
    R4ToothSurface as R4ToothSurfacePayload,
    R4ToothSystem as R4ToothSystemPayload,
    R4TreatmentNote as R4TreatmentNotePayload,
)


@dataclass
class ChartingImportStats:
    tooth_systems_created: int = 0
    tooth_systems_updated: int = 0
    tooth_systems_skipped: int = 0
    tooth_surfaces_created: int = 0
    tooth_surfaces_updated: int = 0
    tooth_surfaces_skipped: int = 0
    chart_actions_created: int = 0
    chart_actions_updated: int = 0
    chart_actions_skipped: int = 0
    chart_actions_null_patients: int = 0
    bpe_created: int = 0
    bpe_updated: int = 0
    bpe_skipped: int = 0
    bpe_null_patients: int = 0
    bpe_date_min: str | None = None
    bpe_date_max: str | None = None
    bpe_furcations_created: int = 0
    bpe_furcations_updated: int = 0
    bpe_furcations_skipped: int = 0
    bpe_furcations_unlinked_patients: int = 0
    perio_probes_seen: int = 0
    perio_probes_created: int = 0
    perio_probes_updated: int = 0
    perio_probes_skipped: int = 0
    perio_probes_unlinked_patients: int = 0
    perio_probes_null_patients: int = 0
    perio_probes_unmapped_patients: int = 0
    perio_probes_skipped_duplicate: int = 0
    perio_probes_sample_unlinked: list[str] = field(default_factory=list)
    perio_probes_sample_unmapped: list[str] = field(default_factory=list)
    perio_probes_sample_duplicate: list[str] = field(default_factory=list)
    perio_plaque_created: int = 0
    perio_plaque_updated: int = 0
    perio_plaque_skipped: int = 0
    perio_plaque_unlinked_patients: int = 0
    perio_plaque_null_patients: int = 0
    perio_plaque_unmapped_patients: int = 0
    patient_notes_created: int = 0
    patient_notes_updated: int = 0
    patient_notes_skipped: int = 0
    patient_notes_null_patients: int = 0
    patient_notes_date_min: str | None = None
    patient_notes_date_max: str | None = None
    fixed_notes_created: int = 0
    fixed_notes_updated: int = 0
    fixed_notes_skipped: int = 0
    note_categories_created: int = 0
    note_categories_updated: int = 0
    note_categories_skipped: int = 0
    treatment_notes_created: int = 0
    treatment_notes_updated: int = 0
    treatment_notes_skipped: int = 0
    treatment_notes_null_patients: int = 0
    treatment_notes_date_min: str | None = None
    treatment_notes_date_max: str | None = None
    temporary_notes_created: int = 0
    temporary_notes_updated: int = 0
    temporary_notes_skipped: int = 0
    old_patient_notes_created: int = 0
    old_patient_notes_updated: int = 0
    old_patient_notes_skipped: int = 0
    old_patient_notes_null_patients: int = 0
    old_patient_notes_date_min: str | None = None
    old_patient_notes_date_max: str | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def import_r4_charting(
    session: Session,
    source: R4Source,
    actor_id: int,
    legacy_source: str = "r4",
    patients_from: int | None = None,
    patients_to: int | None = None,
    limit: int | None = None,
    ensure_patient_mappings: bool = True,
) -> ChartingImportStats:
    stats = ChartingImportStats()
    if ensure_patient_mappings:
        ensure_mappings_for_range(
            session,
            source,
            actor_id,
            patients_from,
            patients_to,
            legacy_source=legacy_source,
        )
        if (
            patients_from is not None
            and patients_to is not None
            and patients_from == patients_to
            and not mapping_exists(session, legacy_source, patients_from)
        ):
            raise RuntimeError(
                "Missing patient mapping for patient_code "
                f"{patients_from}. Run patients import first."
            )
    mapped_patient_cache: dict[int, bool] = {}
    seen_perio_probe_keys: set[str] = set()
    imported_patient_codes: set[int] = set()

    for system in source.list_tooth_systems(limit=limit):
        _upsert_tooth_system(session, system, actor_id, legacy_source, stats)
    for surface in source.list_tooth_surfaces(limit=limit):
        _upsert_tooth_surface(session, surface, actor_id, legacy_source, stats)
    for action in source.list_chart_healing_actions(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        _track_patient_code(
            session, legacy_source, action.patient_code, mapped_patient_cache, imported_patient_codes
        )
        _upsert_chart_healing_action(session, action, actor_id, legacy_source, stats)
    for entry in source.list_bpe_entries(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        _track_patient_code(
            session, legacy_source, entry.patient_code, mapped_patient_cache, imported_patient_codes
        )
        _upsert_bpe_entry(session, entry, actor_id, legacy_source, stats)
    for furcation in source.list_bpe_furcations(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        if furcation.patient_code is None:
            stats.bpe_furcations_unlinked_patients += 1
            stats.bpe_furcations_skipped += 1
            _log_unlinked_patient("bpe_furcations", furcation.furcation_id, "null")
            continue
        if furcation.patient_code is not None and not _is_patient_mapped(
            session,
            legacy_source,
            furcation.patient_code,
            mapped_patient_cache,
        ):
            stats.bpe_furcations_unlinked_patients += 1
            stats.bpe_furcations_skipped += 1
            _log_unlinked_patient("bpe_furcations", furcation.furcation_id, furcation.patient_code)
            continue
        _track_patient_code(
            session,
            legacy_source,
            furcation.patient_code,
            mapped_patient_cache,
            imported_patient_codes,
        )
        _upsert_bpe_furcation(session, furcation, actor_id, legacy_source, stats)
    for probe in source.list_perio_probes(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        stats.perio_probes_seen += 1
        if probe.patient_code is None:
            stats.perio_probes_null_patients += 1
            stats.perio_probes_unlinked_patients += 1
            stats.perio_probes_skipped += 1
            _log_unlinked_patient("perio_probes", probe.trans_id, "null")
            _append_sample(stats.perio_probes_sample_unlinked, _build_perio_probe_key(probe))
            continue
        if probe.patient_code is not None and not _is_patient_mapped(
            session,
            legacy_source,
            probe.patient_code,
            mapped_patient_cache,
        ):
            stats.perio_probes_unmapped_patients += 1
            stats.perio_probes_unlinked_patients += 1
            stats.perio_probes_skipped += 1
            _log_unlinked_patient("perio_probes", probe.trans_id, probe.patient_code)
            _append_sample(stats.perio_probes_sample_unmapped, _build_perio_probe_key(probe))
            continue
        _track_patient_code(
            session, legacy_source, probe.patient_code, mapped_patient_cache, imported_patient_codes
        )
        legacy_key = _build_perio_probe_key(probe)
        if legacy_key in seen_perio_probe_keys:
            stats.perio_probes_skipped_duplicate += 1
            stats.perio_probes_skipped += 1
            _append_sample(stats.perio_probes_sample_duplicate, legacy_key)
            continue
        seen_perio_probe_keys.add(legacy_key)
        _upsert_perio_probe(session, probe, actor_id, legacy_source, stats)
    for plaque in source.list_perio_plaque(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        if plaque.patient_code is None:
            stats.perio_plaque_null_patients += 1
            stats.perio_plaque_unlinked_patients += 1
            stats.perio_plaque_skipped += 1
            _log_unlinked_patient("perio_plaque", plaque.trans_id, "null")
            continue
        if plaque.patient_code is not None and not _is_patient_mapped(
            session,
            legacy_source,
            plaque.patient_code,
            mapped_patient_cache,
        ):
            stats.perio_plaque_unmapped_patients += 1
            stats.perio_plaque_unlinked_patients += 1
            stats.perio_plaque_skipped += 1
            _log_unlinked_patient("perio_plaque", plaque.trans_id, plaque.patient_code)
            continue
        _track_patient_code(
            session, legacy_source, plaque.patient_code, mapped_patient_cache, imported_patient_codes
        )
        _upsert_perio_plaque(session, plaque, actor_id, legacy_source, stats)
    for note in source.list_patient_notes(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        _track_patient_code(
            session, legacy_source, note.patient_code, mapped_patient_cache, imported_patient_codes
        )
        _upsert_patient_note(session, note, actor_id, legacy_source, stats)
    for fixed_note in source.list_fixed_notes(limit=limit):
        _upsert_fixed_note(session, fixed_note, actor_id, legacy_source, stats)
    for category in source.list_note_categories(limit=limit):
        _upsert_note_category(session, category, actor_id, legacy_source, stats)
    for note in source.list_treatment_notes(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        _track_patient_code(
            session, legacy_source, note.patient_code, mapped_patient_cache, imported_patient_codes
        )
        _upsert_treatment_note(session, note, actor_id, legacy_source, stats)
    for note in source.list_temporary_notes(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        _track_patient_code(
            session, legacy_source, note.patient_code, mapped_patient_cache, imported_patient_codes
        )
        _upsert_temporary_note(session, note, actor_id, legacy_source, stats)
    for note in source.list_old_patient_notes(
        patients_from=patients_from,
        patients_to=patients_to,
        limit=limit,
    ):
        _track_patient_code(
            session, legacy_source, note.patient_code, mapped_patient_cache, imported_patient_codes
        )
        _upsert_old_patient_note(session, note, actor_id, legacy_source, stats)

    _record_charting_import_state(
        session,
        legacy_source,
        imported_patient_codes,
        actor_id,
    )

    return stats


def _upsert_tooth_system(
    session: Session,
    system: R4ToothSystemPayload,
    actor_id: int,
    legacy_source: str,
    stats: ChartingImportStats,
) -> None:
    existing = session.scalar(
        select(R4ToothSystem).where(
            R4ToothSystem.legacy_source == legacy_source,
            R4ToothSystem.legacy_tooth_system_id == system.tooth_system_id,
        )
    )
    updates = {
        "name": _clean_text(system.name),
        "description": _clean_text(system.description),
        "sort_order": system.sort_order,
        "is_default": system.is_default,
        "updated_by_user_id": actor_id,
    }
    if existing:
        updated = _apply_updates(existing, updates)
        if updated:
            stats.tooth_systems_updated += 1
        else:
            stats.tooth_systems_skipped += 1
        return

    row = R4ToothSystem(
        legacy_source=legacy_source,
        legacy_tooth_system_id=system.tooth_system_id,
        created_by_user_id=actor_id,
        **updates,
    )
    session.add(row)
    stats.tooth_systems_created += 1


def _upsert_tooth_surface(
    session: Session,
    surface: R4ToothSurfacePayload,
    actor_id: int,
    legacy_source: str,
    stats: ChartingImportStats,
) -> None:
    existing = session.scalar(
        select(R4ToothSurface).where(
            R4ToothSurface.legacy_source == legacy_source,
            R4ToothSurface.legacy_tooth_id == surface.tooth_id,
            R4ToothSurface.legacy_surface_no == surface.surface_no,
        )
    )
    updates = {
        "label": _clean_text(surface.label),
        "short_label": _clean_text(surface.short_label),
        "sort_order": surface.sort_order,
        "updated_by_user_id": actor_id,
    }
    if existing:
        updated = _apply_updates(existing, updates)
        if updated:
            stats.tooth_surfaces_updated += 1
        else:
            stats.tooth_surfaces_skipped += 1
        return

    row = R4ToothSurface(
        legacy_source=legacy_source,
        legacy_tooth_id=surface.tooth_id,
        legacy_surface_no=surface.surface_no,
        created_by_user_id=actor_id,
        **updates,
    )
    session.add(row)
    stats.tooth_surfaces_created += 1


def _upsert_chart_healing_action(
    session: Session,
    action: R4ChartHealingActionPayload,
    actor_id: int,
    legacy_source: str,
    stats: ChartingImportStats,
) -> None:
    existing = session.scalar(
        select(R4ChartHealingAction).where(
            R4ChartHealingAction.legacy_source == legacy_source,
            R4ChartHealingAction.legacy_action_id == action.action_id,
        )
    )
    if action.patient_code is None:
        stats.chart_actions_null_patients += 1
    updates = {
        "legacy_patient_code": action.patient_code,
        "appointment_need_id": action.appointment_need_id,
        "tp_number": action.tp_number,
        "tp_item": action.tp_item,
        "code_id": action.code_id,
        "action_date": _normalize_datetime(action.action_date),
        "action_type": _clean_text(action.action_type),
        "tooth": action.tooth,
        "surface": action.surface,
        "status": _clean_text(action.status),
        "notes": _clean_text(action.notes),
        "user_code": action.user_code,
        "updated_by_user_id": actor_id,
    }
    if existing:
        updated = _apply_updates(existing, updates)
        if updated:
            stats.chart_actions_updated += 1
        else:
            stats.chart_actions_skipped += 1
        return

    row = R4ChartHealingAction(
        legacy_source=legacy_source,
        legacy_action_id=action.action_id,
        created_by_user_id=actor_id,
        **updates,
    )
    session.add(row)
    stats.chart_actions_created += 1


def _upsert_bpe_entry(
    session: Session,
    entry: R4BPEEntryPayload,
    actor_id: int,
    legacy_source: str,
    stats: ChartingImportStats,
) -> None:
    legacy_key = _build_bpe_key(entry)
    existing = session.scalar(
        select(R4BPEEntry).where(
            R4BPEEntry.legacy_source == legacy_source,
            R4BPEEntry.legacy_bpe_key == legacy_key,
        )
    )
    if entry.patient_code is None:
        stats.bpe_null_patients += 1
    _maybe_update_range(stats, "bpe", entry.recorded_at)
    updates = {
        "legacy_bpe_id": entry.bpe_id,
        "legacy_patient_code": entry.patient_code,
        "recorded_at": _normalize_datetime(entry.recorded_at),
        "sextant_1": entry.sextant_1,
        "sextant_2": entry.sextant_2,
        "sextant_3": entry.sextant_3,
        "sextant_4": entry.sextant_4,
        "sextant_5": entry.sextant_5,
        "sextant_6": entry.sextant_6,
        "notes": _clean_text(entry.notes),
        "user_code": entry.user_code,
        "updated_by_user_id": actor_id,
    }
    if existing:
        updated = _apply_updates(existing, updates)
        if updated:
            stats.bpe_updated += 1
        else:
            stats.bpe_skipped += 1
        return

    row = R4BPEEntry(
        legacy_source=legacy_source,
        legacy_bpe_key=legacy_key,
        created_by_user_id=actor_id,
        **updates,
    )
    session.add(row)
    stats.bpe_created += 1


def _upsert_bpe_furcation(
    session: Session,
    furcation: R4BPEFurcationPayload,
    actor_id: int,
    legacy_source: str,
    stats: ChartingImportStats,
) -> None:
    legacy_key = _build_bpe_furcation_key(furcation)
    existing = session.scalar(
        select(R4BPEFurcation).where(
            R4BPEFurcation.legacy_source == legacy_source,
            R4BPEFurcation.legacy_bpe_furcation_key == legacy_key,
        )
    )
    updates = {
        "legacy_bpe_id": furcation.bpe_id,
        "legacy_patient_code": furcation.patient_code,
        "tooth": furcation.tooth,
        "furcation": furcation.furcation,
        "sextant": furcation.sextant,
        "recorded_at": _normalize_datetime(furcation.recorded_at),
        "notes": _clean_text(furcation.notes),
        "user_code": furcation.user_code,
        "updated_by_user_id": actor_id,
    }
    if existing:
        updated = _apply_updates(existing, updates)
        if updated:
            stats.bpe_furcations_updated += 1
        else:
            stats.bpe_furcations_skipped += 1
        return

    row = R4BPEFurcation(
        legacy_source=legacy_source,
        legacy_bpe_furcation_key=legacy_key,
        created_by_user_id=actor_id,
        **updates,
    )
    session.add(row)
    stats.bpe_furcations_created += 1


def _upsert_perio_probe(
    session: Session,
    probe: R4PerioProbePayload,
    actor_id: int,
    legacy_source: str,
    stats: ChartingImportStats,
) -> None:
    legacy_key = _build_perio_probe_key(probe)
    existing = session.scalar(
        select(R4PerioProbe).where(
            R4PerioProbe.legacy_source == legacy_source,
            R4PerioProbe.legacy_probe_key == legacy_key,
        )
    )
    updates = {
        "legacy_trans_id": probe.trans_id,
        "legacy_patient_code": probe.patient_code,
        "tooth": probe.tooth,
        "probing_point": probe.probing_point,
        "depth": probe.depth,
        "bleeding": probe.bleeding,
        "plaque": probe.plaque,
        "recorded_at": _normalize_datetime(probe.recorded_at),
        "updated_by_user_id": actor_id,
    }
    if existing:
        updated = _apply_updates(existing, updates)
        if updated:
            stats.perio_probes_updated += 1
        else:
            stats.perio_probes_skipped += 1
        return

    row = R4PerioProbe(
        legacy_source=legacy_source,
        legacy_probe_key=legacy_key,
        created_by_user_id=actor_id,
        **updates,
    )
    session.add(row)
    stats.perio_probes_created += 1


def _upsert_perio_plaque(
    session: Session,
    plaque: R4PerioPlaquePayload,
    actor_id: int,
    legacy_source: str,
    stats: ChartingImportStats,
) -> None:
    legacy_key = _build_perio_plaque_key(plaque)
    existing = session.scalar(
        select(R4PerioPlaque).where(
            R4PerioPlaque.legacy_source == legacy_source,
            R4PerioPlaque.legacy_plaque_key == legacy_key,
        )
    )
    updates = {
        "legacy_trans_id": plaque.trans_id,
        "legacy_patient_code": plaque.patient_code,
        "tooth": plaque.tooth,
        "plaque": plaque.plaque,
        "bleeding": plaque.bleeding,
        "recorded_at": _normalize_datetime(plaque.recorded_at),
        "updated_by_user_id": actor_id,
    }
    if existing:
        updated = _apply_updates(existing, updates)
        if updated:
            stats.perio_plaque_updated += 1
        else:
            stats.perio_plaque_skipped += 1
        return

    row = R4PerioPlaque(
        legacy_source=legacy_source,
        legacy_plaque_key=legacy_key,
        created_by_user_id=actor_id,
        **updates,
    )
    session.add(row)
    stats.perio_plaque_created += 1


def _upsert_patient_note(
    session: Session,
    note: R4PatientNotePayload,
    actor_id: int,
    legacy_source: str,
    stats: ChartingImportStats,
) -> None:
    legacy_key = _build_patient_note_key(note)
    existing = session.scalar(
        select(R4PatientNote).where(
            R4PatientNote.legacy_source == legacy_source,
            R4PatientNote.legacy_note_key == legacy_key,
        )
    )
    if note.patient_code is None:
        stats.patient_notes_null_patients += 1
    _maybe_update_range(stats, "patient_notes", note.note_date)
    updates = {
        "legacy_patient_code": note.patient_code,
        "legacy_note_number": note.note_number,
        "note_date": _normalize_datetime(note.note_date),
        "note": _clean_text(note.note),
        "tooth": note.tooth,
        "surface": note.surface,
        "category_number": note.category_number,
        "fixed_note_code": note.fixed_note_code,
        "user_code": note.user_code,
        "updated_by_user_id": actor_id,
    }
    if existing:
        updated = _apply_updates(existing, updates)
        if updated:
            stats.patient_notes_updated += 1
        else:
            stats.patient_notes_skipped += 1
        return

    row = R4PatientNote(
        legacy_source=legacy_source,
        legacy_note_key=legacy_key,
        created_by_user_id=actor_id,
        **updates,
    )
    session.add(row)
    stats.patient_notes_created += 1


def _upsert_fixed_note(
    session: Session,
    note: R4FixedNotePayload,
    actor_id: int,
    legacy_source: str,
    stats: ChartingImportStats,
) -> None:
    existing = session.scalar(
        select(R4FixedNote).where(
            R4FixedNote.legacy_source == legacy_source,
            R4FixedNote.legacy_fixed_note_code == note.fixed_note_code,
        )
    )
    updates = {
        "category_number": note.category_number,
        "description": _clean_text(note.description),
        "note": _clean_text(note.note),
        "tooth": note.tooth,
        "surface": note.surface,
        "updated_by_user_id": actor_id,
    }
    if existing:
        updated = _apply_updates(existing, updates)
        if updated:
            stats.fixed_notes_updated += 1
        else:
            stats.fixed_notes_skipped += 1
        return

    row = R4FixedNote(
        legacy_source=legacy_source,
        legacy_fixed_note_code=note.fixed_note_code,
        created_by_user_id=actor_id,
        **updates,
    )
    session.add(row)
    stats.fixed_notes_created += 1


def _upsert_note_category(
    session: Session,
    category: R4NoteCategoryPayload,
    actor_id: int,
    legacy_source: str,
    stats: ChartingImportStats,
) -> None:
    existing = session.scalar(
        select(R4NoteCategory).where(
            R4NoteCategory.legacy_source == legacy_source,
            R4NoteCategory.legacy_category_number == category.category_number,
        )
    )
    updates = {
        "description": _clean_text(category.description),
        "updated_by_user_id": actor_id,
    }
    if existing:
        updated = _apply_updates(existing, updates)
        if updated:
            stats.note_categories_updated += 1
        else:
            stats.note_categories_skipped += 1
        return

    row = R4NoteCategory(
        legacy_source=legacy_source,
        legacy_category_number=category.category_number,
        created_by_user_id=actor_id,
        **updates,
    )
    session.add(row)
    stats.note_categories_created += 1


def _upsert_treatment_note(
    session: Session,
    note: R4TreatmentNotePayload,
    actor_id: int,
    legacy_source: str,
    stats: ChartingImportStats,
) -> None:
    existing = session.scalar(
        select(R4TreatmentNote).where(
            R4TreatmentNote.legacy_source == legacy_source,
            R4TreatmentNote.legacy_treatment_note_id == note.note_id,
        )
    )
    if note.patient_code is None:
        stats.treatment_notes_null_patients += 1
    _maybe_update_range(stats, "treatment_notes", note.note_date)
    updates = {
        "legacy_patient_code": note.patient_code,
        "tp_number": note.tp_number,
        "tp_item": note.tp_item,
        "note": _clean_text(note.note),
        "note_date": _normalize_datetime(note.note_date),
        "user_code": note.user_code,
        "updated_by_user_id": actor_id,
    }
    if existing:
        updated = _apply_updates(existing, updates)
        if updated:
            stats.treatment_notes_updated += 1
        else:
            stats.treatment_notes_skipped += 1
        return

    row = R4TreatmentNote(
        legacy_source=legacy_source,
        legacy_treatment_note_id=note.note_id,
        created_by_user_id=actor_id,
        **updates,
    )
    session.add(row)
    stats.treatment_notes_created += 1


def _upsert_temporary_note(
    session: Session,
    note: R4TemporaryNotePayload,
    actor_id: int,
    legacy_source: str,
    stats: ChartingImportStats,
) -> None:
    existing = session.scalar(
        select(R4TemporaryNote).where(
            R4TemporaryNote.legacy_source == legacy_source,
            R4TemporaryNote.legacy_patient_code == note.patient_code,
        )
    )
    updates = {
        "note": _clean_text(note.note),
        "legacy_updated_at": _normalize_datetime(note.legacy_updated_at),
        "user_code": note.user_code,
        "updated_by_user_id": actor_id,
    }
    if existing:
        updated = _apply_updates(existing, updates)
        if updated:
            stats.temporary_notes_updated += 1
        else:
            stats.temporary_notes_skipped += 1
        return

    row = R4TemporaryNote(
        legacy_source=legacy_source,
        legacy_patient_code=note.patient_code,
        created_by_user_id=actor_id,
        **updates,
    )
    session.add(row)
    stats.temporary_notes_created += 1


def _upsert_old_patient_note(
    session: Session,
    note: R4OldPatientNotePayload,
    actor_id: int,
    legacy_source: str,
    stats: ChartingImportStats,
) -> None:
    legacy_key = _build_old_patient_note_key(note)
    existing = session.scalar(
        select(R4OldPatientNote).where(
            R4OldPatientNote.legacy_source == legacy_source,
            R4OldPatientNote.legacy_note_key == legacy_key,
        )
    )
    if note.patient_code is None:
        stats.old_patient_notes_null_patients += 1
    _maybe_update_range(stats, "old_patient_notes", note.note_date)
    updates = {
        "legacy_patient_code": note.patient_code,
        "legacy_note_number": note.note_number,
        "note_date": _normalize_datetime(note.note_date),
        "note": _clean_text(note.note),
        "tooth": note.tooth,
        "surface": note.surface,
        "category_number": note.category_number,
        "fixed_note_code": note.fixed_note_code,
        "user_code": note.user_code,
        "updated_by_user_id": actor_id,
    }
    if existing:
        updated = _apply_updates(existing, updates)
        if updated:
            stats.old_patient_notes_updated += 1
        else:
            stats.old_patient_notes_skipped += 1
        return

    row = R4OldPatientNote(
        legacy_source=legacy_source,
        legacy_note_key=legacy_key,
        created_by_user_id=actor_id,
        **updates,
    )
    session.add(row)
    stats.old_patient_notes_created += 1


def _build_bpe_key(entry: R4BPEEntryPayload) -> str:
    if entry.bpe_id is not None:
        return str(entry.bpe_id)
    return _build_legacy_key(entry.patient_code, entry.recorded_at)


def _build_bpe_furcation_key(entry: R4BPEFurcationPayload) -> str:
    if entry.furcation_id is not None:
        return str(entry.furcation_id)
    return _build_legacy_key(entry.bpe_id, entry.patient_code, entry.tooth, entry.furcation)


def _build_perio_probe_key(entry: R4PerioProbePayload) -> str:
    return _build_legacy_key(entry.trans_id, entry.tooth, entry.probing_point)


def _build_perio_plaque_key(entry: R4PerioPlaquePayload) -> str:
    return _build_legacy_key(entry.trans_id, entry.tooth)


def _build_patient_note_key(note: R4PatientNotePayload) -> str:
    if note.note_number is not None:
        return _build_legacy_key(note.patient_code, note.note_number)
    return _build_legacy_key(note.patient_code, note.note_date)


def _track_patient_code(
    session: Session,
    legacy_source: str,
    patient_code: int | None,
    cache: dict[int, bool],
    imported: set[int],
) -> None:
    if patient_code is None:
        return
    if _is_patient_mapped(session, legacy_source, patient_code, cache):
        imported.add(patient_code)


def _record_charting_import_state(
    session: Session,
    legacy_source: str,
    patient_codes: set[int],
    actor_id: int,
) -> None:
    if not patient_codes:
        return
    mappings = session.scalars(
        select(R4PatientMapping).where(
            R4PatientMapping.legacy_source == legacy_source,
            R4PatientMapping.legacy_patient_code.in_(patient_codes),
        )
    ).all()
    manual_rows = session.execute(
        select(R4ManualMapping.legacy_patient_code, R4ManualMapping.target_patient_id).where(
            R4ManualMapping.legacy_source == legacy_source,
            R4ManualMapping.legacy_patient_code.in_(patient_codes),
        )
    ).all()
    if not mappings and not manual_rows:
        return
    now = datetime.now(timezone.utc)
    mapping_entries: list[tuple[int, int]] = [
        (int(mapping.legacy_patient_code), int(mapping.patient_id)) for mapping in mappings
    ]
    mapping_entries.extend(
        [(int(code), int(patient_id)) for code, patient_id in manual_rows]
    )
    for legacy_patient_code, patient_id in mapping_entries:
        record = session.scalar(
            select(R4ChartingImportState).where(
                R4ChartingImportState.patient_id == patient_id
            )
        )
        if record:
            record.legacy_patient_code = legacy_patient_code
            record.last_imported_at = now
            record.updated_by_user_id = actor_id
        else:
            session.add(
                R4ChartingImportState(
                    patient_id=patient_id,
                    legacy_patient_code=legacy_patient_code,
                    last_imported_at=now,
                    created_by_user_id=actor_id,
                )
            )


def _is_patient_mapped(
    session: Session,
    legacy_source: str,
    patient_code: int,
    cache: dict[int, bool],
) -> bool:
    cached = cache.get(patient_code)
    if cached is not None:
        return cached
    mapped = (
        resolve_patient_id_from_r4_patient_code(
            session, patient_code, legacy_source=legacy_source
        )
        is not None
    )
    cache[patient_code] = mapped
    return mapped


def _log_unlinked_patient(entity: str, legacy_key: int | str | None, patient_code: int | str) -> None:
    print(
        "r4_import_skip_unlinked_patient "
        f"entity={entity} legacy_key={legacy_key} patient_code={patient_code}"
    )


def _append_sample(bucket: list[str], value: str | None, limit: int = 5) -> None:
    if value is None:
        return
    if len(bucket) >= limit:
        return
    bucket.append(str(value))


def _build_old_patient_note_key(note: R4OldPatientNotePayload) -> str:
    return _build_legacy_key(note.patient_code, note.note_number, note.note_date)


def _build_legacy_key(*parts: object) -> str:
    safe_parts = ["null" if part is None else str(part) for part in parts]
    return ":".join(safe_parts)


def _maybe_update_range(stats: ChartingImportStats, prefix: str, value: datetime | None) -> None:
    if value is None:
        return
    normalized = _normalize_datetime(value)
    if normalized is None:
        return
    value_str = normalized.isoformat()
    min_key = f"{prefix}_date_min"
    max_key = f"{prefix}_date_max"
    current_min = getattr(stats, min_key)
    current_max = getattr(stats, max_key)
    if current_min is None or value_str < current_min:
        setattr(stats, min_key, value_str)
    if current_max is None or value_str > current_max:
        setattr(stats, max_key, value_str)


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    microseconds = (value.microsecond // 1000) * 1000
    return value.replace(microsecond=microseconds)


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _apply_updates(model, updates: dict) -> bool:
    changed = False
    for field, value in updates.items():
        if getattr(model, field) != value:
            setattr(model, field, value)
            changed = True
    return changed
