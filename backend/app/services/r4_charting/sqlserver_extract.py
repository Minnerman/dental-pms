from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import hashlib
from typing import Iterable

from app.services.r4_charting.canonical_types import CanonicalRecordInput
from app.services.r4_charting.completed_treatment_findings_import import (
    collect_completed_treatment_finding_canonical_records,
)
from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource


_RESTORATIVE_TREATMENT_STATUS_DESCRIPTIONS = {
    "fillings",
    "fillings additional tooth items",
    "crown",
    "crowns/inlays additions",
    "inlay/crown add. tooth items",
    "root filling",
    "root fillings additional items",
    "implant",
    "post",
    "partial denture",
    "adjust denture",
    "dentures additional items",
    "dentures addl tooth items",
    "full upper denture",
    "full lower denture",
    "reline denture",
    "denture prior treatment",
    "bridge additions",
    "bridges additional tooth items",
    "abutment",
    "extraction",
    "extraction additional items",
    "extraction incl bone removal",
    "extraction of soft tissue",
}
_RESTORATIVE_SURFACE_VALID_MASK = 0b111111


@dataclass
class SqlServerExtractReport:
    missing_date: int = 0
    out_of_range: int = 0
    undated_included: int = 0
    restorative_missing_tooth: int = 0
    restorative_invalid_surface: int = 0
    restorative_status_ignored: int = 0
    restorative_not_completed: int = 0
    restorative_missing_code_id: int = 0
    missing_patient_code: int = 0
    missing_tooth: int = 0
    missing_code_id: int = 0
    out_of_window: int = 0
    restorative_classified: int = 0
    duplicate_key: int = 0
    included: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "missing_date": self.missing_date,
            "out_of_range": self.out_of_range,
            "undated_included": self.undated_included,
            "restorative_missing_tooth": self.restorative_missing_tooth,
            "restorative_invalid_surface": self.restorative_invalid_surface,
            "restorative_status_ignored": self.restorative_status_ignored,
            "restorative_not_completed": self.restorative_not_completed,
            "restorative_missing_code_id": self.restorative_missing_code_id,
            "missing_patient_code": self.missing_patient_code,
            "missing_tooth": self.missing_tooth,
            "missing_code_id": self.missing_code_id,
            "out_of_window": self.out_of_window,
            "restorative_classified": self.restorative_classified,
            "duplicate_key": self.duplicate_key,
            "included": self.included,
        }


