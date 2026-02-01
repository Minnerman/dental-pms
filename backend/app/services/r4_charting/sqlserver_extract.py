from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from app.services.r4_charting.canonical_types import CanonicalRecordInput
from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource


@dataclass
class SqlServerExtractReport:
    missing_date: int = 0
    out_of_range: int = 0
    undated_included: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "missing_date": self.missing_date,
            "out_of_range": self.out_of_range,
            "undated_included": self.undated_included,
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
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int | None = None,
    ) -> tuple[list[CanonicalRecordInput], dict[str, int]]:
        records: list[CanonicalRecordInput] = []
        report = SqlServerExtractReport()

        for item in self._source.list_bpe_entries(
            patients_from=patients_from,
            patients_to=patients_to,
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

        for item in self._source.list_perio_probes(
            patients_from=patients_from,
            patients_to=patients_to,
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

        return records, report.as_dict()


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
