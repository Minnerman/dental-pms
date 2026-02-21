import json
import sys
from datetime import date

from app.services.r4_import.types import R4Patient

from app.scripts import r4_import as r4_import_script
from app.services.r4_import.sqlserver_source import R4SqlServerConfig


class DummySqlServerSource:
    def __init__(self, _config):
        self._config = _config

    def dry_run_summary(self, limit=10, date_from=None, date_to=None):
        return {"ok": True, "limit": limit}

    def dry_run_summary_patients(self, limit=10, patients_from=None, patients_to=None):
        return {"ok": True, "limit": limit, "entity": "patients"}


def test_cli_sqlserver_dry_run_no_import(monkeypatch):
    config = R4SqlServerConfig(
        enabled=True,
        host="sql.local",
        port=1433,
        database="sys2000",
        user="readonly",
        password="secret",
        driver=None,
        encrypt=True,
        trust_cert=False,
        timeout_seconds=5,
    )
    monkeypatch.setattr(r4_import_script.R4SqlServerConfig, "from_env", lambda: config)
    monkeypatch.setattr(r4_import_script, "R4SqlServerSource", DummySqlServerSource)
    monkeypatch.setattr(
        r4_import_script, "import_r4", lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("import_r4 should not run in dry-run mode")
        )
    )
    monkeypatch.setattr(sys, "argv", ["r4_import.py", "--source", "sqlserver", "--dry-run"])
    assert r4_import_script.main() == 0


def test_parse_patient_codes_csv_ok():
    parsed = r4_import_script._parse_patient_codes_csv("1000035, 1000036,1000035")
    assert parsed == [1000035, 1000036]


def test_parse_patient_codes_csv_invalid_token():
    try:
        r4_import_script._parse_patient_codes_csv("1000,abc,1002")
    except RuntimeError as exc:
        assert "Invalid patient code in --patient-codes: abc" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError for invalid token")


def test_parse_patient_codes_csv_empty_token():
    try:
        r4_import_script._parse_patient_codes_csv("1000,,1002")
    except RuntimeError as exc:
        assert "empty token" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError for empty token")


def test_parse_patient_codes_file_csv_and_newline(tmp_path):
    codes_file = tmp_path / "codes.txt"
    codes_file.write_text(
        "1000036,1000035\n# comment\n1000036\n1000037\n",
        encoding="utf-8",
    )
    parsed = r4_import_script._parse_patient_codes_file(str(codes_file))
    assert parsed == [1000035, 1000036, 1000037]


def test_parse_patient_codes_arg_rejects_mutual_exclusion(tmp_path):
    codes_file = tmp_path / "codes.txt"
    codes_file.write_text("1000035\n", encoding="utf-8")
    try:
        r4_import_script._parse_patient_codes_arg("1000035", str(codes_file))
    except RuntimeError as exc:
        assert "mutually exclusive" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError for mutually exclusive args")


def test_parse_charting_domains_accepts_restorative_treatments():
    assert r4_import_script._parse_charting_domains_arg("restorative_treatments") == [
        "restorative_treatments"
    ]


def test_cli_rejects_patient_codes_with_range(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "r4_import.py",
            "--entity",
            "patients",
            "--patient-codes",
            "1,2",
            "--patients-from",
            "1",
            "--patients-to",
            "2",
        ],
    )
    assert r4_import_script.main() == 2


def test_cli_rejects_resume_without_state_file(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "r4_import.py",
            "--entity",
            "charting_canonical",
            "--patient-codes",
            "1000035,1000036",
            "--resume",
        ],
    )
    assert r4_import_script.main() == 2


def test_cli_sqlserver_apply_requires_confirm(monkeypatch):
    config = R4SqlServerConfig(
        enabled=True,
        host="sql.local",
        port=1433,
        database="sys2000",
        user="readonly",
        password="secret",
        driver=None,
        encrypt=True,
        trust_cert=False,
        timeout_seconds=5,
    )
    monkeypatch.setattr(r4_import_script.R4SqlServerConfig, "from_env", lambda: config)
    monkeypatch.setattr(r4_import_script, "R4SqlServerSource", DummySqlServerSource)
    monkeypatch.setattr(
        r4_import_script, "import_r4", lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("import_r4 should not run without confirm")
        )
    )
    monkeypatch.setattr(sys, "argv", ["r4_import.py", "--source", "sqlserver", "--apply"])
    assert r4_import_script.main() == 2