class SqlServerChartingExtractor:
    """SELECT-only extractor for a bounded charting pilot.

    Sources used in Stage 129C:
    - dbo.BPE
    - dbo.PerioProbe
    """

    select_only = True

    def __init__(self, config: R4SqlServerConfig) -> None:
        config.require_enabled()
        config.require_readonly()
        self._source = R4SqlServerSource(config)

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
        records: list[CanonicalRecordInput] = []
        report = SqlServerExtractReport()
        domain_filter = {domain.strip().lower() for domain in (domains or []) if domain.strip()}

        def _include(*names: str) -> bool:
            if not domain_filter:
                return True
            return any(name.lower() in domain_filter for name in names)

        if _include("bpe", "bpe_entry"):
            for item in self._iter_bpe(
                patients_from=patients_from,
                patients_to=patients_to,
                patient_codes=patient_codes,
                limit=limit,
            ):
                recorded_at = item.recorded_at
                if not _date_in_range(recorded_at, date_from, date_to, report):
                    continue
                if item.bpe_id is not None:
                    source_id = str(item.bpe_id)
                else:
                    source_id = f"{item.patient_code}:{recorded_at}"
                records.append(
                    CanonicalRecordInput(
                        domain="bpe_entry",
                        r4_source="dbo.BPE",
                        r4_source_id=source_id,
                        legacy_patient_code=item.patient_code,
                        recorded_at=recorded_at,
                        entered_at=None,
                        tooth=None,
                        surface=None,
                        code_id=None,
                        status=None,
                        payload=item.model_dump() if hasattr(item, "model_dump") else item.dict(),
                    )
                )

        if _include("chart_healing_actions", "chart_healing_action") and hasattr(
            self._source, "list_chart_healing_actions"
        ):
            for item in self._iter_chart_healing_actions(
                patients_from=patients_from,
                patients_to=patients_to,
                patient_codes=patient_codes,
                limit=limit,
            ):
                recorded_at = item.action_date
                if date_from or date_to:
                    if recorded_at is None:
                        report.undated_included += 1
                    elif not _date_in_range(recorded_at, date_from, date_to, report):
                        continue
                records.append(
                    CanonicalRecordInput(
                        domain="chart_healing_action",
                        r4_source="dbo.ChartHealingActions",
                        r4_source_id=str(item.action_id),
                        legacy_patient_code=item.patient_code,
                        recorded_at=recorded_at,
                        entered_at=None,
                        tooth=item.tooth,
                        surface=item.surface,
                        code_id=item.code_id,
                        status=item.status,
                        payload=item.model_dump() if hasattr(item, "model_dump") else item.dict(),
                    )
                )

        if _include("perioprobe", "perio_probe"):
            for item in self._iter_perio_probes(
                patients_from=patients_from,
                patients_to=patients_to,
                patient_codes=patient_codes,
                limit=limit,
            ):
                recorded_at = item.recorded_at
                if date_from or date_to:
                    if recorded_at is None:
                        report.undated_included += 1
                    else:
                        if not _date_in_range(recorded_at, date_from, date_to, report):
                            continue
                source_id = f"{item.trans_id}:{item.tooth}:{item.probing_point}"
                records.append(
                    CanonicalRecordInput(
                        domain="perio_probe",
                        r4_source="dbo.PerioProbe",
                        r4_source_id=source_id,
                        legacy_patient_code=item.patient_code,
                        recorded_at=recorded_at,
                        entered_at=None,
                        tooth=item.tooth,
                        surface=None,
                        code_id=None,
                        status=None,
                        payload=item.model_dump() if hasattr(item, "model_dump") else item.dict(),
                    )
                )

        if _include("patient_notes", "patient_note"):
            for item in self._iter_patient_notes(
                patients_from=patients_from,
                patients_to=patients_to,
                patient_codes=patient_codes,
                limit=limit,
            ):
                note_date = item.note_date
                if not _date_in_range(note_date, date_from, date_to, report):
                    continue
                if item.note_number is not None:
                    source_id = str(item.note_number)
                else:
                    note_digest = hashlib.sha1((item.note or "").encode("utf-8")).hexdigest()[:16]
                    source_id = f"{item.patient_code}:{note_date}:{note_digest}"
                records.append(
                    CanonicalRecordInput(
                        domain="patient_note",
                        r4_source="dbo.PatientNotes",
                        r4_source_id=source_id,
                        legacy_patient_code=item.patient_code,
                        recorded_at=note_date,
                        entered_at=None,
                        tooth=item.tooth,
                        surface=item.surface,
                        code_id=item.fixed_note_code,
                        status=None,
                        payload=item.model_dump() if hasattr(item, "model_dump") else item.dict(),
                    )
                )

        if _include("treatment_notes", "treatment_note"):
            for item in self._iter_treatment_notes(
                patients_from=patients_from,
                patients_to=patients_to,
                patient_codes=patient_codes,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
            ):
                note_date = item.note_date
                if not _date_in_range(note_date, date_from, date_to, report):
                    continue
                if item.note_id is not None:
                    source_id = str(item.note_id)
                else:
                    note_digest = hashlib.sha1((item.note or "").encode("utf-8")).hexdigest()[:16]
                    source_id = f"{item.patient_code}:{note_date}:{note_digest}"
                records.append(
                    CanonicalRecordInput(
                        domain="treatment_note",
                        r4_source="dbo.TreatmentNotes",
                        r4_source_id=source_id,
                        legacy_patient_code=item.patient_code,
                        recorded_at=note_date,
                        entered_at=None,
                        tooth=None,
                        surface=None,
                        code_id=None,
                        status=None,
                        payload=item.model_dump() if hasattr(item, "model_dump") else item.dict(),
                    )
                )

        if _include("treatment_plans", "treatment_plan"):
            for item in self._iter_treatment_plans(
                patients_from=patients_from,
                patients_to=patients_to,
                patient_codes=patient_codes,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
            ):
                recorded_at = item.creation_date
                if date_from or date_to:
                    if recorded_at is None:
                        report.undated_included += 1
                    elif not _date_in_range(recorded_at, date_from, date_to, report):
                        continue
                if item.treatment_plan_id is not None:
                    source_id = str(item.treatment_plan_id)
                else:
                    source_id = f"{item.patient_code}:{item.tp_number}"
                records.append(
                    CanonicalRecordInput(
                        domain="treatment_plan",
                        r4_source="dbo.TreatmentPlans",
                        r4_source_id=source_id,
                        legacy_patient_code=item.patient_code,
                        recorded_at=recorded_at,
                        entered_at=item.acceptance_date,
                        tooth=None,
                        surface=None,
                        code_id=None,
                        status=str(item.status_code) if item.status_code is not None else None,
                        payload=item.model_dump() if hasattr(item, "model_dump") else item.dict(),
                    )
                )

        if _include("treatment_plan_items", "treatment_plan_item"):
            for item in self._iter_treatment_plan_items(
                patients_from=patients_from,
                patients_to=patients_to,
                patient_codes=patient_codes,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
            ):
                # Date semantics for TP items are anchored on the parent plan creation date.
                item_date = item.plan_creation_date or item.item_date or item.completed_date
                if not _date_in_range(item_date, date_from, date_to, report):
                    continue
                if item.tp_item_key is not None:
                    source_id = str(item.tp_item_key)
                else:
                    source_id = f"{item.patient_code}:{item.tp_number}:{item.tp_item}"
                records.append(
                    CanonicalRecordInput(
                        domain="treatment_plan_item",
                        r4_source="dbo.TreatmentPlanItems",
                        r4_source_id=source_id,
                        legacy_patient_code=item.patient_code,
                        recorded_at=item_date,
                        entered_at=None,
                        tooth=item.tooth,
                        surface=item.surface,
                        code_id=item.code_id,
                        status="completed" if item.completed else "planned",
                        payload=item.model_dump() if hasattr(item, "model_dump") else item.dict(),
                    )
                )

        if _include("restorative_treatments", "restorative_treatment") and hasattr(
            self._source, "list_restorative_treatments"
        ):
            for item in self._iter_restorative_treatments(
                patients_from=patients_from,
                patients_to=patients_to,
                patient_codes=patient_codes,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
            ):
                recorded_at = (
                    item.recorded_at
                    or item.completion_date
                    or item.transaction_date
                    or item.creation_date
                )
                if not _date_in_range(recorded_at, date_from, date_to, report):
                    continue
                if item.ref_id is not None:
                    source_id = str(item.ref_id)
                elif item.tp_item_key is not None:
                    source_id = f"tpitemkey:{item.tp_item_key}"
                elif item.patient_code is not None and item.tp_number is not None and item.tp_item is not None:
                    source_id = f"{item.patient_code}:{item.tp_number}:{item.tp_item}"
                elif (
                    item.patient_code is not None
                    and item.trans_code is not None
                    and recorded_at is not None
                ):
                    source_id = f"{item.patient_code}:{item.trans_code}:{recorded_at.isoformat()}"
                else:
                    source_id = f"{item.patient_code}:{item.code_id}:{item.tooth}:{item.surface}:{recorded_at}"
                status_norm = str(item.status_description or "").strip().lower()
                if status_norm not in _RESTORATIVE_TREATMENT_STATUS_DESCRIPTIONS:
                    report.restorative_status_ignored += 1
                    continue
                if not (item.completed or item.complete):
                    report.restorative_not_completed += 1
                    continue
                if item.tooth is None or item.tooth <= 0:
                    report.restorative_missing_tooth += 1
                    continue
                if item.code_id is None:
                    report.restorative_missing_code_id += 1
                    continue
                if not _is_valid_restorative_surface(item.surface):
                    report.restorative_invalid_surface += 1
                    continue
                status = item.status_description
                if not status and item.status_code is not None:
                    status = str(item.status_code)
                records.append(
                    CanonicalRecordInput(
                        domain="restorative_treatment",
                        r4_source="dbo.vwTreatments",
                        r4_source_id=source_id,
                        legacy_patient_code=item.patient_code,
                        recorded_at=recorded_at,
                        entered_at=item.acceptance_date,
                        tooth=item.tooth,
                        surface=item.surface,
                        code_id=item.code_id,
                        status=status,
                        payload=item.model_dump() if hasattr(item, "model_dump") else item.dict(),
                    )
                )

        if _include("completed_treatment_findings", "completed_treatment_finding") and hasattr(
            self._source, "list_completed_treatment_findings"
        ):
            findings_rows = self._iter_completed_treatment_findings(
                patients_from=patients_from,
                patients_to=patients_to,
                patient_codes=patient_codes,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
            )
            finding_records, findings_report = collect_completed_treatment_finding_canonical_records(
                findings_rows,
                date_from=date_from,
                date_to=date_to,
            )
            records.extend(finding_records)
            report.missing_patient_code += findings_report.missing_patient_code
            report.missing_tooth += findings_report.missing_tooth
            report.missing_code_id += findings_report.missing_code_id
            report.out_of_window += findings_report.out_of_window
            report.restorative_classified += findings_report.restorative_classified
            report.duplicate_key += findings_report.duplicate_key
            report.included += findings_report.included

        if _include("bpe_furcation", "bpe_furcations"):
            for row in self._iter_bpe_furcations(
                patients_from=patients_from,
                patients_to=patients_to,
                patient_codes=patient_codes,
                limit=limit,
            ):
                recorded_at = row.get("recorded_at")
                if not _date_in_range(recorded_at, date_from, date_to, report):
                    continue
                bpe_id = row.get("bpe_id")
                patient_code = row.get("patient_code")
                if bpe_id is not None:
                    source_id = str(bpe_id)
                elif row.get("pkey") is not None:
                    source_id = str(row.get("pkey"))
                else:
                    source_id = f"{patient_code}:{recorded_at}"
                records.append(
                    CanonicalRecordInput(
                        domain="bpe_furcation",
                        r4_source="dbo.BPEFurcation",
                        r4_source_id=source_id,
                        legacy_patient_code=int(patient_code) if patient_code is not None else None,
                        recorded_at=recorded_at,
                        entered_at=None,
                        tooth=None,
                        surface=None,
                        code_id=None,
                        status=None,
                        payload={
                            "bpe_id": bpe_id,
                            "pkey": row.get("pkey"),
                            "furcation_1": row.get("furcation_1"),
                            "furcation_2": row.get("furcation_2"),
                            "furcation_3": row.get("furcation_3"),
                            "furcation_4": row.get("furcation_4"),
                            "furcation_5": row.get("furcation_5"),
                            "furcation_6": row.get("furcation_6"),
                        },
                    )
                )

        return records, report.as_dict()

    def _iter_bpe(
        self,
        *,
        patients_from: int | None,
        patients_to: int | None,
        patient_codes: list[int] | None,
        limit: int | None,
    ):
        if not patient_codes:
            yield from self._source.list_bpe_entries(
                patients_from=patients_from,
                patients_to=patients_to,
                limit=limit,
            )
            return
        remaining = limit
        for batch in _chunk_codes(patient_codes, size=100):
            if remaining is not None and remaining <= 0:
                break
            batch_limit = remaining if remaining is not None else None
            for code in batch:
                if remaining is not None and remaining <= 0:
                    break
                for item in self._source.list_bpe_entries(
                    patients_from=code,
                    patients_to=code,
                    limit=batch_limit,
                ):
                    yield item
                    if remaining is not None:
                        remaining -= 1
                        batch_limit = remaining
                        if remaining <= 0:
                            break

    def _iter_perio_probes(
        self,
        *,
        patients_from: int | None,
        patients_to: int | None,
        patient_codes: list[int] | None,
        limit: int | None,
    ):
        if not patient_codes:
            yield from self._source.list_perio_probes(
                patients_from=patients_from,
                patients_to=patients_to,
                limit=limit,
            )
            return
        remaining = limit
        for batch in _chunk_codes(patient_codes, size=100):
            if remaining is not None and remaining <= 0:
                break
            batch_limit = remaining if remaining is not None else None
            for code in batch:
                if remaining is not None and remaining <= 0:
                    break
                for item in self._source.list_perio_probes(
                    patients_from=code,
                    patients_to=code,
                    limit=batch_limit,
                ):
                    yield item
                    if remaining is not None:
                        remaining -= 1
                        batch_limit = remaining
                        if remaining <= 0:
                            break

    def _iter_chart_healing_actions(
        self,
        *,
        patients_from: int | None,
        patients_to: int | None,
        patient_codes: list[int] | None,
        limit: int | None,
    ):
        if not hasattr(self._source, "list_chart_healing_actions"):
            return
        if not patient_codes:
            yield from self._source.list_chart_healing_actions(
                patients_from=patients_from,
                patients_to=patients_to,
                limit=limit,
            )
            return
        remaining = limit
        for batch in _chunk_codes(patient_codes, size=100):
            if remaining is not None and remaining <= 0:
                break
            batch_limit = remaining if remaining is not None else None
            for code in batch:
                if remaining is not None and remaining <= 0:
                    break
                for item in self._source.list_chart_healing_actions(
                    patients_from=code,
                    patients_to=code,
                    limit=batch_limit,
                ):
                    yield item
                    if remaining is not None:
                        remaining -= 1
                        batch_limit = remaining
                        if remaining <= 0:
                            break

    def _iter_patient_notes(
        self,
        *,
        patients_from: int | None,
        patients_to: int | None,
        patient_codes: list[int] | None,
        limit: int | None,
    ):
        if not patient_codes:
            yield from self._source.list_patient_notes(
                patients_from=patients_from,
                patients_to=patients_to,
                limit=limit,
            )
            return
        remaining = limit
        for batch in _chunk_codes(patient_codes, size=100):
            if remaining is not None and remaining <= 0:
                break
            batch_limit = remaining if remaining is not None else None
            for code in batch:
                if remaining is not None and remaining <= 0:
                    break
                for item in self._source.list_patient_notes(
                    patients_from=code,
                    patients_to=code,
                    limit=batch_limit,
                ):
                    yield item
                    if remaining is not None:
                        remaining -= 1
                        batch_limit = remaining
                        if remaining <= 0:
                            break

    def _iter_treatment_notes(
        self,
        *,
        patients_from: int | None,
        patients_to: int | None,
        patient_codes: list[int] | None,
        date_from: date | None,
        date_to: date | None,
        limit: int | None,
    ):
        if not patient_codes:
            yield from self._source.list_treatment_notes(
                patients_from=patients_from,
                patients_to=patients_to,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
            )
            return
        remaining = limit
        for batch in _chunk_codes(patient_codes, size=100):
            if remaining is not None and remaining <= 0:
                break
            batch_limit = remaining if remaining is not None else None
            for code in batch:
                if remaining is not None and remaining <= 0:
                    break
                for item in self._source.list_treatment_notes(
                    patients_from=code,
                    patients_to=code,
                    date_from=date_from,
                    date_to=date_to,
                    limit=batch_limit,
                ):
                    yield item
                    if remaining is not None:
                        remaining -= 1
                        batch_limit = remaining
                        if remaining <= 0:
                            break

    def _iter_treatment_plan_items(
        self,
        *,
        patients_from: int | None,
        patients_to: int | None,
        patient_codes: list[int] | None,
        date_from: date | None,
        date_to: date | None,
        limit: int | None,
    ):
        if not patient_codes:
            yield from self._source.list_treatment_plan_items(
                patients_from=patients_from,
                patients_to=patients_to,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
            )
            return
        remaining = limit
        for batch in _chunk_codes(patient_codes, size=100):
            if remaining is not None and remaining <= 0:
                break
            batch_limit = remaining if remaining is not None else None
            for code in batch:
                if remaining is not None and remaining <= 0:
                    break
                for item in self._source.list_treatment_plan_items(
                    patients_from=code,
                    patients_to=code,
                    date_from=date_from,
                    date_to=date_to,
                    limit=batch_limit,
                ):
                    yield item
                    if remaining is not None:
                        remaining -= 1
                        batch_limit = remaining
                        if remaining <= 0:
                            break

    def _iter_restorative_treatments(
        self,
        *,
        patients_from: int | None,
        patients_to: int | None,
        patient_codes: list[int] | None,
        date_from: date | None,
        date_to: date | None,
        limit: int | None,
    ):
        if not hasattr(self._source, "list_restorative_treatments"):
            return
        if not patient_codes:
            yield from self._source.list_restorative_treatments(
                patients_from=patients_from,
                patients_to=patients_to,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
                include_not_completed=True,
                require_tooth=False,
                status_descriptions=None,
            )
            return
        remaining = limit
        for batch in _chunk_codes(patient_codes, size=100):
            if remaining is not None and remaining <= 0:
                break
            batch_limit = remaining if remaining is not None else None
            for code in batch:
                if remaining is not None and remaining <= 0:
                    break
                for item in self._source.list_restorative_treatments(
                    patients_from=code,
                    patients_to=code,
                    date_from=date_from,
                    date_to=date_to,
                    limit=batch_limit,
                    include_not_completed=True,
                    require_tooth=False,
                    status_descriptions=None,
                ):
                    yield item
                    if remaining is not None:
                        remaining -= 1
                        batch_limit = remaining
                        if remaining <= 0:
                            break

    def _iter_completed_treatment_findings(
        self,
        *,
        patients_from: int | None,
        patients_to: int | None,
        patient_codes: list[int] | None,
        date_from: date | None,
        date_to: date | None,
        limit: int | None,
    ):
        if not hasattr(self._source, "list_completed_treatment_findings"):
            return
        if not patient_codes:
            yield from self._source.list_completed_treatment_findings(
                patients_from=patients_from,
                patients_to=patients_to,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
            )
            return
        remaining = limit
        for batch in _chunk_codes(patient_codes, size=100):
            if remaining is not None and remaining <= 0:
                break
            batch_limit = remaining if remaining is not None else None
            for code in batch:
                if remaining is not None and remaining <= 0:
                    break
                for item in self._source.list_completed_treatment_findings(
                    patients_from=code,
                    patients_to=code,
                    date_from=date_from,
                    date_to=date_to,
                    limit=batch_limit,
                ):
                    yield item
                    if remaining is not None:
                        remaining -= 1
                        batch_limit = remaining
                        if remaining <= 0:
                            break

    def _iter_treatment_plans(
        self,
        *,
        patients_from: int | None,
        patients_to: int | None,
        patient_codes: list[int] | None,
        date_from: date | None,
        date_to: date | None,
        limit: int | None,
    ):
        if not patient_codes:
            yield from self._source.list_treatment_plans(
                patients_from=patients_from,
                patients_to=patients_to,
                date_from=date_from,
                date_to=date_to,
                include_undated=True,
                limit=limit,
            )
            return
        remaining = limit
        for batch in _chunk_codes(patient_codes, size=100):
            if remaining is not None and remaining <= 0:
                break
            batch_limit = remaining if remaining is not None else None
            for code in batch:
                if remaining is not None and remaining <= 0:
                    break
                for item in self._source.list_treatment_plans(
                    patients_from=code,
                    patients_to=code,
                    date_from=date_from,
                    date_to=date_to,
                    include_undated=True,
                    limit=batch_limit,
                ):
                    yield item
                    if remaining is not None:
                        remaining -= 1
                        batch_limit = remaining
                        if remaining <= 0:
                            break

    def _iter_bpe_furcations(
        self,
        *,
        patients_from: int | None,
        patients_to: int | None,
        patient_codes: list[int] | None,
        limit: int | None,
    ):
        if not hasattr(self._source, "_pick_column") or not hasattr(self._source, "_query"):
            return
        bpe_id_col = self._source._pick_column("BPE", ["BPEID", "BPEId", "ID", "RefId", "RefID"])  # noqa: SLF001
        patient_col = self._source._pick_column("BPE", ["PatientCode"])  # noqa: SLF001
        date_col = self._source._pick_column("BPE", ["Date", "BPEDate", "RecordedDate", "EntryDate"])  # noqa: SLF001
        furcation_bpe_col = self._source._pick_column("BPEFurcation", ["BPEID", "BPEId"])  # noqa: SLF001
        pkey_col = self._source._pick_column("BPEFurcation", ["pKey", "ID", "BPEFurcationID"])  # noqa: SLF001
        if not (bpe_id_col and patient_col and furcation_bpe_col):
            return
        fur_cols: list[tuple[str, str]] = []
        for idx in range(1, 7):
            col = self._source._pick_column("BPEFurcation", [f"Furcation{idx}"])  # noqa: SLF001
            if col:
                fur_cols.append((col, f"furcation_{idx}"))
        if not fur_cols:
            return

        def _query_rows_for_code(code: int, batch_limit: int | None):
            select_cols = [
                f"b.{bpe_id_col} AS bpe_id",
                f"b.{patient_col} AS patient_code",
            ]
            if date_col:
                select_cols.append(f"b.{date_col} AS recorded_at")
            if pkey_col:
                select_cols.append(f"f.{pkey_col} AS pkey")
            for src_col, alias in fur_cols:
                select_cols.append(f"f.{src_col} AS {alias}")
            query = (
                f"SELECT TOP (?) {', '.join(select_cols)} "
                "FROM dbo.BPE b WITH (NOLOCK) "
                "JOIN dbo.BPEFurcation f WITH (NOLOCK) "
                f"ON f.{furcation_bpe_col} = b.{bpe_id_col} "
                f"WHERE b.{patient_col} = ? "
                + (
                    f"ORDER BY b.{date_col} ASC, b.{bpe_id_col} ASC"
                    if date_col
                    else f"ORDER BY b.{bpe_id_col} ASC"
                )
            )
            params = [batch_limit if batch_limit is not None else 1000000, code]
            return self._source._query(query, params)  # noqa: SLF001

        if not patient_codes:
            if patients_from is None or patients_to is None:
                return
            select_cols = [
                f"b.{bpe_id_col} AS bpe_id",
                f"b.{patient_col} AS patient_code",
            ]
            if date_col:
                select_cols.append(f"b.{date_col} AS recorded_at")
            if pkey_col:
                select_cols.append(f"f.{pkey_col} AS pkey")
            for src_col, alias in fur_cols:
                select_cols.append(f"f.{src_col} AS {alias}")
            query = (
                f"SELECT TOP (?) {', '.join(select_cols)} "
                "FROM dbo.BPE b WITH (NOLOCK) "
                "JOIN dbo.BPEFurcation f WITH (NOLOCK) "
                f"ON f.{furcation_bpe_col} = b.{bpe_id_col} "
                f"WHERE b.{patient_col} >= ? AND b.{patient_col} <= ? "
                + (
                    f"ORDER BY b.{date_col} ASC, b.{bpe_id_col} ASC"
                    if date_col
                    else f"ORDER BY b.{bpe_id_col} ASC"
                )
            )
            rows = self._source._query(  # noqa: SLF001
                query,
                [limit if limit is not None else 1000000, patients_from, patients_to],
            )
            for row in rows:
                yield row
            return

        remaining = limit
        for batch in _chunk_codes(patient_codes, size=100):
            if remaining is not None and remaining <= 0:
                break
            for code in batch:
                if remaining is not None and remaining <= 0:
                    break
                batch_limit = remaining if remaining is not None else None
                for row in _query_rows_for_code(code, batch_limit):
                    yield row
                    if remaining is not None:
                        remaining -= 1
                        if remaining <= 0:
                            break


