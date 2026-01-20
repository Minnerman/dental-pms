import sys

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