def test_cli_sqlserver_dry_run_patients(monkeypatch):
    class PatientsOnlySqlServerSource:
        def __init__(self, _config):
            self._config = _config

        def dry_run_summary(self, *args, **kwargs):
            raise AssertionError("dry_run_summary should not run for patients entity")

        def dry_run_summary_patients(self, limit=10, patients_from=None, patients_to=None):
            return {"ok": True, "limit": limit, "entity": "patients"}

    config = R4SqlServerConfig(
        enabled=True,
        host="sql.local",
        port=1433,
        database="sys2000",
        user="readonly",
        password="secret",
        driver=None,
        encrypt=True,
        trust_cert=False,
        timeout_seconds=5,
    )
    monkeypatch.setattr(r4_import_script.R4SqlServerConfig, "from_env", lambda: config)
    monkeypatch.setattr(r4_import_script, "R4SqlServerSource", PatientsOnlySqlServerSource)
    monkeypatch.setattr(
        r4_import_script, "import_r4_patients", lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("import_r4_patients should not run in dry-run mode")
        )
    )
    monkeypatch.setattr(sys, "argv", ["r4_import.py", "--source", "sqlserver", "--dry-run", "--entity", "patients"])
    assert r4_import_script.main() == 0


def test_cli_sqlserver_dry_run_appointments(monkeypatch):
    class ApptsSqlServerSource:
        def __init__(self, _config):
            self._config = _config

        def dry_run_summary(self, *args, **kwargs):
            raise AssertionError("dry_run_summary should not run for appointments entity")

        def dry_run_summary_appointments(self, limit=10, date_from=None, date_to=None):
            return {"ok": True, "limit": limit, "entity": "appointments"}

    config = R4SqlServerConfig(
        enabled=True,
        host="sql.local",
        port=1433,
        database="sys2000",
        user="readonly",
        password="secret",
        driver=None,
        encrypt=True,
        trust_cert=False,
        timeout_seconds=5,
    )
    monkeypatch.setattr(r4_import_script.R4SqlServerConfig, "from_env", lambda: config)
    monkeypatch.setattr(r4_import_script, "R4SqlServerSource", ApptsSqlServerSource)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "r4_import.py",
            "--source",
            "sqlserver",
            "--dry-run",
            "--entity",
            "appointments",
        ],
    )
    assert r4_import_script.main() == 0


def test_cli_sqlserver_dry_run_appointments_respects_filters(monkeypatch):
    recorded = {}

    class FilteredAppointmentsSource:
        def __init__(self, _config):
            self._config = _config

        def dry_run_summary_appointments(
            self,
            limit: int = 10,
            date_from: date | None = None,
            date_to: date | None = None,
        ):
            recorded["limit"] = limit
            recorded["date_from"] = date_from
            recorded["date_to"] = date_to
            return {
                "source": "sqlserver",
                "server": "example:1433",
                "database": "sys2000",
                "appointments_count": 7,
                "appointments_date_range": {"min": "2025-01-02", "max": "2025-01-31"},
                "appointments_patient_null": 1,
                "sample_appointments": [],
            }

    config = R4SqlServerConfig(
        enabled=True,
        host="sql.local",
        port=1433,
        database="sys2000",
        user="readonly",
        password="secret",
        driver=None,
        encrypt=True,
        trust_cert=False,
        timeout_seconds=5,
    )
    monkeypatch.setattr(r4_import_script.R4SqlServerConfig, "from_env", lambda: config)
    monkeypatch.setattr(r4_import_script, "R4SqlServerSource", FilteredAppointmentsSource)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "r4_import.py",
            "--source",
            "sqlserver",
            "--dry-run",
            "--entity",
            "appointments",
            "--appts-from",
            "2025-01-01",
            "--appts-to",
            "2025-01-31",
            "--limit",
            "5",
        ],
    )
    assert r4_import_script.main() == 0
    assert recorded["date_from"] == date(2025, 1, 1)
    assert recorded["date_to"] == date(2025, 1, 31)
    assert recorded["limit"] == 5