def get_distinct_bpe_patient_codes(
    charting_from: date | str,
    charting_to: date | str,
    limit: int = 50,
) -> list[int]:
    if limit <= 0:
        return []
    date_from = _coerce_date(charting_from)
    date_to = _coerce_date(charting_to)
    if date_to < date_from:
        raise ValueError("charting_to must be on or after charting_from")

    config = R4SqlServerConfig.from_env()
    config.require_enabled()
    config.require_readonly()
    source = R4SqlServerSource(config)
    source.ensure_select_only()

    patient_col = source._pick_column("BPE", ["PatientCode"])  # noqa: SLF001
    date_col = source._pick_column(  # noqa: SLF001
        "BPE", ["Date", "BPEDate", "RecordedDate", "EntryDate"]
    )
    if not patient_col or not date_col:
        raise RuntimeError("BPE missing PatientCode/Date columns; cannot fetch distinct codes.")

    rows = source._query(  # noqa: SLF001
        (
            "SELECT TOP (?) "
            f"{patient_col} AS patient_code "
            "FROM dbo.BPE WITH (NOLOCK) "
            f"WHERE {patient_col} IS NOT NULL AND {date_col} >= ? AND {date_col} < ? "
            f"GROUP BY {patient_col} "
            f"ORDER BY MAX({date_col}) DESC, {patient_col} ASC"
        ),
        [limit, date_from, date_to],
    )

    seen: set[int] = set()
    codes: list[int] = []
    for row in rows:
        value = row.get("patient_code")
        if value is None:
            continue
        code = int(value)
        if code in seen:
            continue
        seen.add(code)
        codes.append(code)
    return codes


