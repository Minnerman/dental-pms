from datetime import datetime, timezone
from sqlalchemy import delete, func, select

from app.db.session import SessionLocal
from app.models.r4_charting_canonical import R4ChartingCanonicalRecord
from app.services.r4_charting.canonical_importer import (
    import_r4_charting_canonical,
    import_r4_charting_canonical_report,
)
from app.services.r4_charting.canonical_types import CanonicalRecordInput
from app.services.r4_charting.sqlserver_extract import SqlServerExtractReport
from app.services.r4_import.fixture_source import FixtureSource


def clear_canonical(session) -> None:
    session.execute(delete(R4ChartingCanonicalRecord))


def test_canonical_import_idempotent():
    session = SessionLocal()
    try:
        clear_canonical(session)
        session.commit()

        source = FixtureSource()
        stats_first = import_r4_charting_canonical(session, source)
        session.commit()

        assert stats_first.total > 0
        assert stats_first.created == stats_first.total
        assert stats_first.updated == 0
        assert stats_first.skipped == 0

        stats_second = import_r4_charting_canonical(session, source)
        session.commit()

        assert stats_second.total == stats_first.total
        assert stats_second.created == 0
        assert stats_second.updated == 0
        assert stats_second.skipped == stats_second.total
    finally:
        session.close()


def test_canonical_report_includes_sources():
    session = SessionLocal()
    try:
        source = FixtureSource()
        stats, report = import_r4_charting_canonical_report(session, source, dry_run=True)
        assert stats.total > 0
        assert report["total_records"] == stats.total
        by_source = report["by_source"]
        assert "dbo.BPE" in by_source
        assert "dbo.PerioProbe" in by_source
    finally:
        session.close()


class UndatedSource:
    select_only = True

    def collect_canonical_records(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        date_from=None,
        date_to=None,
        limit: int | None = None,
    ):
        report = SqlServerExtractReport(undated_included=2)
        records = [
            CanonicalRecordInput(
                domain="perio_probe",
                r4_source="dbo.PerioProbe",
                r4_source_id="1:11:1",
                legacy_patient_code=1000000,
                recorded_at=None,
                entered_at=None,
                tooth=11,
                surface=None,
                code_id=None,
                status=None,
                payload={"note": "undated"},
            ),
            CanonicalRecordInput(
                domain="perio_probe",
                r4_source="dbo.PerioProbe",
                r4_source_id="1:11:2",
                legacy_patient_code=1000000,
                recorded_at=None,
                entered_at=None,
                tooth=11,
                surface=None,
                code_id=None,
                status=None,
                payload={"note": "undated"},
            ),
        ]
        return records, report.as_dict()


def test_report_warns_on_undated_sources():
    session = SessionLocal()
    try:
        source = UndatedSource()
        stats, report = import_r4_charting_canonical_report(
            session,
            source,
            date_from=datetime(2020, 1, 1, tzinfo=timezone.utc).date(),
            date_to=datetime(2020, 12, 31, tzinfo=timezone.utc).date(),
            dry_run=True,
        )
        assert stats.total == 2
        assert report["dropped"]["undated_included"] == 2
        warnings = report.get("warnings", [])
        assert any("Undated rows included" in w for w in warnings)
    finally:
        session.close()


class DuplicateKeySource:
    select_only = True

    def collect_canonical_records(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        date_from=None,
        date_to=None,
        limit: int | None = None,
    ):
        record = CanonicalRecordInput(
            domain="perio_probe",
            r4_source="dbo.PerioProbe",
            r4_source_id="2:3:1",
            legacy_patient_code=1000000,
            recorded_at=None,
            entered_at=None,
            tooth=3,
            surface=None,
            code_id=None,
            status=None,
            payload={"note": "dup"},
        )
        return [record, record], {}


def test_dedupes_duplicate_unique_key_in_apply():
    session = SessionLocal()
    try:
        clear_canonical(session)
        session.commit()
        source = DuplicateKeySource()
        stats, report = import_r4_charting_canonical_report(session, source, dry_run=False)
        session.commit()
        assert stats.created == 1
        assert report["dropped"]["duplicate_unique_key"] == 1
        total = session.scalar(select(func.count()).select_from(R4ChartingCanonicalRecord))
        assert total == 1
    finally:
        session.close()


class MutatingSource:
    select_only = True

    def __init__(self) -> None:
        self._toggle = False

    def collect_canonical_records(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        date_from=None,
        date_to=None,
        limit: int | None = None,
    ):
        payload_note = "v1" if not self._toggle else "v2"
        self._toggle = True
        record = CanonicalRecordInput(
            domain="bpe_entry",
            r4_source="dbo.BPE",
            r4_source_id="1000035:2017-10-25 12:08:48",
            legacy_patient_code=1000035,
            recorded_at=None,
            entered_at=None,
            tooth=None,
            surface=None,
            code_id=None,
            status=None,
            payload={"note": payload_note},
        )
        return [record], {}


def test_content_hash_prevents_updates_when_unchanged():
    session = SessionLocal()
    try:
        clear_canonical(session)
        session.commit()
        source = FixtureSource()
        stats, _ = import_r4_charting_canonical_report(session, source, dry_run=False)
        session.commit()
        stats_rerun, _ = import_r4_charting_canonical_report(session, source, dry_run=False)
        session.commit()
        assert stats.created > 0
        assert stats_rerun.updated == 0
    finally:
        session.close()


def test_content_hash_updates_on_change():
    session = SessionLocal()
    try:
        clear_canonical(session)
        session.commit()
        source = MutatingSource()
        stats_first, _ = import_r4_charting_canonical_report(session, source, dry_run=False)
        session.commit()
        stats_second, _ = import_r4_charting_canonical_report(session, source, dry_run=False)
        session.commit()
        assert stats_first.created == 1
        assert stats_second.updated == 1
    finally:
        session.close()
