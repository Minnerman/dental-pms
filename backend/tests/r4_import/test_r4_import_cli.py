import sys

from app.scripts import r4_import as r4_import_script
from app.services.r4_import.sqlserver_source import R4SqlServerConfig


class DummySqlServerSource:
    def __init__(self, _config):
        self._config = _config

    def dry_run_summary(self, limit=10, date_from=None, date_to=None):
        return {"ok": True, "limit": limit}


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