def get_distinct_chart_healing_actions_patient_codes(
    charting_from: date | str,
    charting_to: date | str,
    limit: int = 50,
) -> list[int]:
    if limit <= 0:
        return []
    date_from = _coerce_date(charting_from)
    date_to = _coerce_date(charting_to)
    if date_to < date_from:
        raise ValueError("charting_to must be on or after charting_from")

    config = R4SqlServerConfig.from_env()
    config.require_enabled()
    config.require_readonly()
    source = R4SqlServerSource(config)
    source.ensure_select_only()

    patient_col = source._pick_column("ChartHealingActions", ["PatientCode"])  # noqa: SLF001
    date_col = source._pick_column(  # noqa: SLF001
        "ChartHealingActions",
        ["ActionDate", "Date", "CreatedDate", "ActionedDate", "ActionedOn"],
    )
    id_col = source._pick_column(  # noqa: SLF001
        "ChartHealingActions",
        ["ID", "ActionID", "ChartHealingActionID"],
    )
    if not patient_col:
        raise RuntimeError("ChartHealingActions missing PatientCode; cannot fetch distinct codes.")
    if not date_col and not id_col:
        raise RuntimeError(
            "ChartHealingActions missing date/id columns; cannot fetch distinct codes."
        )

    if date_col:
        rows = source._query(  # noqa: SLF001
            (
                "SELECT TOP (?) "
                f"{patient_col} AS patient_code "
                "FROM dbo.ChartHealingActions WITH (NOLOCK) "
                f"WHERE {patient_col} IS NOT NULL AND {date_col} >= ? AND {date_col} < ? "
                f"GROUP BY {patient_col} "
                f"ORDER BY MAX({date_col}) DESC, {patient_col} ASC"
            ),
            [limit, date_from, date_to],
        )
    else:
        rows = source._query(  # noqa: SLF001
            (
                "SELECT TOP (?) "
                f"{patient_col} AS patient_code "
                "FROM dbo.ChartHealingActions WITH (NOLOCK) "
                f"WHERE {patient_col} IS NOT NULL "
                f"GROUP BY {patient_col} "
                f"ORDER BY MAX({id_col}) DESC, {patient_col} ASC"
            ),
            [limit],
        )

    seen: set[int] = set()
    codes: list[int] = []
    for row in rows:
        value = row.get("patient_code")
        if value is None:
            continue
        code = int(value)
        if code in seen:
            continue
        seen.add(code)
        codes.append(code)
    return codes


