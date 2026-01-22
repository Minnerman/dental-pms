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
    assert payload["window"] == {"patients_from": None, "patients_to": None}
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
