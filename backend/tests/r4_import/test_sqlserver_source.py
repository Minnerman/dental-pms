from datetime import date, datetime

import pytest

from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource


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
    monkeypatch.delenv("R4_SQLSERVER_DATABASE", raising=False)
    monkeypatch.delenv("R4_SQLSERVER_USER", raising=False)
    monkeypatch.delenv("R4_SQLSERVER_PASSWORD", raising=False)
    monkeypatch.delenv("R4_SQLSERVER_TRUST_CERT", raising=False)
    monkeypatch.delenv("R4_SQLSERVER_TRUST_SERVER_CERT", raising=False)
    config = R4SqlServerConfig.from_env()
    with pytest.raises(RuntimeError, match="Missing required SQL Server env vars"):
        config.require_enabled()


def test_sqlserver_config_parses_env():
    env = {
        "R4_SQLSERVER_ENABLED": "true",
        "R4_SQLSERVER_HOST": "sql.example.local",
        "R4_SQLSERVER_PORT": "1444",
        "R4_SQLSERVER_DATABASE": "sys2000",
        "R4_SQLSERVER_USER": "readonly",
        "R4_SQLSERVER_PASSWORD": "secret",
        "R4_SQLSERVER_DRIVER": "ODBC Driver 18 for SQL Server",
        "R4_SQLSERVER_ENCRYPT": "false",
        "R4_SQLSERVER_TRUST_SERVER_CERT": "true",
        "R4_SQLSERVER_TIMEOUT_SECONDS": "12",
    }
    config = R4SqlServerConfig.from_env(env)
    assert config.enabled is True
    assert config.host == "sql.example.local"
    assert config.port == 1444
    assert config.database == "sys2000"
    assert config.user == "readonly"
    assert config.password == "secret"
    assert config.driver == "ODBC Driver 18 for SQL Server"
    assert config.encrypt is False
    assert config.trust_cert is True
    assert config.trust_cert_set is True
    assert config.timeout_seconds == 12


def test_sqlserver_config_accepts_legacy_aliases():
    env = {
        "R4_SQLSERVER_ENABLED": "true",
        "R4_SQLSERVER_HOST": "sql.example.local",
        "R4_SQLSERVER_DB": "sys2000",
        "R4_SQLSERVER_USER": "readonly",
        "R4_SQLSERVER_PASSWORD": "secret",
        "R4_SQLSERVER_TRUST_CERT": "false",
    }
    config = R4SqlServerConfig.from_env(env)
    assert config.database == "sys2000"
    assert config.trust_cert is False
    assert config.trust_cert_set is True


def test_sqlserver_config_prefers_trust_server_cert_over_legacy_alias():
    env = {
        "R4_SQLSERVER_ENABLED": "true",
        "R4_SQLSERVER_HOST": "sql.example.local",
        "R4_SQLSERVER_DATABASE": "sys2000",
        "R4_SQLSERVER_USER": "readonly",
        "R4_SQLSERVER_PASSWORD": "secret",
        "R4_SQLSERVER_TRUST_SERVER_CERT": "true",
        "R4_SQLSERVER_TRUST_CERT": "false",
    }
    config = R4SqlServerConfig.from_env(env)
    assert config.trust_cert is True
    assert config.trust_cert_set is True


def test_treatment_transactions_date_range_date_floor(monkeypatch):
    config = R4SqlServerConfig(
        enabled=True,
        host="sql.example.local",
        port=1433,
        database="sys2000",
        user="readonly",
        password="secret",
        driver=None,
        encrypt=True,
        trust_cert=False,
        timeout_seconds=5,
    )
    source = R4SqlServerSource(config)

    def fake_require_column(_table, candidates):
        return "Date" if "Date" in candidates else "PatientCode"

    def fake_query(_sql, params=None):
        if params and any(isinstance(param, datetime) for param in params):
            return [{"min_date": datetime(2000, 1, 1), "max_date": datetime(2001, 1, 1)}]
        return [{"min_date": datetime(1929, 2, 3), "max_date": datetime(2001, 1, 1)}]

    monkeypatch.setattr(source, "_require_column", fake_require_column)
    monkeypatch.setattr(source, "_query", fake_query)

    raw = source.treatment_transactions_date_range()
    sane = source.treatment_transactions_date_range(date_floor=date(1950, 1, 1))

    assert raw["min"].startswith("1929")
    assert sane["min"].startswith("2000")