def get_distinct_perioprobe_patient_codes(
    charting_from: date | str,
    charting_to: date | str,
    limit: int = 50,
) -> list[int]:
    if limit <= 0:
        return []
    date_from = _coerce_date(charting_from)
    date_to = _coerce_date(charting_to)
    if date_to < date_from:
        raise ValueError("charting_to must be on or after charting_from")

    config = R4SqlServerConfig.from_env()
    config.require_enabled()
    config.require_readonly()
    extractor = SqlServerChartingExtractor(config)
    seen: set[int] = set()
    codes: list[int] = []
    for row in extractor._iter_perio_probes(  # noqa: SLF001
        patients_from=None,
        patients_to=None,
        patient_codes=None,
        limit=None,
    ):
        code = row.patient_code
        if code is None or code in seen:
            continue
        # Keep selector semantics aligned with canonical importer:
        # when bounds are set, undated perio rows are still eligible.
        recorded_at = row.recorded_at
        if recorded_at is not None:
            day = recorded_at.date()
            if day < date_from or day > date_to:
                continue
        seen.add(code)
        codes.append(code)
        if len(codes) >= limit:
            break
    codes.sort()
    return codes


def get_distinct_bpe_furcation_patient_codes(
    charting_from: date | str,
    charting_to: date | str,
    limit: int = 50,
) -> list[int]:
    if limit <= 0:
        return []
    date_from = _coerce_date(charting_from)
    date_to = _coerce_date(charting_to)
    if date_to < date_from:
        raise ValueError("charting_to must be on or after charting_from")

    config = R4SqlServerConfig.from_env()
    config.require_enabled()
    config.require_readonly()
    source = R4SqlServerSource(config)
    source.ensure_select_only()

    patient_col = source._pick_column("BPE", ["PatientCode"])  # noqa: SLF001
    date_col = source._pick_column(  # noqa: SLF001
        "BPE", ["Date", "BPEDate", "RecordedDate", "EntryDate"]
    )
    bpe_id_col = source._pick_column("BPE", ["BPEID", "BPEId", "ID", "RefId", "RefID"])  # noqa: SLF001
    furcation_bpe_col = source._pick_column("BPEFurcation", ["BPEID", "BPEId"])  # noqa: SLF001
    if not patient_col or not date_col or not bpe_id_col or not furcation_bpe_col:
        raise RuntimeError(
            "BPE/BPEFurcation missing linkage columns; cannot fetch distinct furcation codes."
        )

    rows = source._query(  # noqa: SLF001
        (
            "SELECT TOP (?) "
            f"b.{patient_col} AS patient_code "
            "FROM dbo.BPE b WITH (NOLOCK) "
            "JOIN dbo.BPEFurcation f WITH (NOLOCK) "
            f"ON f.{furcation_bpe_col} = b.{bpe_id_col} "
            f"WHERE b.{patient_col} IS NOT NULL AND b.{date_col} >= ? AND b.{date_col} < ? "
            f"GROUP BY b.{patient_col} "
            f"ORDER BY MAX(b.{date_col}) DESC, b.{patient_col} ASC"
        ),
        [limit, date_from, date_to],
    )

    seen: set[int] = set()
    codes: list[int] = []
    for row in rows:
        value = row.get("patient_code")
        if value is None:
            continue
        code = int(value)
        if code in seen:
            continue
        seen.add(code)
        codes.append(code)
    return codes


