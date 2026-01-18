import pytest

from app.services.r4_import.sqlserver_source import R4SqlServerConfig


def test_sqlserver_config_disabled_by_default(monkeypatch):
    monkeypatch.delenv("R4_SQLSERVER_ENABLED", raising=False)
    config = R4SqlServerConfig.from_env()
    assert config.enabled is False
    with pytest.raises(RuntimeError, match="disabled"):
        config.require_enabled()


def test_sqlserver_config_requires_fields_when_enabled(monkeypatch):
    monkeypatch.setenv("R4_SQLSERVER_ENABLED", "true")
    monkeypatch.delenv("R4_SQLSERVER_HOST", raising=False)
    monkeypatch.delenv("R4_SQLSERVER_DB", raising=False)
    monkeypatch.delenv("R4_SQLSERVER_USER", raising=False)
    monkeypatch.delenv("R4_SQLSERVER_PASSWORD", raising=False)
    config = R4SqlServerConfig.from_env()
    with pytest.raises(RuntimeError, match="Missing required SQL Server env vars"):
        config.require_enabled()


def test_sqlserver_config_parses_env(monkeypatch):
    monkeypatch.setenv("R4_SQLSERVER_ENABLED", "true")
    monkeypatch.setenv("R4_SQLSERVER_HOST", "sql.example.local")
    monkeypatch.setenv("R4_SQLSERVER_PORT", "1444")
    monkeypatch.setenv("R4_SQLSERVER_DB", "sys2000")
    monkeypatch.setenv("R4_SQLSERVER_USER", "readonly")
    monkeypatch.setenv("R4_SQLSERVER_PASSWORD", "secret")
    monkeypatch.setenv("R4_SQLSERVER_DRIVER", "ODBC Driver 18 for SQL Server")
    monkeypatch.setenv("R4_SQLSERVER_ENCRYPT", "false")
    monkeypatch.setenv("R4_SQLSERVER_TRUST_CERT", "true")
    monkeypatch.setenv("R4_SQLSERVER_TIMEOUT_SECONDS", "12")
    config = R4SqlServerConfig.from_env()
    assert config.enabled is True
    assert config.host == "sql.example.local"
    assert config.port == 1444
    assert config.database == "sys2000"
    assert config.user == "readonly"
    assert config.password == "secret"
    assert config.driver == "ODBC Driver 18 for SQL Server"
    assert config.encrypt is False
    assert config.trust_cert is True
    assert config.timeout_seconds == 12