def test_cli_sqlserver_dry_run_patients_mapping_quality_out(tmp_path, monkeypatch):
    class PatientsOnlySqlServerSource:
        def __init__(self, _config):
            self._config = _config

        def dry_run_summary(self, *args, **kwargs):
            raise AssertionError("dry_run_summary should not run for patients entity")

        def dry_run_summary_patients(self, limit=10, patients_from=None, patients_to=None):
            return {"ok": True, "limit": limit, "entity": "patients"}

        def stream_patients(self, patients_from=None, patients_to=None, limit=None):
            return [
                R4Patient(
                    patient_code=1,
                    first_name="A",
                    last_name="Patient",
                    email="A@Example.com",
                ),
                R4Patient(
                    patient_code=2,
                    first_name="B",
                    last_name="Patient",
                    email="a@example.com",
                ),
            ]

    config = R4SqlServerConfig(
        enabled=True,
        host="sql.local",
        port=1433,
        database="sys2000",
        user="readonly",
        password="secret",
        driver=None,
        encrypt=True,
        trust_cert=False,
        timeout_seconds=5,
    )
    output_path = tmp_path / "mapping_quality.json"
    monkeypatch.setattr(r4_import_script.R4SqlServerConfig, "from_env", lambda: config)
    monkeypatch.setattr(r4_import_script, "R4SqlServerSource", PatientsOnlySqlServerSource)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "r4_import.py",
            "--source",
            "sqlserver",
            "--dry-run",
            "--entity",
            "patients",
            "--mapping-quality-out",
            str(output_path),
        ],
    )
    assert r4_import_script.main() == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["entity"] == "patients"
    assert payload["window"]["patient_filter_mode"] == "none"
    assert payload["mapping_quality"]["duplicates"]["email"]["count"] == 1
    assert payload["mapping_quality"]["duplicates"]["email"]["sample"] == ["a@example.com"]


def test_cli_sqlserver_dry_run_patients_no_mapping_quality_out(tmp_path, monkeypatch):
    class PatientsOnlySqlServerSource:
        def __init__(self, _config):
            self._config = _config

        def dry_run_summary(self, *args, **kwargs):
            raise AssertionError("dry_run_summary should not run for patients entity")

        def dry_run_summary_patients(self, limit=10, patients_from=None, patients_to=None):
            return {"ok": True, "limit": limit, "entity": "patients"}

        def stream_patients(self, patients_from=None, patients_to=None, limit=None):
            return []

    config = R4SqlServerConfig(
        enabled=True,
        host="sql.local",
        port=1433,
        database="sys2000",
        user="readonly",
        password="secret",
        driver=None,
        encrypt=True,
        trust_cert=False,
        timeout_seconds=5,
    )
    output_path = tmp_path / "mapping_quality.json"
    monkeypatch.setattr(r4_import_script.R4SqlServerConfig, "from_env", lambda: config)
    monkeypatch.setattr(r4_import_script, "R4SqlServerSource", PatientsOnlySqlServerSource)
    monkeypatch.setattr(
        sys,
        "argv",
        ["r4_import.py", "--source", "sqlserver", "--dry-run", "--entity", "patients"],
    )
    assert r4_import_script.main() == 0
    assert not output_path.exists()


def test_cli_verify_postgres_requires_patients_entity(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["r4_import.py", "--verify-postgres", "--entity", "treatments"])
    assert r4_import_script.main() == 2


def test_cli_sqlserver_dry_run_treatment_transactions(monkeypatch):
    class TreatmentTransactionsSqlServerSource:
        def __init__(self, _config):
            self._config = _config

        def dry_run_summary(self, *args, **kwargs):
            raise AssertionError("dry_run_summary should not run for treatment_transactions")

        def dry_run_summary_treatment_transactions(
            self, limit=10, patients_from=None, patients_to=None, date_floor=None
        ):
            assert date_floor == date(2000, 1, 1)
            return {
                "ok": True,
                "limit": limit,
                "patients_from": patients_from,
                "patients_to": patients_to,
            }

    config = R4SqlServerConfig(
        enabled=True,
        host="sql.local",
        port=1433,
        database="sys2000",
        user="readonly",
        password="secret",
        driver=None,
        encrypt=True,
        trust_cert=False,
        timeout_seconds=5,
    )
    monkeypatch.setattr(r4_import_script.R4SqlServerConfig, "from_env", lambda: config)
    monkeypatch.setattr(
        r4_import_script, "R4SqlServerSource", TreatmentTransactionsSqlServerSource
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "r4_import.py",
            "--source",
            "sqlserver",
            "--dry-run",
            "--entity",
            "treatment_transactions",
            "--patients-from",
            "100",
            "--patients-to",
            "200",
            "--date-floor",
            "2000-01-01",
        ],
    )
    assert r4_import_script.main() == 0


def test_cli_sqlserver_dry_run_users(monkeypatch):
    class UsersSqlServerSource:
        def __init__(self, _config):
            self._config = _config

        def dry_run_summary(self, *args, **kwargs):
            raise AssertionError("dry_run_summary should not run for users entity")

        def dry_run_summary_users(self, limit=10):
            return {"ok": True, "limit": limit, "entity": "users"}

    config = R4SqlServerConfig(
        enabled=True,
        host="sql.local",
        port=1433,
        database="sys2000",
        user="readonly",
        password="secret",
        driver=None,
        encrypt=True,
        trust_cert=False,
        timeout_seconds=5,
    )
    monkeypatch.setattr(r4_import_script.R4SqlServerConfig, "from_env", lambda: config)
    monkeypatch.setattr(r4_import_script, "R4SqlServerSource", UsersSqlServerSource)
    monkeypatch.setattr(
        sys,
        "argv",
        ["r4_import.py", "--source", "sqlserver", "--dry-run", "--entity", "users"],
    )
    assert r4_import_script.main() == 0