def get_distinct_patient_notes_patient_codes(
    charting_from: date | str,
    charting_to: date | str,
    limit: int = 50,
) -> list[int]:
    if limit <= 0:
        return []
    date_from = _coerce_date(charting_from)
    date_to = _coerce_date(charting_to)
    if date_to < date_from:
        raise ValueError("charting_to must be on or after charting_from")

    config = R4SqlServerConfig.from_env()
    config.require_enabled()
    config.require_readonly()
    source = R4SqlServerSource(config)
    source.ensure_select_only()

    patient_col = source._pick_column("PatientNotes", ["PatientCode"])  # noqa: SLF001
    date_col = source._pick_column(  # noqa: SLF001
        "PatientNotes", ["Date", "NoteDate", "CreatedDate", "CreatedOn"]
    )
    if not patient_col or not date_col:
        raise RuntimeError("PatientNotes missing PatientCode/Date columns; cannot fetch distinct codes.")

    rows = source._query(  # noqa: SLF001
        (
            "SELECT TOP (?) "
            f"{patient_col} AS patient_code "
            "FROM dbo.PatientNotes WITH (NOLOCK) "
            f"WHERE {patient_col} IS NOT NULL AND {date_col} >= ? AND {date_col} < ? "
            f"GROUP BY {patient_col} "
            f"ORDER BY MAX({date_col}) DESC, {patient_col} ASC"
        ),
        [limit, date_from, date_to],
    )
    seen: set[int] = set()
    codes: list[int] = []
    for row in rows:
        value = row.get("patient_code")
        if value is None:
            continue
        code = int(value)
        if code in seen:
            continue
        seen.add(code)
        codes.append(code)
    return codes


