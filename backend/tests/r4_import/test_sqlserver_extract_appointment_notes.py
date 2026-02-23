from datetime import date, datetime

from app.services.r4_charting import sqlserver_extract as extract
from app.services.r4_import.types import R4AppointmentNote


def test_collect_canonical_records_appointment_notes_filters_and_maps():
    class DummySource:
        def __init__(self, _config=None):
            self._config = _config

        def list_appointment_notes(self, patients_from=None, patients_to=None, limit=None):
            rows = [
                R4AppointmentNote(
                    source_apptid=1,
                    patient_code=None,
                    appointment_datetime=datetime(2025, 1, 2, 9, 0, 0),
                    note="valid but missing patient",
                ),
                R4AppointmentNote(
                    source_apptid=None,
                    patient_code=1001,
                    appointment_datetime=datetime(2025, 1, 2, 9, 0, 0),
                    note="missing appt id",
                ),
                R4AppointmentNote(
                    source_apptid=3,
                    patient_code=1001,
                    appointment_datetime=None,
                    note="missing date",
                ),
                R4AppointmentNote(
                    source_apptid=4,
                    patient_code=1001,
                    appointment_datetime=datetime(2026, 2, 1, 0, 0, 0),  # end-exclusive
                    note="out of window",
                ),
                R4AppointmentNote(
                    source_apptid=5,
                    patient_code=1001,
                    appointment_datetime=datetime(2025, 1, 3, 9, 0, 0),
                    note="   ",
                ),
                R4AppointmentNote(
                    source_apptid=6,
                    patient_code=1001,
                    appointment_datetime=datetime(2025, 1, 4, 9, 0, 0),
                    note="First appointment note",
                    status="Booked",
                    appt_flag=1,
                ),
                R4AppointmentNote(
                    source_apptid=6,
                    patient_code=1001,
                    appointment_datetime=datetime(2025, 1, 4, 10, 0, 0),
                    note="Duplicate appt id",
                    status="Arrived",
                    appt_flag=2,
                ),
                R4AppointmentNote(
                    source_apptid=7,
                    patient_code=1002,
                    appointment_datetime=datetime(2025, 1, 5, 9, 0, 0),
                    note="Second appointment note",
                ),
            ]
            if patients_from is not None and patients_to is not None:
                rows = [
                    row
                    for row in rows
                    if row.patient_code is not None and patients_from <= row.patient_code <= patients_to
                ]
            if limit is not None:
                rows = rows[:limit]
            return rows

    extractor = object.__new__(extract.SqlServerChartingExtractor)
    extractor._source = DummySource()

    records, dropped = extractor.collect_canonical_records(
        patient_codes=[1001, 1002],
        date_from=date(2025, 1, 1),
        date_to=date(2026, 2, 1),
        domains=["appointment_notes"],
        limit=100,
    )

    assert len(records) == 2
    assert {record.legacy_patient_code for record in records} == {1001, 1002}
    for record in records:
        assert record.domain == "appointment_note"
        assert record.r4_source == "dbo.vwAppointmentDetails"
        assert isinstance(record.payload, dict)
        assert record.payload["source_apptid"] is not None
        assert record.payload["note"]
        assert record.payload["appointment_datetime"] is not None

    first = next(record for record in records if record.legacy_patient_code == 1001)
    assert first.r4_source_id == "apptid:6"
    assert first.payload["source_apptid"] == 6
    assert first.payload["status"] == "Booked"
    assert first.payload["appt_flag"] == 1

    second = next(record for record in records if record.legacy_patient_code == 1002)
    assert second.r4_source_id == "apptid:7"

    # Patient-scoped batching excludes NULL patient rows before domain filtering.
    assert dropped["missing_patient_code"] == 0
    assert dropped["missing_appt_id"] == 1
    assert dropped["missing_date"] == 1
    assert dropped["out_of_window"] == 1
    assert dropped["blank_note"] == 1
    assert dropped["duplicate_key"] == 1
    assert dropped["accepted_nonblank_note"] == 2
    assert dropped["accepted_blank_note"] == 1
    assert dropped["included"] == 2


def test_collect_canonical_records_appointment_notes_domain_alias():
    class DummySource:
        def __init__(self, _config=None):
            self._config = _config

        def list_appointment_notes(self, **_kwargs):
            return [
                R4AppointmentNote(
                    source_apptid=77,
                    patient_code=1003,
                    appointment_datetime=datetime(2025, 2, 1, 10, 0, 0),
                    note="Appointment note",
                )
            ]

    extractor = object.__new__(extract.SqlServerChartingExtractor)
    extractor._source = DummySource()

    records, dropped = extractor.collect_canonical_records(
        patient_codes=[1003],
        date_from=date(2025, 1, 1),
        date_to=date(2026, 2, 1),
        domains=["appointment_note"],
        limit=10,
    )

    assert len(records) == 1
    assert records[0].domain == "appointment_note"
    assert dropped["included"] == 1