def test_cli_sqlserver_apply_stats_out(tmp_path, monkeypatch):
    class DummySession:
        def commit(self):
            return None

        def close(self):
            return None

    class DummySource:
        def __init__(self, _config):
            self._config = _config

    class DummyStats:
        mapping_quality = None

        def as_dict(self):
            return {"patients_created": 1, "patients_updated": 0, "patients_skipped": 0}

    config = R4SqlServerConfig(
        enabled=True,
        host="sql.local",
        port=1433,
        database="sys2000",
        user="readonly",
        password="secret",
        driver=None,
        encrypt=True,
        trust_cert=False,
        timeout_seconds=5,
    )
    output_path = tmp_path / "stats.json"
    monkeypatch.setattr(r4_import_script.R4SqlServerConfig, "from_env", lambda: config)
    monkeypatch.setattr(r4_import_script, "R4SqlServerSource", DummySource)
    monkeypatch.setattr(r4_import_script, "SessionLocal", lambda: DummySession())
    monkeypatch.setattr(r4_import_script, "resolve_actor_id", lambda _session: 1)
    monkeypatch.setattr(r4_import_script, "import_r4_patients", lambda *args, **kwargs: DummyStats())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "r4_import.py",
            "--source",
            "sqlserver",
            "--apply",
            "--confirm",
            "APPLY",
            "--entity",
            "patients",
            "--stats-out",
            str(output_path),
        ],
    )
    assert r4_import_script.main() == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["entity"] == "patients"
    assert payload["stats"]["patients_created"] == 1


def test_cli_sqlserver_dry_run_charting(monkeypatch):
    recorded = {}

    class ChartingSqlServerSource:
        def __init__(self, _config):
            self._config = _config

        def dry_run_summary(self, *args, **kwargs):
            raise AssertionError("dry_run_summary should not run for charting entity")

        def dry_run_summary_charting(
            self,
            limit: int = 10,
            patients_from: int | None = None,
            patients_to: int | None = None,
        ):
            recorded["limit"] = limit
            recorded["patients_from"] = patients_from
            recorded["patients_to"] = patients_to
            return {"ok": True, "entity": "charting"}

    config = R4SqlServerConfig(
        enabled=True,
        host="sql.local",
        port=1433,
        database="sys2000",
        user="readonly",
        password="secret",
        driver=None,
        encrypt=True,
        trust_cert=False,
        timeout_seconds=5,
    )
    monkeypatch.setattr(r4_import_script.R4SqlServerConfig, "from_env", lambda: config)
    monkeypatch.setattr(r4_import_script, "R4SqlServerSource", ChartingSqlServerSource)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "r4_import.py",
            "--source",
            "sqlserver",
            "--dry-run",
            "--entity",
            "charting",
            "--patients-from",
            "100",
            "--patients-to",
            "200",
            "--limit",
            "5",
        ],
    )
    assert r4_import_script.main() == 0
    assert recorded["limit"] == 5
    assert recorded["patients_from"] == 100
    assert recorded["patients_to"] == 200


def test_cli_charting_canonical_report_includes_patient_codes(tmp_path, monkeypatch):
    captured = {}

    class DummyStats:
        def as_dict(self):
            return {"created": 0, "updated": 0, "skipped": 0, "unmapped_patients": 0, "total": 1}

    class DummySession:
        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    def fake_import(*_args, **kwargs):
        captured["patient_codes"] = kwargs.get("patient_codes")
        return DummyStats(), {
            "total_records": 1,
            "distinct_patients": 1,
            "missing_source_id": 0,
            "missing_patient_code": 0,
            "by_source": {"dbo.BPE": {"fetched": 1}},
            "stats": {"created": 0, "updated": 0, "skipped": 0, "unmapped_patients": 0},
        }

    monkeypatch.setattr(r4_import_script, "SessionLocal", lambda: DummySession())
    monkeypatch.setattr(r4_import_script, "resolve_actor_id", lambda _session: 1)
    monkeypatch.setattr(r4_import_script, "import_r4_charting_canonical_report", fake_import)
    output_path = tmp_path / "charting_codes.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "r4_import.py",
            "--entity",
            "charting_canonical",
            "--patient-codes",
            "1000035,1000036",
            "--output-json",
            str(output_path),
        ],
    )
    assert r4_import_script.main() == 0
    assert captured["patient_codes"] == [1000035, 1000036]
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["patient_filter_mode"] == "codes"
    assert payload["patient_codes_count"] == 2
    assert payload["patient_codes_sample"] == [1000035, 1000036]