def get_distinct_treatment_notes_patient_codes(
    charting_from: date | str,
    charting_to: date | str,
    limit: int = 50,
) -> list[int]:
    if limit <= 0:
        return []
    date_from = _coerce_date(charting_from)
    date_to = _coerce_date(charting_to)
    if date_to < date_from:
        raise ValueError("charting_to must be on or after charting_from")

    config = R4SqlServerConfig.from_env()
    config.require_enabled()
    config.require_readonly()
    source = R4SqlServerSource(config)
    source.ensure_select_only()

    patient_col = source._pick_column("TreatmentNotes", ["PatientCode"])  # noqa: SLF001
    date_col = source._pick_column(  # noqa: SLF001
        "TreatmentNotes",
        ["Date", "NoteDate", "DateAdded", "CreatedDate", "CreatedOn"],
    )
    if not patient_col or not date_col:
        raise RuntimeError("TreatmentNotes missing PatientCode/Date columns; cannot fetch distinct codes.")

    rows = source._query(  # noqa: SLF001
        (
            "SELECT TOP (?) "
            f"{patient_col} AS patient_code "
            "FROM dbo.TreatmentNotes WITH (NOLOCK) "
            f"WHERE {patient_col} IS NOT NULL AND {date_col} >= ? AND {date_col} < ? "
            f"GROUP BY {patient_col} "
            f"ORDER BY MAX({date_col}) DESC, {patient_col} ASC"
        ),
        [limit, date_from, date_to],
    )
    seen: set[int] = set()
    codes: list[int] = []
    for row in rows:
        value = row.get("patient_code")
        if value is None:
            continue
        code = int(value)
        if code in seen:
            continue
        seen.add(code)
        codes.append(code)
    return codes


def get_distinct_treatment_plan_items_patient_codes(
    charting_from: date | str,
    charting_to: date | str,
    limit: int = 50,
) -> list[int]:
    if limit <= 0:
        return []
    date_from = _coerce_date(charting_from)
    date_to = _coerce_date(charting_to)
    if date_to < date_from:
        raise ValueError("charting_to must be on or after charting_from")

    config = R4SqlServerConfig.from_env()
    config.require_enabled()
    config.require_readonly()
    source = R4SqlServerSource(config)
    source.ensure_select_only()

    item_patient_col = source._pick_column("TreatmentPlanItems", ["PatientCode"])  # noqa: SLF001
    item_tp_col = source._pick_column("TreatmentPlanItems", ["TPNumber", "TPNum", "TPNo"])  # noqa: SLF001
    plan_patient_col = source._pick_column("TreatmentPlans", ["PatientCode"])  # noqa: SLF001
    plan_tp_col = source._pick_column("TreatmentPlans", ["TPNumber", "TPNum", "TPNo"])  # noqa: SLF001
    plan_date_col = source._pick_column(  # noqa: SLF001
        "TreatmentPlans",
        ["CreationDate", "Date", "PlanDate"],
    )
    if (
        not item_patient_col
        or not item_tp_col
        or not plan_patient_col
        or not plan_tp_col
        or not plan_date_col
    ):
        raise RuntimeError(
            "TreatmentPlanItems/TreatmentPlans missing patient/TP/date columns; cannot fetch distinct codes."
        )

    rows = source._query(  # noqa: SLF001
        (
            "SELECT TOP (?) "
            f"ti.{item_patient_col} AS patient_code "
            "FROM dbo.TreatmentPlanItems ti WITH (NOLOCK) "
            "JOIN dbo.TreatmentPlans tp WITH (NOLOCK) "
            f"ON tp.{plan_patient_col} = ti.{item_patient_col} "
            f"AND tp.{plan_tp_col} = ti.{item_tp_col} "
            f"WHERE ti.{item_patient_col} IS NOT NULL "
            f"AND tp.{plan_date_col} >= ? AND tp.{plan_date_col} < ? "
            f"GROUP BY ti.{item_patient_col} "
            f"ORDER BY MAX(tp.{plan_date_col}) DESC, ti.{item_patient_col} ASC"
        ),
        [limit, date_from, date_to],
    )
    seen: set[int] = set()
    codes: list[int] = []
    for row in rows:
        value = row.get("patient_code")
        if value is None:
            continue
        code = int(value)
        if code in seen:
            continue
        seen.add(code)
        codes.append(code)
    return codes


