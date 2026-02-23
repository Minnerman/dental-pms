from datetime import date, datetime

from app.scripts import r4_appointment_notes_drop_report as drop_report
from app.services.r4_import.types import R4AppointmentNote


class _DummyCfg:
    def require_enabled(self):
        return None

    def require_readonly(self):
        return None


class _DummySource:
    def __init__(self, _cfg):
        self._cfg = _cfg

    def ensure_select_only(self):
        return None

    def list_appointment_notes(self, **kwargs):
        return [
            R4AppointmentNote(
                source_apptid=200,
                patient_code=1001,
                appointment_datetime=datetime(2025, 1, 1, 9, 0, 0),
                note="Kept appt note",
                status="Booked",
                appt_flag=1,
            ),
            R4AppointmentNote(
                source_apptid=None,
                patient_code=1001,
                appointment_datetime=datetime(2025, 1, 1, 10, 0, 0),
                note="missing appt id",
            ),
            R4AppointmentNote(
                source_apptid=201,
                patient_code=1001,
                appointment_datetime=datetime(2025, 1, 2, 9, 0, 0),
                note="  ",
            ),
            R4AppointmentNote(
                source_apptid=200,
                patient_code=1001,
                appointment_datetime=datetime(2025, 1, 3, 9, 0, 0),
                note="Duplicate apptid",
            ),
            R4AppointmentNote(
                source_apptid=202,
                patient_code=1001,
                appointment_datetime=datetime(2026, 2, 1, 0, 0, 0),
                note="Out of window",
            ),
        ]


class _DummyRecord:
    def __init__(self, recorded_at, payload):
        self.recorded_at = recorded_at
        self.payload = payload
        self.r4_source_id = str(payload.get("source_id"))
        self.domain = "appointment_note"
        self.legacy_patient_code = int(payload.get("patient_code", 1001))


class _DummyScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _DummyExecResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _DummyScalarResult(self._rows)


class _DummySession:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, _stmt):
        return _DummyExecResult(self._rows)


def test_build_drop_report_counts_sql_and_pg_and_reasons(monkeypatch):
    monkeypatch.setattr(drop_report.R4SqlServerConfig, "from_env", staticmethod(lambda: _DummyCfg()))
    monkeypatch.setattr(drop_report, "R4SqlServerSource", _DummySource)

    def _fake_canonical_report(*_args, **_kwargs):
        class _Stats:
            def as_dict(self):
                return {"created": 0, "updated": 0, "skipped": 0, "unmapped_patients": 0, "total": 1}

        return _Stats(), {
            "total_records": 1,
            "dropped": {
                "missing_appt_id": 1,
                "blank_note": 1,
                "duplicate_key": 1,
                "out_of_window": 1,
            },
        }

    monkeypatch.setattr(drop_report, "import_r4_charting_canonical_report", _fake_canonical_report)
    monkeypatch.setattr(drop_report, "SqlServerChartingExtractor", lambda _cfg: object())

    session = _DummySession(
        [
            _DummyRecord(
                datetime(2025, 1, 1, 9, 0, 0),
                {
                    "patient_code": 1001,
                    "source_id": "apptid:200",
                    "source_apptid": 200,
                    "note": "Kept appt note",
                    "status": "Booked",
                    "appt_flag": 1,
                },
            )
        ]
    )

    payload = drop_report.build_drop_report(
        session,
        patient_code=1001,
        date_from=date(2025, 1, 1),
        date_to=date(2026, 2, 1),
        row_limit=100,
    )

    assert payload["sql_count"] == 1
    assert payload["pg_count"] == 1
    assert payload["delta_sql_minus_pg"] == 0
    assert payload["sql_candidates_total"] == 5
    assert payload["sql_dropped_reasons"]["missing_appt_id"] == 1
    assert payload["sql_dropped_reasons"]["blank_note"] == 1
    assert payload["sql_dropped_reasons"]["duplicate_key"] == 1
    assert payload["sql_dropped_reasons"]["out_of_window"] == 1
    assert payload["dropped_reasons"]["missing_appt_id"] == 1
    assert payload["dropped_reasons"]["blank_note"] == 1
    assert payload["dropped_reasons"]["duplicate_key"] == 1
    assert payload["dropped_reasons"]["out_of_window"] == 1
    assert payload["latest_match"] is True
    assert payload["latest_digest_match"] is True
    assert payload["sql_latest_key"]["source_id"] == "apptid:200"
    assert payload["sql_latest_key"]["source_apptid"] == 200

