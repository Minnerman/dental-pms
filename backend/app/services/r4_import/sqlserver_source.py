from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class R4SqlServerConfig:
    enabled: bool
    host: str | None
    port: int
    database: str | None
    user: str | None
    password: str | None
    driver: str | None
    encrypt: bool
    trust_cert: bool
    timeout_seconds: int

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "R4SqlServerConfig":
        env = environ or os.environ
        return cls(
            enabled=_parse_bool(env.get("R4_SQLSERVER_ENABLED"), default=False),
            host=env.get("R4_SQLSERVER_HOST"),
            port=int(env.get("R4_SQLSERVER_PORT", "1433")),
            database=env.get("R4_SQLSERVER_DB"),
            user=env.get("R4_SQLSERVER_USER"),
            password=env.get("R4_SQLSERVER_PASSWORD"),
            driver=env.get("R4_SQLSERVER_DRIVER"),
            encrypt=_parse_bool(env.get("R4_SQLSERVER_ENCRYPT"), default=True),
            trust_cert=_parse_bool(env.get("R4_SQLSERVER_TRUST_CERT"), default=False),
            timeout_seconds=int(env.get("R4_SQLSERVER_TIMEOUT_SECONDS", "8")),
        )

    def require_enabled(self) -> None:
        if not self.enabled:
            raise RuntimeError("R4 SQL Server source is disabled (set R4_SQLSERVER_ENABLED=true).")
        missing = [
            name
            for name, value in {
                "R4_SQLSERVER_HOST": self.host,
                "R4_SQLSERVER_DB": self.database,
                "R4_SQLSERVER_USER": self.user,
                "R4_SQLSERVER_PASSWORD": self.password,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError("Missing required SQL Server env vars: " + ", ".join(missing))


class R4SqlServerSource:
    def __init__(self, config: R4SqlServerConfig) -> None:
        self._config = config
        self._columns_cache: dict[str, list[str]] = {}

    def dry_run_summary(self) -> dict[str, Any]:
        patients_count = self.count_patients()
        appts_count = self.count_appts()
        appt_range = self.appt_date_range()
        return {
            "source": "sqlserver",
            "server": f"{self._config.host}:{self._config.port}",
            "database": self._config.database,
            "patients_count": patients_count,
            "appointments_count": appts_count,
            "appointments_date_range": appt_range,
            "sample_patient_codes": self.sample_patient_codes(),
            "sample_appointments": self.sample_appts(),
        }

    def count_patients(self) -> int:
        rows = self._query("SELECT COUNT(1) AS count FROM dbo.Patients WITH (NOLOCK)")
        return int(rows[0]["count"]) if rows else 0

    def count_appts(self) -> int:
        rows = self._query("SELECT COUNT(1) AS count FROM dbo.Appts WITH (NOLOCK)")
        return int(rows[0]["count"]) if rows else 0

    def appt_date_range(self) -> dict[str, str] | None:
        starts_col = self._pick_column("Appts", ["StartTime", "StartsAt", "ApptDate", "ScheduledDate"])
        if not starts_col:
            return None
        rows = self._query(
            f"SELECT MIN({starts_col}) AS min_date, MAX({starts_col}) AS max_date "
            "FROM dbo.Appts WITH (NOLOCK)"
        )
        if not rows:
            return None
        min_date = rows[0].get("min_date")
        max_date = rows[0].get("max_date")
        return {
            "min": self._format_dt(min_date),
            "max": self._format_dt(max_date),
        }

    def sample_patient_codes(self, limit: int = 10) -> list[int]:
        rows = self._query(
            "SELECT TOP (?) PatientCode FROM dbo.Patients WITH (NOLOCK) "
            "WHERE PatientCode IS NOT NULL ORDER BY PatientCode",
            [limit],
        )
        return [int(row["PatientCode"]) for row in rows if row.get("PatientCode") is not None]

    def sample_appts(self, limit: int = 10) -> list[dict[str, Any]]:
        patient_col = self._pick_column("Appts", ["PatientCode"])
        if not patient_col:
            raise RuntimeError("Appts.PatientCode column not found; cannot sample appointments.")
        appt_id_col = self._pick_column(
            "Appts",
            ["ApptID", "AppointmentID", "ApptNum", "ApptPrimaryKey", "ApptRecNum"],
        )
        starts_col = self._pick_column("Appts", ["StartTime", "StartsAt", "ApptDate", "ScheduledDate"])
        select_cols = [f"{patient_col} AS patient_code"]
        if appt_id_col:
            select_cols.append(f"{appt_id_col} AS legacy_id")
        if starts_col:
            select_cols.append(f"{starts_col} AS starts_at")
        select_clause = ", ".join(select_cols)
        order_col = starts_col or appt_id_col or patient_col
        rows = self._query(
            f"SELECT TOP (?) {select_clause} FROM dbo.Appts WITH (NOLOCK) ORDER BY {order_col}",
            [limit],
        )
        samples: list[dict[str, Any]] = []
        for row in rows:
            samples.append(
                {
                    "legacy_id": row.get("legacy_id"),
                    "patient_code": row.get("patient_code"),
                    "starts_at": self._format_dt(row.get("starts_at")),
                }
            )
        return samples

    def _connect(self):
        try:
            import pyodbc  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "pyodbc is not installed. Install it and the SQL Server ODBC driver."
            ) from exc

        driver = self._config.driver or "ODBC Driver 18 for SQL Server"
        server = f"{self._config.host},{self._config.port}"
        encrypt = "yes" if self._config.encrypt else "no"
        trust_cert = "yes" if self._config.trust_cert else "no"
        conn_str = (
            f"DRIVER={{{driver}}};SERVER={server};DATABASE={self._config.database};"
            f"UID={self._config.user};PWD={self._config.password};"
            f"Encrypt={encrypt};TrustServerCertificate={trust_cert};"
            "ApplicationIntent=ReadOnly;"
            f"Connection Timeout={self._config.timeout_seconds};"
        )
        return pyodbc.connect(conn_str, timeout=self._config.timeout_seconds, autocommit=True)

    def _query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.timeout = self._config.timeout_seconds
            cursor.execute(sql, params or [])
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            conn.close()

    def _get_columns(self, table: str) -> list[str]:
        if table in self._columns_cache:
            return self._columns_cache[table]
        rows = self._query(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = ? ORDER BY ORDINAL_POSITION",
            [table],
        )
        columns = [row["COLUMN_NAME"] for row in rows]
        self._columns_cache[table] = columns
        return columns

    def _pick_column(self, table: str, candidates: list[str]) -> str | None:
        columns = self._get_columns(table)
        for candidate in candidates:
            if candidate in columns:
                return candidate
        return None

    @staticmethod
    def _format_dt(value: Any) -> str | None:
        if isinstance(value, datetime):
            return value.isoformat()
        if value is None:
            return None
        return str(value)