def get_distinct_treatment_plans_patient_codes(
    charting_from: date | str,
    charting_to: date | str,
    limit: int = 50,
) -> list[int]:
    if limit <= 0:
        return []
    date_from = _coerce_date(charting_from)
    date_to = _coerce_date(charting_to)
    if date_to < date_from:
        raise ValueError("charting_to must be on or after charting_from")

    config = R4SqlServerConfig.from_env()
    config.require_enabled()
    config.require_readonly()
    source = R4SqlServerSource(config)
    source.ensure_select_only()

    seen: set[int] = set()
    codes: list[int] = []
    # Pull wider than requested then sort by latest CreationDate for deterministic recency bias.
    rows: list[tuple[int, datetime | None]] = []
    scan_limit = max(limit * 5, limit)
    for item in source.list_treatment_plans(
        limit=scan_limit,
        date_from=date_from,
        date_to=date_to,
        include_undated=False,
    ):
        if item.patient_code is None:
            continue
        rows.append((int(item.patient_code), item.creation_date))
    rows.sort(key=lambda pair: ((pair[1] is not None), pair[1] or datetime.min), reverse=True)
    for code, _ in rows:
        if code in seen:
            continue
        seen.add(code)
        codes.append(code)
        if len(codes) >= limit:
            break
    return codes


def get_distinct_restorative_treatments_patient_codes(
    charting_from: date | str,
    charting_to: date | str,
    limit: int = 50,
) -> list[int]:
    if limit <= 0:
        return []
    date_from = _coerce_date(charting_from)
    date_to = _coerce_date(charting_to)
    if date_to < date_from:
        raise ValueError("charting_to must be on or after charting_from")

    config = R4SqlServerConfig.from_env()
    config.require_enabled()
    config.require_readonly()
    source = R4SqlServerSource(config)
    source.ensure_select_only()

    patient_col = source._pick_column("vwTreatments", ["PatientCode", "patientcode"])  # noqa: SLF001
    status_col = source._pick_column("vwTreatments", ["StatusDescription", "statusdescription"])  # noqa: SLF001
    tooth_col = source._pick_column("vwTreatments", ["Tooth", "tooth"])  # noqa: SLF001
    date_col = source._pick_column(  # noqa: SLF001
        "vwTreatments",
        ["CompletionDate", "transactionDate", "CreationDate", "Date"],
    )
    completed_col = source._pick_column("vwTreatments", ["Completed", "Complete"])  # noqa: SLF001

    if not patient_col or not status_col or not tooth_col or not date_col:
        raise RuntimeError(
            "vwTreatments missing patient/status/tooth/date columns; cannot fetch restorative codes."
        )

    statuses = sorted(_RESTORATIVE_TREATMENT_STATUS_DESCRIPTIONS)
    status_placeholders = ", ".join(["?"] * len(statuses))
    where_parts = [
        f"{patient_col} IS NOT NULL",
        f"{date_col} >= ?",
        f"{date_col} < ?",
        f"{tooth_col} IS NOT NULL",
        f"{tooth_col} > 0",
        f"LOWER(CONVERT(nvarchar(200), {status_col})) IN ({status_placeholders})",
    ]
    if completed_col:
        where_parts.append(f"{completed_col} = 1")

    rows = source._query(  # noqa: SLF001
        (
            "SELECT TOP (?) "
            f"{patient_col} AS patient_code "
            "FROM dbo.vwTreatments WITH (NOLOCK) "
            f"WHERE {' AND '.join(where_parts)} "
            f"GROUP BY {patient_col} "
            f"ORDER BY MAX({date_col}) DESC, {patient_col} ASC"
        ),
        [limit, date_from, date_to, *statuses],
    )

    seen: set[int] = set()
    codes: list[int] = []
    for row in rows:
        value = row.get("patient_code")
        if value is None:
            continue
        code = int(value)
        if code in seen:
            continue
        seen.add(code)
        codes.append(code)
    return codes


def get_distinct_active_patient_codes(
    active_from: date | str,
    active_to: date | str,
    limit: int = 50,
) -> list[int]:
    if limit <= 0:
        return []
    from_day = _coerce_date(active_from)
    to_day = _coerce_date(active_to)
    if to_day < from_day:
        raise ValueError("active_to must be on or after active_from")

    config = R4SqlServerConfig.from_env()
    config.require_enabled()
    config.require_readonly()
    source = R4SqlServerSource(config)
    source.ensure_select_only()

    patient_col = source._pick_column("vwAppointmentDetails", ["patientcode"])  # noqa: SLF001
    date_col = source._pick_column("vwAppointmentDetails", ["appointmentDateTimevalue"])  # noqa: SLF001
    if not patient_col or not date_col:
        raise RuntimeError(
            "vwAppointmentDetails missing patient/date columns; cannot fetch active patient codes."
        )

    rows = source._query(  # noqa: SLF001
        (
            "SELECT TOP (?) "
            f"{patient_col} AS patient_code "
            "FROM dbo.vwAppointmentDetails WITH (NOLOCK) "
            f"WHERE {patient_col} IS NOT NULL "
            f"AND {date_col} >= ? AND {date_col} <= ? "
            f"GROUP BY {patient_col} "
            f"ORDER BY MAX({date_col}) DESC, {patient_col} ASC"
        ),
        [limit, from_day, to_day],
    )
    seen: set[int] = set()
    codes: list[int] = []
    for row in rows:
        value = row.get("patient_code")
        if value is None:
            continue
        code = int(value)
        if code in seen:
            continue
        seen.add(code)
        codes.append(code)
    return codes


def _date_in_range(
    recorded_at,
    date_from: date | None,
    date_to: date | None,
    report: SqlServerExtractReport,
) -> bool:
    if date_from is None and date_to is None:
        return True
    if recorded_at is None:
        report.missing_date += 1
        return False
    day = recorded_at.date()
    if date_from and day < date_from:
        report.out_of_range += 1
        return False
    if date_to and day > date_to:
        report.out_of_range += 1
        return False
    return True


def _is_valid_restorative_surface(surface: int | None) -> bool:
    if surface is None:
        return True
    if surface == 0:
        return True
    if surface < 0:
        return False
    return (surface & ~_RESTORATIVE_SURFACE_VALID_MASK) == 0


def _coerce_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _chunk_codes(codes: list[int], *, size: int) -> Iterable[list[int]]:
    if size <= 0:
        raise ValueError("chunk size must be positive")
    unique: list[int] = []
    seen: set[int] = set()
    for code in codes:
        if code in seen:
            continue
        seen.add(code)
        unique.append(code)
    for idx in range(0, len(unique), size):
        yield unique[idx : idx + size]
