from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Iterable

from app.services.r4_import.types import R4Appointment, R4Patient

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

    def dry_run_summary(
        self,
        limit: int = 10,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Any]:
        patients_count = self.count_patients()
        appts_count = self.count_appts(date_from=date_from, date_to=date_to)
        appt_range = self.appt_date_range()
        return {
            "source": "sqlserver",
            "server": f"{self._config.host}:{self._config.port}",
            "database": self._config.database,
            "patients_count": patients_count,
            "appointments_count": appts_count,
            "appointments_date_range": appt_range,
            "sample_patient_codes": self.sample_patient_codes(limit=limit),
            "sample_appointments": self.sample_appts(limit=limit),
        }

    def count_patients(self) -> int:
        rows = self._query("SELECT COUNT(1) AS count FROM dbo.Patients WITH (NOLOCK)")
        return int(rows[0]["count"]) if rows else 0

    def count_appts(self, date_from: date | None = None, date_to: date | None = None) -> int:
        starts_col = self._pick_column("Appts", ["StartTime", "StartDateTime", "ApptDate", "ScheduledDate"])
        if not starts_col:
            rows = self._query("SELECT COUNT(1) AS count FROM dbo.Appts WITH (NOLOCK)")
            return int(rows[0]["count"]) if rows else 0
        where_clause, params = self._build_date_filter(starts_col, date_from, date_to)
        rows = self._query(
            f"SELECT COUNT(1) AS count FROM dbo.Appts WITH (NOLOCK){where_clause}",
            params,
        )
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
        patient_col = self._require_column("Appts", ["PatientCode"])
        appt_id_col = self._pick_column(
            "Appts",
            ["ApptID", "AppointmentID", "ApptNum", "ApptPrimaryKey", "ApptRecNum"],
        )
        starts_col = self._pick_column("Appts", ["StartTime", "StartDateTime", "ApptDate", "ScheduledDate"])
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

    def list_patients(self, limit: int | None = None) -> Iterable[R4Patient]:
        patient_code_col = self._require_column("Patients", ["PatientCode"])
        first_name_col = self._pick_column("Patients", ["FirstName", "Forename"])
        last_name_col = self._pick_column("Patients", ["LastName", "Surname"])
        dob_col = self._pick_column("Patients", ["DOB", "DateOfBirth", "BirthDate"])
        if not first_name_col or not last_name_col:
            raise RuntimeError("Patients name columns not found; check sys2000.dbo.Patients schema.")

        last_code = 0
        remaining = limit
        batch_size = 500
        while True:
            if remaining is not None:
                if remaining <= 0:
                    break
                batch_size = min(batch_size, remaining)
            rows = self._query(
                f"SELECT TOP (?) {patient_code_col} AS patient_code, "
                f"{first_name_col} AS first_name, {last_name_col} AS last_name"
                + (f", {dob_col} AS date_of_birth" if dob_col else "")
                + " FROM dbo.Patients WITH (NOLOCK) "
                f"WHERE {patient_code_col} > ? ORDER BY {patient_code_col} ASC",
                [batch_size, last_code],
            )
            if not rows:
                break
            for row in rows:
                patient_code = row.get("patient_code")
                if patient_code is None:
                    continue
                last_code = int(patient_code)
                first_name = (row.get("first_name") or "").strip()
                last_name = (row.get("last_name") or "").strip()
                yield R4Patient(
                    patient_code=last_code,
                    first_name=first_name,
                    last_name=last_name,
                    date_of_birth=row.get("date_of_birth"),
                )
                if remaining is not None:
                    remaining -= 1

    def list_appts(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int | None = None,
    ) -> Iterable[R4Appointment]:
        patient_col = self._require_column("Appts", ["PatientCode"])
        starts_col = self._require_column(
            "Appts", ["StartTime", "StartDateTime", "ApptDate", "ScheduledDate"]
        )
        appt_id_col = self._pick_column(
            "Appts",
            ["ApptID", "AppointmentID", "ApptNum", "ApptPrimaryKey", "ApptRecNum"],
        )
        end_col = self._pick_column("Appts", ["EndTime", "EndDateTime", "ApptEnd", "EndDate"])
        duration_col = self._pick_column("Appts", ["Minutes", "Duration", "ApptLength", "LengthMinutes"])
        clinician_col = self._pick_column("Appts", ["Clinician", "Provider", "Doctor", "Operator"])
        location_col = self._pick_column("Appts", ["Location", "Operatory", "Room", "Op"])
        appt_type_col = self._pick_column("Appts", ["AppointmentType", "ApptType", "Type"])
        status_col = self._pick_column("Appts", ["Status", "ApptStatus"])

        tie_col = appt_id_col or patient_col
        last_start: datetime | None = None
        last_tie: Any | None = None
        remaining = limit
        batch_size = 500
        while True:
            if remaining is not None:
                if remaining <= 0:
                    break
                batch_size = min(batch_size, remaining)
            where_parts: list[str] = []
            params: list[Any] = []
            date_clause, date_params = self._build_date_filter(starts_col, date_from, date_to)
            if date_clause:
                where_parts.append(date_clause.replace("WHERE", "").strip())
                params.extend(date_params)
            if last_start is not None and last_tie is not None:
                where_parts.append(f"({starts_col} > ? OR ({starts_col} = ? AND {tie_col} > ?))")
                params.extend([last_start, last_start, last_tie])
            where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
            select_cols = [
                f"{starts_col} AS starts_at",
                f"{patient_col} AS patient_code",
            ]
            if appt_id_col:
                select_cols.append(f"{appt_id_col} AS appointment_id")
            if end_col:
                select_cols.append(f"{end_col} AS ends_at")
            if duration_col:
                select_cols.append(f"{duration_col} AS duration_minutes")
            if clinician_col:
                select_cols.append(f"{clinician_col} AS clinician")
            if location_col:
                select_cols.append(f"{location_col} AS location")
            if appt_type_col:
                select_cols.append(f"{appt_type_col} AS appointment_type")
            if status_col:
                select_cols.append(f"{status_col} AS status")
            rows = self._query(
                f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.Appts WITH (NOLOCK) "
                f"{where_sql} ORDER BY {starts_col} ASC, {tie_col} ASC",
                [batch_size, *params],
            )
            if not rows:
                break
            for row in rows:
                starts_at = row.get("starts_at")
                if starts_at is None:
                    continue
                patient_code = row.get("patient_code")
                tie_value = row.get("appointment_id") or patient_code
                last_start = starts_at
                if tie_value is not None:
                    last_tie = tie_value
                ends_at = row.get("ends_at")
                if ends_at is None and duration_col:
                    duration = row.get("duration_minutes")
                    try:
                        minutes = int(duration) if duration is not None else 0
                    except (TypeError, ValueError):
                        minutes = 0
                    ends_at = starts_at + timedelta(minutes=minutes)
                if ends_at is None:
                    ends_at = starts_at
                yield R4Appointment(
                    appointment_id=str(row.get("appointment_id")) if row.get("appointment_id") else None,
                    patient_code=int(patient_code) if patient_code is not None else None,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    clinician=(row.get("clinician") or "").strip() or None,
                    location=(row.get("location") or "").strip() or None,
                    appointment_type=(row.get("appointment_type") or "").strip() or None,
                    status=(row.get("status") or "").strip() or None,
                )
                if remaining is not None:
                    remaining -= 1

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
            # Some pyodbc builds don't support cursor.timeout; connect() already sets timeout.
            try:
                cursor.timeout = self._config.timeout_seconds
            except AttributeError:
                pass
            cursor.execute(f"SET NOCOUNT ON; {sql}", params or [])
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

    def _require_column(self, table: str, candidates: list[str]) -> str:
        column = self._pick_column(table, candidates)
        if column is None:
            raise RuntimeError(
                f"{table} missing expected column (tried: {', '.join(candidates)})."
            )
        return column

    def _build_date_filter(
        self,
        column: str,
        date_from: date | None,
        date_to: date | None,
    ) -> tuple[str, list[Any]]:
        if not date_from and not date_to:
            return "", []
        filters: list[str] = []
        params: list[Any] = []
        if date_from:
            filters.append(f"{column} >= ?")
            params.append(datetime.combine(date_from, datetime.min.time()))
        if date_to:
            end = datetime.combine(date_to, datetime.min.time()) + timedelta(days=1)
            filters.append(f"{column} < ?")
            params.append(end)
        return f"WHERE {' AND '.join(filters)}", params

    @staticmethod
    def _format_dt(value: Any) -> str | None:
        if isinstance(value, datetime):
            return value.isoformat()
        if value is None:
            return None
        return str(value)
