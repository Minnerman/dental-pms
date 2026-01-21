from __future__ import annotations

import os
import socket
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Iterable

from app.services.r4_import.types import (
    R4Appointment,
    R4Patient,
    R4Treatment,
    R4TreatmentPlan,
    R4TreatmentPlanItem,
    R4TreatmentPlanReview,
)

def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _coerce_bool(value: Any | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


NOLOCK_RETRY_MAX = 6
NOLOCK_RETRY_BASE_SLEEP = 0.5
NOLOCK_RETRY_MAX_SLEEP = 8.0


def _is_nolock_601_error(exc: Exception, sql: str) -> bool:
    message = str(exc)
    if "(601)" not in message and "Could not continue scan with NOLOCK" not in message:
        return False
    return "NOLOCK" in sql.upper()


def _check_tcp_connectivity(host: str | None, port: int, timeout_seconds: int) -> None:
    if not host:
        raise RuntimeError("R4 SQL Server host is not configured.")
    sock = socket.socket()
    sock.settimeout(timeout_seconds)
    try:
        sock.connect((host, port))
    except OSError as exc:
        raise RuntimeError(
            "Cannot reach SQL Server host/port from backend container: "
            f"{host}:{port} ({exc}). Check R4 power/network, firewall, VPN/Tailscale, "
            "and SQL Server port."
        ) from exc
    finally:
        try:
            sock.close()
        except Exception:
            pass


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
    trust_cert_set: bool | None = None

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "R4SqlServerConfig":
        env = environ or os.environ
        database = env.get("R4_SQLSERVER_DATABASE") or env.get("R4_SQLSERVER_DB")
        trust_cert_raw = env.get("R4_SQLSERVER_TRUST_SERVER_CERT") or env.get(
            "R4_SQLSERVER_TRUST_CERT"
        )
        return cls(
            enabled=_parse_bool(env.get("R4_SQLSERVER_ENABLED"), default=False),
            host=env.get("R4_SQLSERVER_HOST"),
            port=int(env.get("R4_SQLSERVER_PORT", "1433")),
            database=database,
            user=env.get("R4_SQLSERVER_USER"),
            password=env.get("R4_SQLSERVER_PASSWORD"),
            driver=env.get("R4_SQLSERVER_DRIVER"),
            encrypt=_parse_bool(env.get("R4_SQLSERVER_ENCRYPT"), default=True),
            trust_cert=_parse_bool(trust_cert_raw, default=False)
            if trust_cert_raw is not None
            else False,
            timeout_seconds=int(env.get("R4_SQLSERVER_TIMEOUT_SECONDS", "8")),
            trust_cert_set=trust_cert_raw is not None,
        )

    def require_enabled(self) -> None:
        if not self.enabled:
            raise RuntimeError("R4 SQL Server source is disabled (set R4_SQLSERVER_ENABLED=true).")
        missing = [
            name
            for name, value in {
                "R4_SQLSERVER_HOST": self.host,
                "R4_SQLSERVER_DATABASE (or R4_SQLSERVER_DB)": self.database,
                "R4_SQLSERVER_USER": self.user,
                "R4_SQLSERVER_PASSWORD": self.password,
            }.items()
            if not value
        ]
        if self.trust_cert_set is False:
            missing.append(
                "R4_SQLSERVER_TRUST_SERVER_CERT (or R4_SQLSERVER_TRUST_CERT)"
            )
        if missing:
            raise RuntimeError(
                "Missing required SQL Server env vars: " + ", ".join(missing)
            )


class R4SqlServerSource:
    def __init__(self, config: R4SqlServerConfig) -> None:
        self._config = config
        self._columns_cache: dict[str, list[str]] = {}
        self._tcp_checked = False

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

    def dry_run_summary_treatments(self, limit: int = 10) -> dict[str, Any]:
        return {
            "source": "sqlserver",
            "server": f"{self._config.host}:{self._config.port}",
            "database": self._config.database,
            "treatments_count": self.count_treatments(),
            "sample_treatments": self.sample_treatments(limit=limit),
        }

    def dry_run_summary_patients(
        self,
        limit: int = 10,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> dict[str, Any]:
        return {
            "source": "sqlserver",
            "server": f"{self._config.host}:{self._config.port}",
            "database": self._config.database,
            "patients_count": self.count_patients(
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "sample_patients": self.sample_patients(
                limit=limit,
                patients_from=patients_from,
                patients_to=patients_to,
            ),
        }

    def dry_run_summary_treatment_plans(
        self,
        limit: int = 10,
        patients_from: int | None = None,
        patients_to: int | None = None,
        tp_from: int | None = None,
        tp_to: int | None = None,
    ) -> dict[str, Any]:
        return {
            "source": "sqlserver",
            "server": f"{self._config.host}:{self._config.port}",
            "database": self._config.database,
            "treatment_plans_count": self.count_treatment_plans(
                patients_from=patients_from,
                patients_to=patients_to,
                tp_from=tp_from,
                tp_to=tp_to,
            ),
            "treatment_plan_items_count": self.count_treatment_plan_items(
                patients_from=patients_from,
                patients_to=patients_to,
                tp_from=tp_from,
                tp_to=tp_to,
            ),
            "treatment_plan_reviews_count": self.count_treatment_plan_reviews(
                patients_from=patients_from,
                patients_to=patients_to,
                tp_from=tp_from,
                tp_to=tp_to,
            ),
            "sample_treatment_plans": self.sample_treatment_plans(
                limit=limit,
                patients_from=patients_from,
                patients_to=patients_to,
                tp_from=tp_from,
                tp_to=tp_to,
            ),
        }

    def count_patients(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> int:
        patient_col = self._require_column("Patients", ["PatientCode"])
        where_clause, params = self._build_range_filter(
            patient_col,
            patients_from,
            patients_to,
        )
        rows = self._query(
            "SELECT COUNT(1) AS count FROM dbo.Patients WITH (NOLOCK)" + where_clause,
            params,
        )
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

    def count_treatments(self) -> int:
        rows = self._query("SELECT COUNT(1) AS count FROM dbo.Treatments WITH (NOLOCK)")
        return int(rows[0]["count"]) if rows else 0

    def count_treatment_plans(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        tp_from: int | None = None,
        tp_to: int | None = None,
    ) -> int:
        patient_col = self._require_column("TreatmentPlans", ["PatientCode"])
        tp_col = self._require_column("TreatmentPlans", ["TPNumber", "TPNum", "TPNo"])
        where_clause, params = self._build_range_filter(
            patient_col,
            patients_from,
            patients_to,
        )
        tp_prefix = "AND" if where_clause else "WHERE"
        tp_clause, tp_params = self._build_range_filter(tp_col, tp_from, tp_to, prefix=tp_prefix)
        where_clause = f"{where_clause}{tp_clause}"
        params.extend(tp_params)
        rows = self._query(
            f"SELECT COUNT(1) AS count FROM dbo.TreatmentPlans WITH (NOLOCK){where_clause}",
            params,
        )
        return int(rows[0]["count"]) if rows else 0

    def count_treatment_plan_items(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        tp_from: int | None = None,
        tp_to: int | None = None,
    ) -> int:
        patient_col = self._require_column("TreatmentPlanItems", ["PatientCode"])
        tp_col = self._require_column("TreatmentPlanItems", ["TPNumber", "TPNum", "TPNo"])
        where_clause, params = self._build_range_filter(
            patient_col,
            patients_from,
            patients_to,
        )
        tp_prefix = "AND" if where_clause else "WHERE"
        tp_clause, tp_params = self._build_range_filter(tp_col, tp_from, tp_to, prefix=tp_prefix)
        where_clause = f"{where_clause}{tp_clause}"
        params.extend(tp_params)
        rows = self._query(
            "SELECT COUNT(1) AS count FROM dbo.TreatmentPlanItems WITH (NOLOCK)"
            f"{where_clause}",
            params,
        )
        return int(rows[0]["count"]) if rows else 0

    def count_treatment_plan_reviews(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        tp_from: int | None = None,
        tp_to: int | None = None,
    ) -> int:
        columns = self._get_columns("TreatmentPlanReviews")
        if not columns:
            return 0
        patient_col = self._pick_column("TreatmentPlanReviews", ["PatientCode"])
        tp_col = self._pick_column("TreatmentPlanReviews", ["TPNumber", "TPNum", "TPNo"])
        if not patient_col or not tp_col:
            return 0
        where_clause, params = self._build_range_filter(
            patient_col,
            patients_from,
            patients_to,
        )
        tp_prefix = "AND" if where_clause else "WHERE"
        tp_clause, tp_params = self._build_range_filter(tp_col, tp_from, tp_to, prefix=tp_prefix)
        where_clause = f"{where_clause}{tp_clause}"
        params.extend(tp_params)
        rows = self._query(
            "SELECT COUNT(1) AS count FROM dbo.TreatmentPlanReviews WITH (NOLOCK)"
            f"{where_clause}",
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

    def sample_patients(
        self,
        limit: int = 10,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> list[dict[str, Any]]:
        patient_code_col = self._require_column("Patients", ["PatientCode"])
        first_name_col = self._pick_column("Patients", ["FirstName", "Forename"])
        last_name_col = self._pick_column("Patients", ["LastName", "Surname"])
        dob_col = self._pick_column("Patients", ["DOB", "DateOfBirth", "BirthDate"])
        if not first_name_col or not last_name_col:
            raise RuntimeError("Patients name columns not found; check sys2000.dbo.Patients schema.")
        select_cols = [
            f"{patient_code_col} AS patient_code",
            f"{first_name_col} AS first_name",
            f"{last_name_col} AS last_name",
        ]
        if dob_col:
            select_cols.append(f"{dob_col} AS date_of_birth")
        where_clause, params = self._build_range_filter(
            patient_code_col,
            patients_from,
            patients_to,
        )
        rows = self._query(
            f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.Patients WITH (NOLOCK) "
            f"{where_clause} ORDER BY {patient_code_col}",
            [limit, *params],
        )
        samples: list[dict[str, Any]] = []
        for row in rows:
            samples.append(
                {
                    "patient_code": row.get("patient_code"),
                    "first_name": row.get("first_name"),
                    "last_name": row.get("last_name"),
                    "date_of_birth": self._format_dt(row.get("date_of_birth")),
                }
            )
        return samples

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

    def sample_treatments(self, limit: int = 10) -> list[dict[str, Any]]:
        code_col = self._require_column(
            "Treatments",
            ["TreatmentCode", "CodeID", "TreatmentID", "Code"],
        )
        desc_col = self._pick_column("Treatments", ["Description", "TreatmentDescription", "Name"])
        short_col = self._pick_column("Treatments", ["ShortCode", "ShortDesc", "Code"])
        select_cols = [f"{code_col} AS treatment_code"]
        if desc_col:
            select_cols.append(f"{desc_col} AS description")
        if short_col:
            select_cols.append(f"{short_col} AS short_code")
        rows = self._query(
            f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.Treatments WITH (NOLOCK) "
            f"ORDER BY {code_col}",
            [limit],
        )
        samples: list[dict[str, Any]] = []
        for row in rows:
            samples.append(
                {
                    "treatment_code": row.get("treatment_code"),
                    "description": row.get("description"),
                    "short_code": row.get("short_code"),
                }
            )
        return samples

    def sample_treatment_plans(
        self,
        limit: int = 10,
        patients_from: int | None = None,
        patients_to: int | None = None,
        tp_from: int | None = None,
        tp_to: int | None = None,
    ) -> list[dict[str, Any]]:
        patient_col = self._require_column("TreatmentPlans", ["PatientCode"])
        tp_col = self._require_column("TreatmentPlans", ["TPNumber", "TPNum", "TPNo"])
        created_col = self._pick_column(
            "TreatmentPlans",
            ["CreationDate", "CreatedDate", "DateCreated", "CreatedOn"],
        )
        select_cols = [f"{patient_col} AS patient_code", f"{tp_col} AS tp_number"]
        if created_col:
            select_cols.append(f"{created_col} AS creation_date")
        where_clause, params = self._build_range_filter(
            patient_col,
            patients_from,
            patients_to,
        )
        tp_prefix = "AND" if where_clause else "WHERE"
        tp_clause, tp_params = self._build_range_filter(tp_col, tp_from, tp_to, prefix=tp_prefix)
        where_clause = f"{where_clause}{tp_clause}"
        params.extend(tp_params)
        rows = self._query(
            f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.TreatmentPlans WITH (NOLOCK)"
            f"{where_clause} ORDER BY {patient_col}, {tp_col}",
            [limit, *params],
        )
        samples: list[dict[str, Any]] = []
        for row in rows:
            samples.append(
                {
                    "patient_code": row.get("patient_code"),
                    "tp_number": row.get("tp_number"),
                    "creation_date": self._format_dt(row.get("creation_date")),
                }
            )
        return samples

    def list_patients(self, limit: int | None = None) -> Iterable[R4Patient]:
        return self.stream_patients(limit=limit)

    def stream_patients(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4Patient]:
        patient_code_col = self._require_column("Patients", ["PatientCode"])
        first_name_col = self._pick_column("Patients", ["FirstName", "Forename"])
        last_name_col = self._pick_column("Patients", ["LastName", "Surname"])
        dob_col = self._pick_column("Patients", ["DOB", "DateOfBirth", "BirthDate"])
        title_col = self._pick_column("Patients", ["Title"])
        sex_col = self._pick_column("Patients", ["Sex", "Gender"])
        nhs_col = self._pick_column(
            "Patients",
            ["NHSNumber", "NHSNo", "NHSNo.", "NHS_Number", "NHS"],
        )
        phone_col = self._pick_column(
            "Patients",
            ["Phone", "Telephone", "Tel", "HomePhone", "PhoneNumber"],
        )
        mobile_col = self._pick_column("Patients", ["MobileNo", "Mobile", "MobileNumber"])
        email_col = self._pick_column("Patients", ["EMail", "Email", "EmailAddress"])
        postcode_col = self._pick_column(
            "Patients",
            ["Postcode", "PostCode", "PostalCode", "Zip", "ZipCode"],
        )
        if not first_name_col or not last_name_col:
            raise RuntimeError("Patients name columns not found; check sys2000.dbo.Patients schema.")

        last_code = (patients_from - 1) if patients_from is not None else 0
        remaining = limit
        batch_size = 500
        while True:
            if remaining is not None:
                if remaining <= 0:
                    break
                batch_size = min(batch_size, remaining)
            where_parts: list[str] = []
            params: list[Any] = []
            range_clause, range_params = self._build_range_filter(
                patient_code_col,
                patients_from,
                patients_to,
            )
            if range_clause:
                where_parts.append(range_clause.replace("WHERE", "").strip())
                params.extend(range_params)
            if last_code is not None:
                where_parts.append(f"{patient_code_col} > ?")
                params.append(last_code)
            where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
            select_cols = [
                f"{patient_code_col} AS patient_code",
                f"{first_name_col} AS first_name",
                f"{last_name_col} AS last_name",
            ]
            if dob_col:
                select_cols.append(f"{dob_col} AS date_of_birth")
            if title_col:
                select_cols.append(f"{title_col} AS title")
            if sex_col:
                select_cols.append(f"{sex_col} AS sex")
            if nhs_col:
                select_cols.append(f"{nhs_col} AS nhs_number")
            if phone_col:
                select_cols.append(f"{phone_col} AS phone")
            if mobile_col:
                select_cols.append(f"{mobile_col} AS mobile_no")
            if email_col:
                select_cols.append(f"{email_col} AS email")
            if postcode_col:
                select_cols.append(f"{postcode_col} AS postcode")
            rows = self._query(
                f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.Patients WITH (NOLOCK) "
                f"{where_sql} ORDER BY {patient_code_col} ASC",
                [batch_size, *params],
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
                dob_value = row.get("date_of_birth")
                if isinstance(dob_value, datetime):
                    dob_value = dob_value.date()
                yield R4Patient(
                    patient_code=last_code,
                    first_name=first_name,
                    last_name=last_name,
                    date_of_birth=dob_value,
                    nhs_number=(str(row.get("nhs_number")) if row.get("nhs_number") is not None else None),
                    title=(row.get("title") or "").strip() or None,
                    sex=(row.get("sex") or "").strip() or None,
                    phone=(row.get("phone") or "").strip() or None,
                    mobile_no=(row.get("mobile_no") or "").strip() or None,
                    email=(row.get("email") or "").strip() or None,
                    postcode=(row.get("postcode") or "").strip() or None,
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

    def list_treatments(self, limit: int | None = None) -> Iterable[R4Treatment]:
        code_col = self._require_column(
            "Treatments",
            ["TreatmentCode", "CodeID", "TreatmentID", "Code"],
        )
        desc_col = self._pick_column("Treatments", ["Description", "TreatmentDescription", "Name"])
        short_col = self._pick_column("Treatments", ["ShortCode", "ShortDesc", "Code"])
        default_time_col = self._pick_column(
            "Treatments",
            ["DefaultTime", "DefaultMinutes", "DefaultDuration"],
        )
        exam_col = self._pick_column("Treatments", ["Exam", "IsExam"])
        patient_required_col = self._pick_column(
            "Treatments",
            ["PatientRequired", "RequiresPatient", "PatientReq"],
        )

        last_code = 0
        remaining = limit
        batch_size = 500
        while True:
            if remaining is not None:
                if remaining <= 0:
                    break
                batch_size = min(batch_size, remaining)
            select_cols = [f"{code_col} AS treatment_code"]
            if desc_col:
                select_cols.append(f"{desc_col} AS description")
            if short_col:
                select_cols.append(f"{short_col} AS short_code")
            if default_time_col:
                select_cols.append(
                    "CASE WHEN {0} IS NULL THEN NULL ELSE "
                    "(DATEPART(HOUR, {0}) * 60 + DATEPART(MINUTE, {0})) "
                    "END AS default_time_minutes".format(default_time_col)
                )
            if exam_col:
                select_cols.append(f"{exam_col} AS exam")
            if patient_required_col:
                select_cols.append(f"{patient_required_col} AS patient_required")
            rows = self._query(
                f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.Treatments WITH (NOLOCK) "
                f"WHERE {code_col} > ? ORDER BY {code_col}",
                [batch_size, last_code],
            )
            if not rows:
                break
            for row in rows:
                treatment_code = row.get("treatment_code")
                if treatment_code is None:
                    continue
                last_code = int(treatment_code)
                yield R4Treatment(
                    treatment_code=last_code,
                    description=(row.get("description") or "").strip() or None,
                    short_code=(row.get("short_code") or "").strip() or None,
                    default_time_minutes=(
                        int(row["default_time_minutes"])
                        if row.get("default_time_minutes") is not None
                        else None
                    ),
                    exam=_coerce_bool(row.get("exam"), default=False),
                    patient_required=_coerce_bool(row.get("patient_required"), default=False),
                )
                if remaining is not None:
                    remaining -= 1

    def list_treatment_plans(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        tp_from: int | None = None,
        tp_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4TreatmentPlan]:
        patient_col = self._require_column("TreatmentPlans", ["PatientCode"])
        tp_col = self._require_column("TreatmentPlans", ["TPNumber", "TPNum", "TPNo"])
        index_col = self._pick_column("TreatmentPlans", ["Index", "TPIndex", "PlanIndex"])
        is_master_col = self._pick_column("TreatmentPlans", ["IsMaster"])
        is_current_col = self._pick_column("TreatmentPlans", ["IsCurrent"])
        is_accepted_col = self._pick_column("TreatmentPlans", ["IsAccepted"])
        creation_col = self._pick_column(
            "TreatmentPlans",
            ["CreationDate", "CreatedDate", "DateCreated", "CreatedOn"],
        )
        acceptance_col = self._pick_column(
            "TreatmentPlans",
            ["AcceptanceDate", "AcceptedDate", "DateAccepted", "AcceptedOn"],
        )
        completion_col = self._pick_column(
            "TreatmentPlans",
            ["CompletionDate", "CompletedDate", "DateCompleted", "CompletedOn"],
        )
        status_col = self._pick_column("TreatmentPlans", ["StatusCode", "TPStatus", "Status"])
        reason_col = self._pick_column("TreatmentPlans", ["ReasonID", "ReasonCode"])
        group_col = self._pick_column("TreatmentPlans", ["TPGroup", "GroupCode", "GroupId"])

        last_patient: int | None = None
        last_tp: int | None = None
        remaining = limit
        batch_size = 500
        while True:
            if remaining is not None:
                if remaining <= 0:
                    break
                batch_size = min(batch_size, remaining)
            where_parts: list[str] = []
            params: list[Any] = []
            range_clause, range_params = self._build_range_filter(
                patient_col, patients_from, patients_to
            )
            if range_clause:
                where_parts.append(range_clause.replace("WHERE", "").strip())
                params.extend(range_params)
            tp_clause, tp_params = self._build_range_filter(tp_col, tp_from, tp_to, prefix="AND")
            if tp_clause:
                where_parts.append(tp_clause.replace("AND", "").strip())
                params.extend(tp_params)
            if last_patient is not None and last_tp is not None:
                where_parts.append(
                    f"({patient_col} > ? OR ({patient_col} = ? AND {tp_col} > ?))"
                )
                params.extend([last_patient, last_patient, last_tp])
            where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
            select_cols = [f"{patient_col} AS patient_code", f"{tp_col} AS tp_number"]
            if index_col:
                index_expr = f"[{index_col}]" if index_col.lower() == "index" else index_col
                select_cols.append(f"{index_expr} AS plan_index")
            if is_master_col:
                select_cols.append(f"{is_master_col} AS is_master")
            if is_current_col:
                select_cols.append(f"{is_current_col} AS is_current")
            if is_accepted_col:
                select_cols.append(f"{is_accepted_col} AS is_accepted")
            if creation_col:
                select_cols.append(f"{creation_col} AS creation_date")
            if acceptance_col:
                select_cols.append(f"{acceptance_col} AS acceptance_date")
            if completion_col:
                select_cols.append(f"{completion_col} AS completion_date")
            if status_col:
                select_cols.append(f"{status_col} AS status_code")
            if reason_col:
                select_cols.append(f"{reason_col} AS reason_id")
            if group_col:
                select_cols.append(f"{group_col} AS tp_group")
            rows = self._query(
                f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.TreatmentPlans WITH (NOLOCK) "
                f"{where_sql} ORDER BY {patient_col} ASC, {tp_col} ASC",
                [batch_size, *params],
            )
            if not rows:
                break
            for row in rows:
                patient_code = row.get("patient_code")
                tp_number = row.get("tp_number")
                if patient_code is None or tp_number is None:
                    continue
                last_patient = int(patient_code)
                last_tp = int(tp_number)
                yield R4TreatmentPlan(
                    patient_code=last_patient,
                    tp_number=last_tp,
                    plan_index=int(row["plan_index"]) if row.get("plan_index") is not None else None,
                    is_master=_coerce_bool(row.get("is_master"), default=False),
                    is_current=_coerce_bool(row.get("is_current"), default=False),
                    is_accepted=_coerce_bool(row.get("is_accepted"), default=False),
                    creation_date=row.get("creation_date"),
                    acceptance_date=row.get("acceptance_date"),
                    completion_date=row.get("completion_date"),
                    status_code=int(row["status_code"]) if row.get("status_code") is not None else None,
                    reason_id=int(row["reason_id"]) if row.get("reason_id") is not None else None,
                    tp_group=int(row["tp_group"]) if row.get("tp_group") is not None else None,
                )
                if remaining is not None:
                    remaining -= 1

    def list_treatment_plan_items(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        tp_from: int | None = None,
        tp_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4TreatmentPlanItem]:
        patient_col = self._require_column("TreatmentPlanItems", ["PatientCode"])
        tp_col = self._require_column("TreatmentPlanItems", ["TPNumber", "TPNum", "TPNo"])
        item_col = self._require_column("TreatmentPlanItems", ["TPItem", "TPItemNo", "TPItemNumber"])
        item_key_col = self._pick_column("TreatmentPlanItems", ["TPItemKey", "TPItemID"])
        code_col = self._pick_column("TreatmentPlanItems", ["CodeID"])
        tooth_col = self._pick_column("TreatmentPlanItems", ["Tooth"])
        surface_col = self._pick_column("TreatmentPlanItems", ["Surface"])
        appt_need_col = self._pick_column(
            "TreatmentPlanItems",
            ["AppointmentNeedID", "ApptNeedID", "AppointmentNeed"],
        )
        completed_col = self._pick_column("TreatmentPlanItems", ["Completed", "IsCompleted"])
        completed_date_col = self._pick_column(
            "TreatmentPlanItems",
            ["CompletedDate", "CompletionDate", "DateCompleted"],
        )
        patient_cost_col = self._pick_column("TreatmentPlanItems", ["PatientCost"])
        dpb_cost_col = self._pick_column("TreatmentPlanItems", ["DPBCost", "DPBCharge"])
        discretionary_cost_col = self._pick_column(
            "TreatmentPlanItems",
            ["DiscretionaryCost", "DiscretionaryCharge"],
        )
        material_col = self._pick_column("TreatmentPlanItems", ["Material"])
        arch_col = self._pick_column("TreatmentPlanItems", ["ArchCode", "Arch"])

        last_patient: int | None = None
        last_tp: int | None = None
        last_item: int | None = None
        remaining = limit
        batch_size = 500
        while True:
            if remaining is not None:
                if remaining <= 0:
                    break
                batch_size = min(batch_size, remaining)
            where_parts: list[str] = []
            params: list[Any] = []
            range_clause, range_params = self._build_range_filter(
                patient_col, patients_from, patients_to
            )
            if range_clause:
                where_parts.append(range_clause.replace("WHERE", "").strip())
                params.extend(range_params)
            tp_clause, tp_params = self._build_range_filter(tp_col, tp_from, tp_to, prefix="AND")
            if tp_clause:
                where_parts.append(tp_clause.replace("AND", "").strip())
                params.extend(tp_params)
            if last_patient is not None and last_tp is not None and last_item is not None:
                where_parts.append(
                    f"({patient_col} > ? OR ({patient_col} = ? AND ({tp_col} > ? OR "
                    f"({tp_col} = ? AND {item_col} > ?))))"
                )
                params.extend(
                    [last_patient, last_patient, last_tp, last_tp, last_item]
                )
            where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
            select_cols = [
                f"{patient_col} AS patient_code",
                f"{tp_col} AS tp_number",
                f"{item_col} AS tp_item",
            ]
            if item_key_col:
                select_cols.append(f"{item_key_col} AS tp_item_key")
            if code_col:
                select_cols.append(f"{code_col} AS code_id")
            if tooth_col:
                select_cols.append(f"{tooth_col} AS tooth")
            if surface_col:
                select_cols.append(f"{surface_col} AS surface")
            if appt_need_col:
                select_cols.append(f"{appt_need_col} AS appointment_need_id")
            if completed_col:
                select_cols.append(f"{completed_col} AS completed")
            if completed_date_col:
                select_cols.append(f"{completed_date_col} AS completed_date")
            if patient_cost_col:
                select_cols.append(f"{patient_cost_col} AS patient_cost")
            if dpb_cost_col:
                select_cols.append(f"{dpb_cost_col} AS dpb_cost")
            if discretionary_cost_col:
                select_cols.append(f"{discretionary_cost_col} AS discretionary_cost")
            if material_col:
                select_cols.append(f"{material_col} AS material")
            if arch_col:
                select_cols.append(f"{arch_col} AS arch_code")
            rows = self._query(
                f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.TreatmentPlanItems WITH (NOLOCK) "
                f"{where_sql} ORDER BY {patient_col} ASC, {tp_col} ASC, {item_col} ASC",
                [batch_size, *params],
            )
            if not rows:
                break
            for row in rows:
                patient_code = row.get("patient_code")
                tp_number = row.get("tp_number")
                tp_item = row.get("tp_item")
                if patient_code is None or tp_number is None or tp_item is None:
                    continue
                last_patient = int(patient_code)
                last_tp = int(tp_number)
                last_item = int(tp_item)
                yield R4TreatmentPlanItem(
                    patient_code=last_patient,
                    tp_number=last_tp,
                    tp_item=last_item,
                    tp_item_key=int(row["tp_item_key"]) if row.get("tp_item_key") is not None else None,
                    code_id=int(row["code_id"]) if row.get("code_id") is not None else None,
                    tooth=int(row["tooth"]) if row.get("tooth") is not None else None,
                    surface=int(row["surface"]) if row.get("surface") is not None else None,
                    appointment_need_id=(
                        int(row["appointment_need_id"])
                        if row.get("appointment_need_id") is not None
                        else None
                    ),
                    completed=_coerce_bool(row.get("completed"), default=False),
                    completed_date=row.get("completed_date"),
                    patient_cost=float(row["patient_cost"])
                    if row.get("patient_cost") is not None
                    else None,
                    dpb_cost=float(row["dpb_cost"]) if row.get("dpb_cost") is not None else None,
                    discretionary_cost=float(row["discretionary_cost"])
                    if row.get("discretionary_cost") is not None
                    else None,
                    material=(row.get("material") or "").strip() or None,
                    arch_code=int(row["arch_code"]) if row.get("arch_code") is not None else None,
                )
                if remaining is not None:
                    remaining -= 1

    def list_treatment_plan_reviews(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        tp_from: int | None = None,
        tp_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4TreatmentPlanReview]:
        columns = self._get_columns("TreatmentPlanReviews")
        if not columns:
            return
        patient_col = self._pick_column("TreatmentPlanReviews", ["PatientCode"])
        tp_col = self._pick_column("TreatmentPlanReviews", ["TPNumber", "TPNum", "TPNo"])
        if not patient_col or not tp_col:
            return
        note_col = self._pick_column(
            "TreatmentPlanReviews",
            ["TemporaryNote", "TempNote", "Notes"],
        )
        reviewed_col = self._pick_column("TreatmentPlanReviews", ["Reviewed", "IsReviewed"])
        edit_user_col = self._pick_column(
            "TreatmentPlanReviews",
            ["LastEditUser", "LastEditedBy", "EditedBy"],
        )
        edit_date_col = self._pick_column(
            "TreatmentPlanReviews",
            ["LastEditDate", "LastEditedAt", "EditedAt"],
        )

        last_patient: int | None = None
        last_tp: int | None = None
        remaining = limit
        batch_size = 500
        while True:
            if remaining is not None:
                if remaining <= 0:
                    break
                batch_size = min(batch_size, remaining)
            where_parts: list[str] = []
            params: list[Any] = []
            range_clause, range_params = self._build_range_filter(
                patient_col, patients_from, patients_to
            )
            if range_clause:
                where_parts.append(range_clause.replace("WHERE", "").strip())
                params.extend(range_params)
            tp_clause, tp_params = self._build_range_filter(tp_col, tp_from, tp_to, prefix="AND")
            if tp_clause:
                where_parts.append(tp_clause.replace("AND", "").strip())
                params.extend(tp_params)
            if last_patient is not None and last_tp is not None:
                where_parts.append(
                    f"({patient_col} > ? OR ({patient_col} = ? AND {tp_col} > ?))"
                )
                params.extend([last_patient, last_patient, last_tp])
            where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
            select_cols = [f"{patient_col} AS patient_code", f"{tp_col} AS tp_number"]
            if note_col:
                select_cols.append(f"{note_col} AS temporary_note")
            if reviewed_col:
                select_cols.append(f"{reviewed_col} AS reviewed")
            if edit_user_col:
                select_cols.append(f"{edit_user_col} AS last_edit_user")
            if edit_date_col:
                select_cols.append(f"{edit_date_col} AS last_edit_date")
            rows = self._query(
                f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.TreatmentPlanReviews WITH (NOLOCK) "
                f"{where_sql} ORDER BY {patient_col} ASC, {tp_col} ASC",
                [batch_size, *params],
            )
            if not rows:
                break
            for row in rows:
                patient_code = row.get("patient_code")
                tp_number = row.get("tp_number")
                if patient_code is None or tp_number is None:
                    continue
                last_patient = int(patient_code)
                last_tp = int(tp_number)
                yield R4TreatmentPlanReview(
                    patient_code=last_patient,
                    tp_number=last_tp,
                    temporary_note=(row.get("temporary_note") or "").strip() or None,
                    reviewed=_coerce_bool(row.get("reviewed"), default=False),
                    last_edit_user=(row.get("last_edit_user") or "").strip() or None,
                    last_edit_date=row.get("last_edit_date"),
                )
                if remaining is not None:
                    remaining -= 1

    def _connect(self):
        if not self._tcp_checked:
            _check_tcp_connectivity(
                self._config.host,
                self._config.port,
                timeout_seconds=min(self._config.timeout_seconds, 5),
            )
            self._tcp_checked = True
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
            try:
                import pyodbc  # type: ignore
            except ImportError:
                pyodbc = None
            error_types: tuple[type[BaseException], ...]
            if pyodbc is not None:
                error_types = (pyodbc.Error,)
            else:
                error_types = (Exception,)
            attempt = 0
            while True:
                cursor = conn.cursor()
                try:
                    # Some pyodbc builds don't support cursor.timeout; connect() already sets timeout.
                    try:
                        cursor.timeout = self._config.timeout_seconds
                    except AttributeError:
                        pass
                    cursor.execute(f"SET NOCOUNT ON; {sql}", params or [])
                    columns = [col[0] for col in cursor.description]
                    return [dict(zip(columns, row)) for row in cursor.fetchall()]
                except error_types as exc:
                    if _is_nolock_601_error(exc, sql) and attempt < NOLOCK_RETRY_MAX:
                        sleep_for = min(
                            NOLOCK_RETRY_BASE_SLEEP * (2**attempt), NOLOCK_RETRY_MAX_SLEEP
                        )
                        attempt += 1
                        time.sleep(sleep_for)
                        continue
                    raise
                finally:
                    try:
                        cursor.close()
                    except Exception:
                        pass
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

    def _build_range_filter(
        self,
        column: str,
        value_from: int | None,
        value_to: int | None,
        prefix: str = "WHERE",
    ) -> tuple[str, list[Any]]:
        if value_from is None and value_to is None:
            return "", []
        filters: list[str] = []
        params: list[Any] = []
        if value_from is not None:
            filters.append(f"{column} >= ?")
            params.append(value_from)
        if value_to is not None:
            filters.append(f"{column} <= ?")
            params.append(value_to)
        clause_prefix = prefix.strip()
        if clause_prefix:
            return f"{clause_prefix} {' AND '.join(filters)}", params
        return f"WHERE {' AND '.join(filters)}", params

    @staticmethod
    def _format_dt(value: Any) -> str | None:
        if isinstance(value, datetime):
            return value.isoformat()
        if value is None:
            return None
        return str(value)
