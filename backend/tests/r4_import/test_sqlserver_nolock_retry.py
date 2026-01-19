import sys
import types

from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource


class DummyProgrammingError(Exception):
    pass


def test_sqlserver_nolock_retry(monkeypatch):
    dummy_pyodbc = types.SimpleNamespace(
        Error=DummyProgrammingError,
        ProgrammingError=DummyProgrammingError,
    )
    monkeypatch.setitem(sys.modules, "pyodbc", dummy_pyodbc)

    class FakeCursor:
        def __init__(self, state):
            self._state = state
            self.description = [("col",)]

        def execute(self, _sql, _params):
            self._state["calls"] += 1
            if self._state["calls"] <= 2:
                raise DummyProgrammingError(
                    "Could not continue scan with NOLOCK due to data movement. (601)"
                )

        def fetchall(self):
            return [("ok",)]

        def close(self):
            return None

    class FakeConn:
        def __init__(self, state):
            self._state = state

        def cursor(self):
            return FakeCursor(self._state)

        def close(self):
            return None

    config = R4SqlServerConfig(
        enabled=True,
        host="sql.local",
        port=1433,
        database="sys2000",
        user="readonly",
        password="secret",
        driver=None,
        encrypt=False,
        trust_cert=True,
        timeout_seconds=5,
    )
    source = R4SqlServerSource(config)
    state = {"calls": 0}
    monkeypatch.setattr(source, "_connect", lambda: FakeConn(state))
    monkeypatch.setattr("time.sleep", lambda _s: None)

    rows = source._query("SELECT * FROM dbo.TreatmentPlanItems WITH (NOLOCK)")

    assert rows == [{"col": "ok"}]
    assert state["calls"] == 3