def test_cli_charting_canonical_resume_batches_from_state(tmp_path, monkeypatch):
    class DummyStats:
        def __init__(self, created=0, updated=0, skipped=0, unmapped=0, total=0):
            self._payload = {
                "created": created,
                "updated": updated,
                "skipped": skipped,
                "unmapped_patients": unmapped,
                "total": total,
            }

        def as_dict(self):
            return dict(self._payload)

    class DummySession:
        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    calls: list[list[int]] = []

    def fake_import(*_args, **kwargs):
        batch_codes = kwargs.get("patient_codes") or []
        calls.append(list(batch_codes))
        return DummyStats(created=1, total=1), {
            "total_records": 1,
            "distinct_patients": len(batch_codes),
            "missing_source_id": 0,
            "missing_patient_code": 0,
            "by_source": {"dbo.BPE": {"fetched": 1}},
            "stats": {"created": 1, "updated": 0, "skipped": 0, "unmapped_patients": 0, "total": 1},
            "dropped": {"out_of_range": 0, "missing_date": 0},
        }

    state_path = tmp_path / "state.json"
    stats_path = tmp_path / "stats.json"

    monkeypatch.setattr(r4_import_script, "SessionLocal", lambda: DummySession())
    monkeypatch.setattr(r4_import_script, "resolve_actor_id", lambda _session: 1)
    monkeypatch.setattr(r4_import_script, "FixtureSource", lambda: object())
    monkeypatch.setattr(r4_import_script, "import_r4_charting_canonical_report", fake_import)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "r4_import.py",
            "--entity",
            "charting_canonical",
            "--patient-codes",
            "1000003,1000001,1000002",
            "--batch-size",
            "2",
            "--state-file",
            str(state_path),
            "--stats-out",
            str(stats_path),
            "--stop-after-batches",
            "1",
        ],
    )
    assert r4_import_script.main() == 0
    assert calls == [[1000001, 1000002]]

    calls.clear()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "r4_import.py",
            "--entity",
            "charting_canonical",
            "--patient-codes",
            "1000003,1000001,1000002",
            "--batch-size",
            "2",
            "--state-file",
            str(state_path),
            "--resume",
            "--stats-out",
            str(stats_path),
        ],
    )
    assert r4_import_script.main() == 0
    assert calls == [[1000003]]

    payload = json.loads(stats_path.read_text(encoding="utf-8"))
    assert payload["stats"]["imported_created_total"] == 1
    assert payload["stats"]["candidates_total"] == 1


def test_cli_charting_canonical_stats_out_separates_candidates_and_dropped(tmp_path, monkeypatch):
    class DummyStats:
        def as_dict(self):
            return {"created": 0, "updated": 0, "skipped": 0, "unmapped_patients": 0, "total": 0}

    class DummySession:
        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    def fake_import(*_args, **kwargs):
        return DummyStats(), {
            "total_records": 0,
            "distinct_patients": 0,
            "missing_source_id": 0,
            "missing_patient_code": 0,
            "by_source": {},
            "stats": {"created": 0, "updated": 0, "skipped": 0, "unmapped_patients": 0, "total": 0},
            "dropped": {"out_of_range": 3, "missing_date": 2},
        }

    stats_path = tmp_path / "stats.json"
    monkeypatch.setattr(r4_import_script, "SessionLocal", lambda: DummySession())
    monkeypatch.setattr(r4_import_script, "resolve_actor_id", lambda _session: 1)
    monkeypatch.setattr(r4_import_script, "FixtureSource", lambda: object())
    monkeypatch.setattr(r4_import_script, "import_r4_charting_canonical_report", fake_import)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "r4_import.py",
            "--entity",
            "charting_canonical",
            "--patient-codes",
            "1000001",
            "--stats-out",
            str(stats_path),
        ],
    )
    assert r4_import_script.main() == 0
    payload = json.loads(stats_path.read_text(encoding="utf-8"))
    assert payload["stats"]["imported_created_total"] == 0
    assert payload["stats"]["dropped_out_of_range_total"] == 3
    assert payload["stats"]["dropped_missing_date_total"] == 2
    assert payload["stats"]["candidates_total"] == 5
    assert payload["stats"]["dropped_reasons"] == {
        "missing_date": 2,
        "out_of_range": 3,
    }
