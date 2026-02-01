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
        patient_codes: list[int] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int | None = None,
    ) -> tuple[list[CanonicalRecordInput], dict[str, int]]:
        records: list[CanonicalRecordInput] = []
        report = SqlServerExtractReport()

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
