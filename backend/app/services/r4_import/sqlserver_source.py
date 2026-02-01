from __future__ import annotations

import os
import socket
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Iterable

from app.services.r4_import.types import (
    R4Appointment,
    R4AppointmentRecord,
    R4Patient,
    R4Treatment,
    R4TreatmentTransaction,
    R4User,
    R4TreatmentPlan,
    R4TreatmentPlanItem,
    R4TreatmentPlanReview,
    R4ToothSystem,
    R4ToothSurface,
    R4ChartHealingAction,
    R4BPEEntry,
    R4BPEFurcation,
    R4PerioProbe,
    R4PerioPlaque,
    R4PatientNote,
    R4FixedNote,
    R4NoteCategory,
    R4TreatmentNote,
    R4TemporaryNote,
    R4OldPatientNote,
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


def _format_role_value(value: Any | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return f"Type {int(value)}"
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return f"Type {text}"
    return text


def _build_user_role(
    *,
    role_value: Any | None,
    is_extended_duty_nurse: Any | None,
    is_oral_health_promoter: Any | None,
    is_clinic_admin_super_user: Any | None,
) -> str | None:
    if _coerce_bool(is_extended_duty_nurse, default=False):
        return "Extended duty nurse"
    if _coerce_bool(is_oral_health_promoter, default=False):
        return "Oral health promoter"
    if _coerce_bool(is_clinic_admin_super_user, default=False):
        return "Clinic admin"
    return _format_role_value(role_value)


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
        trust_cert_raw = env.get("R4_SQLSERVER_TRUST_CERT")
        if trust_cert_raw is None:
            trust_cert_raw = env.get("R4_SQLSERVER_TRUST_SERVER_CERT")
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
    select_only = True

    def __init__(self, config: R4SqlServerConfig) -> None:
        self._config = config
        self._columns_cache: dict[str, list[str]] = {}
        self._tcp_checked = False

    def ensure_select_only(self) -> None:
        if not self.select_only:
            raise RuntimeError("R4 SQL Server source must be SELECT-only.")

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

    def dry_run_summary_appointments(
        self,
        limit: int = 10,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Any]:
        appts_count = self.count_appointments(date_from=date_from, date_to=date_to)
        appt_range = self.appointment_date_range(date_from=date_from, date_to=date_to)
        null_patients = self.appointment_patient_null_count(
            date_from=date_from,
            date_to=date_to,
        )
        return {
            "source": "sqlserver",
            "server": f"{self._config.host}:{self._config.port}",
            "database": self._config.database,
            "appointments_count": appts_count,
            "appointments_date_range": appt_range,
            "appointments_patient_null": null_patients,
            "sample_appointments": self.sample_appointments(limit=limit),
        }

    def dry_run_summary_treatments(self, limit: int = 10) -> dict[str, Any]:
        return {
            "source": "sqlserver",
            "server": f"{self._config.host}:{self._config.port}",
            "database": self._config.database,
            "treatments_count": self.count_treatments(),
            "sample_treatments": self.sample_treatments(limit=limit),
        }

    def dry_run_summary_users(self, limit: int = 10) -> dict[str, Any]:
        return {
            "source": "sqlserver",
            "server": f"{self._config.host}:{self._config.port}",
            "database": self._config.database,
            "users_count": self.count_users(),
            "sample_users": self.sample_users(limit=limit),
        }

    def dry_run_summary_treatment_transactions(
        self,
        limit: int = 10,
        patients_from: int | None = None,
        patients_to: int | None = None,
        date_floor: date | None = None,
    ) -> dict[str, Any]:
        raw_range = self.treatment_transactions_date_range(
            patients_from=patients_from,
            patients_to=patients_to,
        )
        sane_range = self.treatment_transactions_date_range(
            patients_from=patients_from,
            patients_to=patients_to,
            date_floor=date_floor,
        )
        return {
            "source": "sqlserver",
            "server": f"{self._config.host}:{self._config.port}",
            "database": self._config.database,
            "treatment_transactions_count": self.count_treatment_transactions(
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "treatment_transactions_date_range": raw_range,
            "treatment_transactions_date_range_raw": raw_range,
            "treatment_transactions_date_range_sane": sane_range,
            "sample_treatment_transactions": self.sample_treatment_transactions(
                limit=limit,
                patients_from=patients_from,
                patients_to=patients_to,
            ),
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

    def dry_run_summary_charting(
        self,
        limit: int = 10,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> dict[str, Any]:
        return {
            "source": "sqlserver",
            "server": f"{self._config.host}:{self._config.port}",
            "database": self._config.database,
            "tooth_systems_count": self.count_tooth_systems(),
            "tooth_surfaces_count": self.count_tooth_surfaces(),
            "chart_healing_actions_count": self.count_chart_healing_actions(
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "chart_healing_actions_date_range": self.chart_healing_actions_date_range(
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "bpe_count": self.count_bpe_entries(
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "bpe_date_range": self.bpe_date_range(
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "bpe_furcations_count": self.count_bpe_furcations(
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "perio_probes_count": self.count_perio_probes(
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "perio_plaque_count": self.count_perio_plaque(
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "patient_notes_count": self.count_patient_notes(
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "patient_notes_date_range": self.patient_notes_date_range(
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "fixed_notes_count": self.count_fixed_notes(),
            "note_categories_count": self.count_note_categories(),
            "treatment_notes_count": self.count_treatment_notes(
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "treatment_notes_date_range": self.treatment_notes_date_range(
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "temporary_notes_count": self.count_temporary_notes(
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "old_patient_notes_count": self.count_old_patient_notes(
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "old_patient_notes_date_range": self.old_patient_notes_date_range(
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "bpe_furcation_linkage": self.bpe_furcation_linkage_summary(),
            "perio_probe_linkage": self.perio_probe_linkage_summary(),
            "perio_probe_pipeline": self.perio_probe_pipeline_summary(
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "sample_tooth_systems": self.sample_tooth_systems(limit=limit),
            "sample_tooth_surfaces": self.sample_tooth_surfaces(limit=limit),
            "sample_chart_healing_actions": self.sample_chart_healing_actions(
                limit=limit,
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "sample_bpe_entries": self.sample_bpe_entries(
                limit=limit,
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "sample_bpe_furcations": self.sample_bpe_furcations(
                limit=limit,
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "sample_perio_probes": self.sample_perio_probes(
                limit=limit,
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "sample_perio_plaque": self.sample_perio_plaque(
                limit=limit,
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "sample_patient_notes": self.sample_patient_notes(
                limit=limit,
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "sample_fixed_notes": self.sample_fixed_notes(limit=limit),
            "sample_note_categories": self.sample_note_categories(limit=limit),
            "sample_treatment_notes": self.sample_treatment_notes(
                limit=limit,
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "sample_temporary_notes": self.sample_temporary_notes(
                limit=limit,
                patients_from=patients_from,
                patients_to=patients_to,
            ),
            "sample_old_patient_notes": self.sample_old_patient_notes(
                limit=limit,
                patients_from=patients_from,
                patients_to=patients_to,
            ),
        }

    def perio_probe_linkage_summary(self) -> dict[str, Any]:
        trans_col = self._pick_column("PerioProbe", ["TransId", "TransID"])
        trans_ref_col = self._pick_column("Transactions", ["RefId"])
        patient_col = self._pick_column("Transactions", ["PatientCode"])
        if not trans_col or not trans_ref_col or not patient_col:
            return {
                "status": "unsupported",
                "reason": "Missing PerioProbe.TransId or Transactions.RefId/PatientCode.",
            }
        total = self._count_table("PerioProbe")
        with_transaction = self._count_table(
            "PerioProbe",
            f" WHERE EXISTS (/*perio_probe_with_transaction*/ SELECT 1 FROM dbo.Transactions t WITH (NOLOCK) "
            f"WHERE t.{trans_ref_col} = dbo.PerioProbe.{trans_col})",
        )
        with_patient = self._count_table(
            "PerioProbe",
            f" WHERE EXISTS (/*perio_probe_with_patient*/ SELECT 1 FROM dbo.Transactions t WITH (NOLOCK) "
            f"WHERE t.{trans_ref_col} = dbo.PerioProbe.{trans_col} AND t.{patient_col} IS NOT NULL)",
        )
        with_unique_patient = self._count_table(
            "PerioProbe",
            f" WHERE EXISTS (/*perio_probe_with_unique_patient*/ SELECT 1 FROM ("
            f"SELECT {trans_ref_col} AS ref_id FROM dbo.Transactions WITH (NOLOCK) "
            f"WHERE {patient_col} IS NOT NULL "
            f"GROUP BY {trans_ref_col} HAVING COUNT(DISTINCT {patient_col}) = 1"
            f") t WHERE t.ref_id = dbo.PerioProbe.{trans_col})",
        )
        ambiguous = self._query(
            "/*perio_probe_ambiguous_count*/ "
            "SELECT COUNT(1) AS count FROM ("
            f"SELECT dbo.PerioProbe.{trans_col} AS trans_id, COUNT(DISTINCT t.{patient_col}) AS patient_count "
            "FROM dbo.PerioProbe WITH (NOLOCK) "
            f"JOIN dbo.Transactions t WITH (NOLOCK) ON t.{trans_ref_col} = dbo.PerioProbe.{trans_col} "
            f"WHERE t.{patient_col} IS NOT NULL "
            f"GROUP BY dbo.PerioProbe.{trans_col} HAVING COUNT(DISTINCT t.{patient_col}) > 1"
            ") AS q"
        )
        sample_ambiguous = self._query(
            "/*perio_probe_sample_ambiguous*/ "
            f"SELECT TOP (5) dbo.PerioProbe.{trans_col} AS trans_id "
            "FROM dbo.PerioProbe WITH (NOLOCK) "
            f"JOIN dbo.Transactions t WITH (NOLOCK) ON t.{trans_ref_col} = dbo.PerioProbe.{trans_col} "
            f"WHERE t.{patient_col} IS NOT NULL "
            f"GROUP BY dbo.PerioProbe.{trans_col} HAVING COUNT(DISTINCT t.{patient_col}) > 1 "
            f"ORDER BY dbo.PerioProbe.{trans_col}"
        )
        sample_unlinked_trans = self._query(
            "/*perio_probe_sample_unlinked_trans*/ "
            f"SELECT TOP (5) dbo.PerioProbe.{trans_col} AS trans_id "
            "FROM dbo.PerioProbe WITH (NOLOCK) "
            f"WHERE NOT EXISTS (SELECT 1 FROM dbo.Transactions t WITH (NOLOCK) "
            f"WHERE t.{trans_ref_col} = dbo.PerioProbe.{trans_col}) "
            f"ORDER BY dbo.PerioProbe.{trans_col}"
        )
        sample_unlinked_patient = self._query(
            "/*perio_probe_sample_unlinked_patient*/ "
            f"SELECT TOP (5) dbo.PerioProbe.{trans_col} AS trans_id "
            "FROM dbo.PerioProbe WITH (NOLOCK) "
            f"WHERE EXISTS (SELECT 1 FROM dbo.Transactions t WITH (NOLOCK) "
            f"WHERE t.{trans_ref_col} = dbo.PerioProbe.{trans_col}) "
            f"AND NOT EXISTS (SELECT 1 FROM dbo.Transactions t WITH (NOLOCK) "
            f"WHERE t.{trans_ref_col} = dbo.PerioProbe.{trans_col} AND t.{patient_col} IS NOT NULL) "
            f"ORDER BY dbo.PerioProbe.{trans_col}"
        )
        return {
            "status": "ok",
            "total_probes": total,
            "probes_with_transaction": with_transaction,
            "probes_with_patient": with_patient,
            "probes_with_unique_patient": with_unique_patient,
            "probes_without_transaction": max(total - with_transaction, 0),
            "ambiguous_trans_ids": int(ambiguous[0]["count"]) if ambiguous else 0,
            "sample_ambiguous_trans_ids": [row["trans_id"] for row in sample_ambiguous],
            "sample_unlinked_trans_ids": [row["trans_id"] for row in sample_unlinked_trans],
            "sample_unlinked_patient_trans_ids": [row["trans_id"] for row in sample_unlinked_patient],
        }

    def perio_probe_pipeline_summary(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        trans_col = self._pick_column("PerioProbe", ["TransId", "TransID"])
        trans_ref_col = self._pick_column("Transactions", ["RefId"])
        patient_col = self._pick_column("Transactions", ["PatientCode"])
        if not trans_col or not trans_ref_col or not patient_col:
            return {
                "status": "unsupported",
                "reason": "Missing PerioProbe.TransId or Transactions.RefId/PatientCode.",
            }
        total = self._count_table("PerioProbe")
        with_transaction = self._count_table(
            "PerioProbe",
            f" WHERE EXISTS (/*perio_probe_pipeline_with_transaction*/ SELECT 1 FROM dbo.Transactions t WITH (NOLOCK) "
            f"WHERE t.{trans_ref_col} = dbo.PerioProbe.{trans_col})",
        )
        with_patient = self._count_table(
            "PerioProbe",
            f" WHERE EXISTS (/*perio_probe_pipeline_with_patient*/ SELECT 1 FROM dbo.Transactions t WITH (NOLOCK) "
            f"WHERE t.{trans_ref_col} = dbo.PerioProbe.{trans_col} AND t.{patient_col} IS NOT NULL)",
        )
        with_unique_patient = self._count_table(
            "PerioProbe",
            f" WHERE EXISTS (/*perio_probe_pipeline_with_unique*/ SELECT 1 FROM ("
            f"SELECT {trans_ref_col} AS ref_id, MIN({patient_col}) AS patient_code "
            f"FROM dbo.Transactions WITH (NOLOCK) "
            f"WHERE {patient_col} IS NOT NULL "
            f"GROUP BY {trans_ref_col} HAVING COUNT(DISTINCT {patient_col}) = 1"
            f") t WHERE t.ref_id = dbo.PerioProbe.{trans_col})",
        )
        ambiguous = self._query(
            "/*perio_probe_pipeline_ambiguous_count*/ "
            "SELECT COUNT(1) AS count FROM ("
            f"SELECT dbo.PerioProbe.{trans_col} AS trans_id, COUNT(DISTINCT t.{patient_col}) AS patient_count "
            "FROM dbo.PerioProbe WITH (NOLOCK) "
            f"JOIN dbo.Transactions t WITH (NOLOCK) ON t.{trans_ref_col} = dbo.PerioProbe.{trans_col} "
            f"WHERE t.{patient_col} IS NOT NULL "
            f"GROUP BY dbo.PerioProbe.{trans_col} HAVING COUNT(DISTINCT t.{patient_col}) > 1"
            ") AS q"
        )
        sample_ambiguous = self._query(
            "/*perio_probe_pipeline_sample_ambiguous*/ "
            f"SELECT TOP ({limit}) dbo.PerioProbe.{trans_col} AS trans_id "
            "FROM dbo.PerioProbe WITH (NOLOCK) "
            f"JOIN dbo.Transactions t WITH (NOLOCK) ON t.{trans_ref_col} = dbo.PerioProbe.{trans_col} "
            f"WHERE t.{patient_col} IS NOT NULL "
            f"GROUP BY dbo.PerioProbe.{trans_col} HAVING COUNT(DISTINCT t.{patient_col}) > 1 "
            f"ORDER BY dbo.PerioProbe.{trans_col}"
        )
        range_clause, range_params = self._build_range_filter(
            "t.patient_code",
            patients_from,
            patients_to,
        )
        range_filter = range_clause.replace("WHERE", "").strip()
        filtered_where = f"WHERE {range_filter}" if range_filter else ""
        filtered = self._query(
            "/*perio_probe_pipeline_after_filters*/ "
            "SELECT COUNT(1) AS count FROM dbo.PerioProbe pp WITH (NOLOCK) "
            "JOIN ("
            f"SELECT {trans_ref_col} AS ref_id, MIN({patient_col}) AS patient_code "
            "FROM dbo.Transactions WITH (NOLOCK) "
            f"WHERE {patient_col} IS NOT NULL "
            f"GROUP BY {trans_ref_col} HAVING COUNT(DISTINCT {patient_col}) = 1"
            ") t ON t.ref_id = pp."
            f"{trans_col} {filtered_where}",
            range_params,
        )
        sample_filtered = self._query(
            "/*perio_probe_pipeline_sample_filtered*/ "
            f"SELECT TOP ({limit}) pp.{trans_col} AS trans_id, t.patient_code "
            "FROM dbo.PerioProbe pp WITH (NOLOCK) "
            "JOIN ("
            f"SELECT {trans_ref_col} AS ref_id, MIN({patient_col}) AS patient_code "
            "FROM dbo.Transactions WITH (NOLOCK) "
            f"WHERE {patient_col} IS NOT NULL "
            f"GROUP BY {trans_ref_col} HAVING COUNT(DISTINCT {patient_col}) = 1"
            ") t ON t.ref_id = pp."
            f"{trans_col} {filtered_where} "
            f"ORDER BY pp.{trans_col}",
            range_params,
        )
        after_filters_count = int(filtered[0]["count"]) if filtered else 0
        return {
            "status": "ok",
            "perio_probes_total_source": total,
            "perio_probes_after_join_transactions": with_transaction,
            "perio_probes_after_patient_link": with_unique_patient,
            "perio_probes_after_filters": after_filters_count,
            "perio_probes_skipped_filtered": max(with_unique_patient - after_filters_count, 0),
            "perio_probes_ambiguous_trans_ids": int(ambiguous[0]["count"]) if ambiguous else 0,
            "perio_probes_ambiguous_sample": [
                row["trans_id"]
                for row in sample_ambiguous
                if "trans_id" in row
            ],
            "perio_probes_with_patient": with_patient,
            "sample_filtered_trans_ids": [
                row["trans_id"]
                for row in sample_filtered
                if "trans_id" in row
            ],
        }

    def perio_probe_patient_summary(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> dict[str, Any]:
        trans_col = self._pick_column("PerioProbe", ["TransId", "TransID"])
        tooth_col = self._pick_column("PerioProbe", ["Tooth"])
        point_col = self._pick_column("PerioProbe", ["ProbingPoint", "Point"])
        if not trans_col or not tooth_col or not point_col:
            return {
                "status": "unsupported",
                "reason": "Missing PerioProbe.TransId/Tooth/ProbingPoint.",
            }
        patient_col = self._pick_column("PerioProbe", ["PatientCode"])
        join_sql = ""
        patient_expr = None
        if patient_col:
            patient_expr = f"pp.{patient_col}"
        else:
            trans_ref_col = self._pick_column("Transactions", ["RefId"])
            trans_patient_col = self._pick_column("Transactions", ["PatientCode"])
            if trans_ref_col and trans_patient_col:
                join_sql = (
                    "JOIN ("
                    f"SELECT {trans_ref_col} AS ref_id, MIN({trans_patient_col}) AS patient_code "
                    "FROM dbo.Transactions WITH (NOLOCK) "
                    f"WHERE {trans_patient_col} IS NOT NULL "
                    f"GROUP BY {trans_ref_col} HAVING COUNT(DISTINCT {trans_patient_col}) = 1"
                    ") t ON t.ref_id = pp."
                    + trans_col
                )
                patient_expr = "t.patient_code"
        if not patient_expr:
            return {
                "status": "unsupported",
                "reason": "Missing patient linkage for PerioProbe.",
            }

        range_clause, range_params = self._build_range_filter(
            patient_expr,
            patients_from,
            patients_to,
        )
        range_filter = range_clause.replace("WHERE", "").strip()
        filtered_where = f"WHERE {range_filter}" if range_filter else ""
        total_rows = self._query(
            "/*perio_probe_patient_total*/ "
            "SELECT COUNT(1) AS count "
            "FROM dbo.PerioProbe pp WITH (NOLOCK) "
            f"{join_sql} {filtered_where}",
            range_params,
        )
        unique_rows = self._query(
            "/*perio_probe_patient_unique*/ "
            "SELECT COUNT(1) AS count FROM ("
            f"SELECT pp.{trans_col} AS trans_id, pp.{tooth_col} AS tooth, "
            f"pp.{point_col} AS probing_point "
            "FROM dbo.PerioProbe pp WITH (NOLOCK) "
            f"{join_sql} {filtered_where} "
            f"GROUP BY pp.{trans_col}, pp.{tooth_col}, pp.{point_col}"
            ") AS q",
            range_params,
        )
        total = int(total_rows[0]["count"]) if total_rows else 0
        unique = int(unique_rows[0]["count"]) if unique_rows else 0
        return {
            "status": "ok",
            "total_rows": total,
            "unique_rows": unique,
            "duplicate_rows": max(total - unique, 0),
        }

    def bpe_furcation_linkage_summary(self) -> dict[str, Any]:
        bpe_id_col = self._pick_column("BPE", ["BPEID", "BPEId", "ID", "RefId", "RefID"])
        bpe_patient_col = self._pick_column("BPE", ["PatientCode"])
        furcation_bpe_col = self._pick_column("BPEFurcation", ["BPEID", "BPEId"])
        if not bpe_id_col or not bpe_patient_col or not furcation_bpe_col:
            return {
                "status": "unsupported",
                "reason": "Missing BPE.BPEID/RefId/PatientCode or BPEFurcation.BPEID.",
            }
        total = self._count_table("BPEFurcation")
        with_bpe = self._count_table(
            "BPEFurcation",
            f" WHERE EXISTS (/*bpe_furcation_with_bpe*/ SELECT 1 FROM dbo.BPE b WITH (NOLOCK) "
            f"WHERE b.{bpe_id_col} = dbo.BPEFurcation.{furcation_bpe_col})",
        )
        with_patient = self._count_table(
            "BPEFurcation",
            f" WHERE EXISTS (/*bpe_furcation_with_patient*/ SELECT 1 FROM dbo.BPE b WITH (NOLOCK) "
            f"WHERE b.{bpe_id_col} = dbo.BPEFurcation.{furcation_bpe_col} AND b.{bpe_patient_col} IS NOT NULL)",
        )
        ambiguous = self._query(
            "/*bpe_furcation_ambiguous_count*/ "
            "SELECT COUNT(1) AS count FROM ("
            f"SELECT b.{bpe_id_col} AS bpe_id, COUNT(DISTINCT b.{bpe_patient_col}) AS patient_count "
            "FROM dbo.BPE b WITH (NOLOCK) "
            f"WHERE b.{bpe_patient_col} IS NOT NULL "
            f"GROUP BY b.{bpe_id_col} HAVING COUNT(DISTINCT b.{bpe_patient_col}) > 1"
            ") AS q"
        )
        sample_ambiguous = self._query(
            "/*bpe_furcation_sample_ambiguous*/ "
            f"SELECT TOP (5) b.{bpe_id_col} AS bpe_id "
            "FROM dbo.BPE b WITH (NOLOCK) "
            f"WHERE b.{bpe_patient_col} IS NOT NULL "
            f"GROUP BY b.{bpe_id_col} HAVING COUNT(DISTINCT b.{bpe_patient_col}) > 1 "
            f"ORDER BY b.{bpe_id_col}"
        )
        sample_unlinked = self._query(
            "/*bpe_furcation_sample_unlinked*/ "
            f"SELECT TOP (5) dbo.BPEFurcation.{furcation_bpe_col} AS bpe_id "
            "FROM dbo.BPEFurcation WITH (NOLOCK) "
            f"WHERE NOT EXISTS (SELECT 1 FROM dbo.BPE b WITH (NOLOCK) "
            f"WHERE b.{bpe_id_col} = dbo.BPEFurcation.{furcation_bpe_col}) "
            f"ORDER BY dbo.BPEFurcation.{furcation_bpe_col}"
        )
        return {
            "status": "ok",
            "total_furcations": total,
            "furcations_with_bpe": with_bpe,
            "furcations_with_patient": with_patient,
            "furcations_without_bpe": max(total - with_bpe, 0),
            "ambiguous_bpe_ids": int(ambiguous[0]["count"]) if ambiguous else 0,
            "sample_ambiguous_bpe_ids": [row["bpe_id"] for row in sample_ambiguous],
            "sample_unlinked_bpe_ids": [row["bpe_id"] for row in sample_unlinked],
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

    def count_appointments(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> int:
        starts_col = self._require_column("vwAppointmentDetails", ["appointmentDateTimevalue"])
        where_clause, params = self._build_date_filter(starts_col, date_from, date_to)
        rows = self._query(
            f"SELECT COUNT(1) AS count FROM dbo.vwAppointmentDetails WITH (NOLOCK){where_clause}",
            params,
        )
        return int(rows[0]["count"]) if rows else 0

    def count_treatments(self) -> int:
        rows = self._query("SELECT COUNT(1) AS count FROM dbo.Treatments WITH (NOLOCK)")
        return int(rows[0]["count"]) if rows else 0

    def count_users(self) -> int:
        rows = self._query("SELECT COUNT(1) AS count FROM dbo.Users WITH (NOLOCK)")
        return int(rows[0]["count"]) if rows else 0

    def count_treatment_transactions(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> int:
        patient_col = self._require_column("Transactions", ["PatientCode"])
        where_clause, params = self._build_range_filter(
            patient_col,
            patients_from,
            patients_to,
        )
        rows = self._query(
            "SELECT COUNT(1) AS count FROM dbo.Transactions WITH (NOLOCK)" + where_clause,
            params,
        )
        return int(rows[0]["count"]) if rows else 0

    def treatment_transactions_date_range(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        date_floor: date | None = None,
    ) -> dict[str, str | None]:
        patient_col = self._require_column("Transactions", ["PatientCode"])
        date_col = self._require_column("Transactions", ["Date"])
        where_clause, params = self._build_range_filter(
            patient_col,
            patients_from,
            patients_to,
        )
        if date_floor is not None:
            floor_dt = datetime.combine(date_floor, datetime.min.time())
            if where_clause:
                where_clause = f"{where_clause} AND {date_col} >= ?"
            else:
                where_clause = f"WHERE {date_col} >= ?"
            params.append(floor_dt)
        rows = self._query(
            f"SELECT MIN({date_col}) AS min_date, MAX({date_col}) AS max_date "
            f"FROM dbo.Transactions WITH (NOLOCK){where_clause}",
            params,
        )
        if not rows:
            return {"min": None, "max": None}
        return {
            "min": self._format_dt(rows[0].get("min_date")),
            "max": self._format_dt(rows[0].get("max_date")),
        }

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

    def count_tooth_systems(self) -> int:
        return self._count_table("ToothSystems")

    def count_tooth_surfaces(self) -> int:
        return self._count_table("ToothSurfaces")

    def count_chart_healing_actions(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> int:
        patient_col = self._pick_column("ChartHealingActions", ["PatientCode"])
        where_clause, params = self._build_range_filter(
            patient_col,
            patients_from,
            patients_to,
        ) if patient_col else ("", [])
        return self._count_table("ChartHealingActions", where_clause, params)

    def count_bpe_entries(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> int:
        patient_col = self._pick_column("BPE", ["PatientCode"])
        where_clause, params = self._build_range_filter(
            patient_col,
            patients_from,
            patients_to,
        ) if patient_col else ("", [])
        return self._count_table("BPE", where_clause, params)

    def count_bpe_furcations(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> int:
        patient_col = self._pick_column("BPEFurcation", ["PatientCode"])
        where_clause, params = self._build_range_filter(
            patient_col,
            patients_from,
            patients_to,
        ) if patient_col else ("", [])
        return self._count_table("BPEFurcation", where_clause, params)

    def count_perio_probes(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> int:
        patient_col = self._pick_column("PerioProbe", ["PatientCode"])
        where_clause, params = self._build_range_filter(
            patient_col,
            patients_from,
            patients_to,
        ) if patient_col else ("", [])
        return self._count_table("PerioProbe", where_clause, params)

    def count_perio_plaque(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> int:
        patient_col = self._pick_column("PerioPlaque", ["PatientCode"])
        where_clause, params = self._build_range_filter(
            patient_col,
            patients_from,
            patients_to,
        ) if patient_col else ("", [])
        return self._count_table("PerioPlaque", where_clause, params)

    def count_patient_notes(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> int:
        patient_col = self._pick_column("PatientNotes", ["PatientCode"])
        where_clause, params = self._build_range_filter(
            patient_col,
            patients_from,
            patients_to,
        ) if patient_col else ("", [])
        return self._count_table("PatientNotes", where_clause, params)

    def count_fixed_notes(self) -> int:
        return self._count_table("FixedNotes")

    def count_note_categories(self) -> int:
        return self._count_table("NoteCategories")

    def count_treatment_notes(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> int:
        patient_col = self._pick_column("TreatmentNotes", ["PatientCode"])
        where_clause, params = self._build_range_filter(
            patient_col,
            patients_from,
            patients_to,
        ) if patient_col else ("", [])
        return self._count_table("TreatmentNotes", where_clause, params)

    def count_temporary_notes(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> int:
        patient_col = self._pick_column("TemporaryNotes", ["PatientCode"])
        where_clause, params = self._build_range_filter(
            patient_col,
            patients_from,
            patients_to,
        ) if patient_col else ("", [])
        return self._count_table("TemporaryNotes", where_clause, params)

    def count_old_patient_notes(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> int:
        patient_col = self._pick_column("OldPatientNotes", ["PatientCode"])
        where_clause, params = self._build_range_filter(
            patient_col,
            patients_from,
            patients_to,
        ) if patient_col else ("", [])
        return self._count_table("OldPatientNotes", where_clause, params)

    def chart_healing_actions_date_range(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> dict[str, str] | None:
        date_col = self._pick_column(
            "ChartHealingActions",
            ["ActionDate", "Date", "CreatedDate", "ActionedDate", "ActionedOn"],
        )
        if not date_col:
            return None
        patient_col = self._pick_column("ChartHealingActions", ["PatientCode"])
        where_clause, params = self._build_range_filter(
            patient_col,
            patients_from,
            patients_to,
        ) if patient_col else ("", [])
        return self._date_range("ChartHealingActions", date_col, where_clause, params)

    def bpe_date_range(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> dict[str, str] | None:
        date_col = self._pick_column("BPE", ["Date", "BPEDate", "RecordedDate", "EntryDate"])
        if not date_col:
            return None
        patient_col = self._pick_column("BPE", ["PatientCode"])
        where_clause, params = self._build_range_filter(
            patient_col,
            patients_from,
            patients_to,
        ) if patient_col else ("", [])
        return self._date_range("BPE", date_col, where_clause, params)

    def patient_notes_date_range(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> dict[str, str] | None:
        date_col = self._pick_column("PatientNotes", ["Date", "NoteDate", "CreatedDate"])
        if not date_col:
            return None
        patient_col = self._pick_column("PatientNotes", ["PatientCode"])
        where_clause, params = self._build_range_filter(
            patient_col,
            patients_from,
            patients_to,
        ) if patient_col else ("", [])
        return self._date_range("PatientNotes", date_col, where_clause, params)

    def treatment_notes_date_range(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> dict[str, str] | None:
        date_col = self._pick_column("TreatmentNotes", ["Date", "NoteDate", "CreatedDate"])
        if not date_col:
            return None
        patient_col = self._pick_column("TreatmentNotes", ["PatientCode"])
        where_clause, params = self._build_range_filter(
            patient_col,
            patients_from,
            patients_to,
        ) if patient_col else ("", [])
        return self._date_range("TreatmentNotes", date_col, where_clause, params)

    def old_patient_notes_date_range(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> dict[str, str] | None:
        date_col = self._pick_column("OldPatientNotes", ["Date", "NoteDate", "CreatedDate"])
        if not date_col:
            return None
        patient_col = self._pick_column("OldPatientNotes", ["PatientCode"])
        where_clause, params = self._build_range_filter(
            patient_col,
            patients_from,
            patients_to,
        ) if patient_col else ("", [])
        return self._date_range("OldPatientNotes", date_col, where_clause, params)

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

    def appointment_date_range(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, str] | None:
        starts_col = self._pick_column("vwAppointmentDetails", ["appointmentDateTimevalue"])
        if not starts_col:
            return None
        where_clause, params = self._build_date_filter(starts_col, date_from, date_to)
        rows = self._query(
            f"SELECT MIN({starts_col}) AS min_date, MAX({starts_col}) AS max_date "
            f"FROM dbo.vwAppointmentDetails WITH (NOLOCK){where_clause}",
            params,
        )
        if not rows:
            return None
        min_date = rows[0].get("min_date")
        max_date = rows[0].get("max_date")
        return {
            "min": self._format_dt(min_date),
            "max": self._format_dt(max_date),
        }

    def appointment_patient_null_count(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> int:
        patient_col = self._require_column("vwAppointmentDetails", ["patientcode"])
        starts_col = self._require_column("vwAppointmentDetails", ["appointmentDateTimevalue"])
        where_clause, params = self._build_date_filter(starts_col, date_from, date_to)
        rows = self._query(
            "SELECT SUM(CASE WHEN {0} IS NULL THEN 1 ELSE 0 END) AS null_count "
            "FROM dbo.vwAppointmentDetails WITH (NOLOCK){1}".format(
                patient_col,
                where_clause,
            ),
            params,
        )
        return int(rows[0]["null_count"] or 0) if rows else 0

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

    def sample_appointments(self, limit: int = 10) -> list[dict[str, Any]]:
        appt_id_col = self._require_column("vwAppointmentDetails", ["apptid"])
        starts_col = self._require_column("vwAppointmentDetails", ["appointmentDateTimevalue"])
        duration_col = self._pick_column("vwAppointmentDetails", ["duration"])
        patient_col = self._pick_column("vwAppointmentDetails", ["patientcode"])
        provider_col = self._pick_column("vwAppointmentDetails", ["providerCode"])
        status_col = self._pick_column("vwAppointmentDetails", ["status"])
        cancelled_col = self._pick_column("vwAppointmentDetails", ["cancelled"])
        clinic_col = self._pick_column("vwAppointmentDetails", ["cliniccode"])
        treatment_col = self._pick_column("vwAppointmentDetails", ["treatmentcode"])
        type_col = self._pick_column("vwAppointmentDetails", ["appointmentType"])
        notes_col = self._pick_column("vwAppointmentDetails", ["notes"])
        flag_col = self._pick_column("vwAppointmentDetails", ["apptflag"])
        select_cols = [
            f"{appt_id_col} AS appointment_id",
            f"{starts_col} AS starts_at",
        ]
        if duration_col:
            select_cols.append(f"{duration_col} AS duration_minutes")
        if patient_col:
            select_cols.append(f"{patient_col} AS patient_code")
        if provider_col:
            select_cols.append(f"{provider_col} AS clinician_code")
        if status_col:
            select_cols.append(f"{status_col} AS status")
        if cancelled_col:
            select_cols.append(f"{cancelled_col} AS cancelled")
        if clinic_col:
            select_cols.append(f"{clinic_col} AS clinic_code")
        if treatment_col:
            select_cols.append(f"{treatment_col} AS treatment_code")
        if type_col:
            select_cols.append(f"{type_col} AS appointment_type")
        if notes_col:
            select_cols.append(f"{notes_col} AS notes")
        if flag_col:
            select_cols.append(f"{flag_col} AS appt_flag")
        rows = self._query(
            f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.vwAppointmentDetails WITH (NOLOCK) "
            f"ORDER BY {appt_id_col} ASC",
            [limit],
        )
        samples: list[dict[str, Any]] = []
        for row in rows:
            samples.append(
                {
                    "appointment_id": row.get("appointment_id"),
                    "starts_at": self._format_dt(row.get("starts_at")),
                    "duration_minutes": row.get("duration_minutes"),
                    "patient_code": row.get("patient_code"),
                    "clinician_code": row.get("clinician_code"),
                    "status": row.get("status"),
                    "cancelled": row.get("cancelled"),
                    "clinic_code": row.get("clinic_code"),
                    "treatment_code": row.get("treatment_code"),
                    "appointment_type": row.get("appointment_type"),
                    "notes": row.get("notes"),
                    "appt_flag": row.get("appt_flag"),
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

    def sample_users(self, limit: int = 10) -> list[dict[str, Any]]:
        user_code_col = self._require_column("Users", ["UserCode"])
        full_name_col = self._pick_column("Users", ["FullName"])
        title_col = self._pick_column("Users", ["Title"])
        forename_col = self._pick_column("Users", ["Forename", "FirstName"])
        surname_col = self._pick_column("Users", ["Surname", "LastName"])
        initials_col = self._pick_column("Users", ["Initials"])
        current_col = self._pick_column("Users", ["Current", "IsCurrent"])
        role_col = self._pick_column(
            "Users",
            ["Role", "UserType", "GradingUserType", "Grade", "Group", "AccessLevel"],
        )
        extended_nurse_col = self._pick_column("Users", ["IsExtendedDutyNurse"])
        promoter_col = self._pick_column("Users", ["IsOralHealthPromoter"])
        clinic_admin_col = self._pick_column("Users", ["IsClinicAdminSuperUser"])
        select_cols = [f"{user_code_col} AS user_code"]
        if full_name_col:
            select_cols.append(f"{full_name_col} AS full_name")
        if title_col:
            select_cols.append(f"{title_col} AS title")
        if forename_col:
            select_cols.append(f"{forename_col} AS forename")
        if surname_col:
            select_cols.append(f"{surname_col} AS surname")
        if initials_col:
            select_cols.append(f"{initials_col} AS initials")
        if current_col:
            current_expr = f"[{current_col}]" if current_col.lower() == "current" else current_col
            select_cols.append(f"{current_expr} AS is_current")
        if role_col:
            role_expr = (
                f"[{role_col}]"
                if role_col.lower() in {"role", "group"}
                else role_col
            )
            select_cols.append(f"{role_expr} AS role_value")
        if extended_nurse_col:
            select_cols.append(f"{extended_nurse_col} AS is_extended_duty_nurse")
        if promoter_col:
            select_cols.append(f"{promoter_col} AS is_oral_health_promoter")
        if clinic_admin_col:
            select_cols.append(f"{clinic_admin_col} AS is_clinic_admin_super_user")
        rows = self._query(
            f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.Users WITH (NOLOCK) "
            f"ORDER BY {user_code_col} ASC",
            [limit],
        )
        samples: list[dict[str, Any]] = []
        for row in rows:
            samples.append(
                {
                    "user_code": row.get("user_code"),
                    "full_name": row.get("full_name"),
                    "title": row.get("title"),
                    "forename": row.get("forename"),
                    "surname": row.get("surname"),
                    "initials": row.get("initials"),
                    "is_current": _coerce_bool(row.get("is_current"), default=False),
                    "role": _build_user_role(
                        role_value=row.get("role_value"),
                        is_extended_duty_nurse=row.get("is_extended_duty_nurse"),
                        is_oral_health_promoter=row.get("is_oral_health_promoter"),
                        is_clinic_admin_super_user=row.get("is_clinic_admin_super_user"),
                    ),
                }
            )
        return samples

    def sample_treatment_transactions(
        self,
        limit: int = 10,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> list[dict[str, Any]]:
        patient_col = self._require_column("Transactions", ["PatientCode"])
        date_col = self._require_column("Transactions", ["Date"])
        ref_col = self._require_column("Transactions", ["RefId"])
        trans_col = self._pick_column("Transactions", ["TransCode"])
        code_col = self._pick_column("Transactions", ["CodeID"])
        patient_cost_col = self._pick_column("Transactions", ["PatientCost"])
        dpb_cost_col = self._pick_column("Transactions", ["DPBCost"])
        recorded_by_col = self._pick_column("Transactions", ["RecordedBy"])
        user_code_col = self._pick_column("Transactions", ["UserCode"])
        tp_number_col = self._pick_column("Transactions", ["TPNumber"])
        tp_item_col = self._pick_column("Transactions", ["TPItem"])

        where_clause, params = self._build_range_filter(
            patient_col,
            patients_from,
            patients_to,
        )
        select_cols = [
            f"{ref_col} AS transaction_id",
            f"{patient_col} AS patient_code",
            f"{date_col} AS performed_at",
        ]
        if code_col:
            select_cols.append(f"{code_col} AS treatment_code")
        if trans_col:
            select_cols.append(f"{trans_col} AS trans_code")
        if patient_cost_col:
            select_cols.append(f"{patient_cost_col} AS patient_cost")
        if dpb_cost_col:
            select_cols.append(f"{dpb_cost_col} AS dpb_cost")
        if recorded_by_col:
            select_cols.append(f"{recorded_by_col} AS recorded_by")
        if user_code_col:
            select_cols.append(f"{user_code_col} AS user_code")
        if tp_number_col:
            select_cols.append(f"{tp_number_col} AS tp_number")
        if tp_item_col:
            select_cols.append(f"{tp_item_col} AS tp_item")
        rows = self._query(
            f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.Transactions WITH (NOLOCK) "
            f"{where_clause} ORDER BY {date_col} DESC",
            [limit, *params],
        )
        samples: list[dict[str, Any]] = []
        for row in rows:
            samples.append(
                {
                    "transaction_id": row.get("transaction_id"),
                    "patient_code": row.get("patient_code"),
                    "performed_at": self._format_dt(row.get("performed_at")),
                    "treatment_code": row.get("treatment_code"),
                    "trans_code": row.get("trans_code"),
                    "patient_cost": self._format_money(row.get("patient_cost")),
                    "dpb_cost": self._format_money(row.get("dpb_cost")),
                    "recorded_by": row.get("recorded_by"),
                    "user_code": row.get("user_code"),
                    "tp_number": row.get("tp_number"),
                    "tp_item": row.get("tp_item"),
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

    def sample_tooth_systems(self, limit: int = 10) -> list[dict[str, Any]]:
        id_col = self._require_column(
            "ToothSystems",
            ["ToothSystemId", "ToothSystemID", "ToothSystem"],
        )
        name_col = self._pick_column("ToothSystems", ["Name", "SystemName"])
        desc_col = self._pick_column("ToothSystems", ["Description", "Notes"])
        sort_col = self._pick_column("ToothSystems", ["SortOrder", "Order", "DisplayOrder"])
        default_col = self._pick_column("ToothSystems", ["IsDefault", "DefaultSystem"])
        select_cols = [f"{id_col} AS tooth_system_id"]
        if name_col:
            select_cols.append(f"{name_col} AS name")
        if desc_col:
            select_cols.append(f"{desc_col} AS description")
        if sort_col:
            select_cols.append(f"{sort_col} AS sort_order")
        if default_col:
            select_cols.append(f"{default_col} AS is_default")
        rows = self._query(
            f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.ToothSystems WITH (NOLOCK) "
            f"ORDER BY {id_col}",
            [limit],
        )
        samples: list[dict[str, Any]] = []
        for row in rows:
            samples.append(
                {
                    "tooth_system_id": row.get("tooth_system_id"),
                    "name": row.get("name"),
                    "description": row.get("description"),
                    "sort_order": row.get("sort_order"),
                    "is_default": _coerce_bool(row.get("is_default"), default=False)
                    if row.get("is_default") is not None
                    else None,
                }
            )
        return samples

    def sample_tooth_surfaces(self, limit: int = 10) -> list[dict[str, Any]]:
        tooth_col = self._require_column("ToothSurfaces", ["ToothId", "ToothID", "Tooth"])
        surface_col = self._require_column(
            "ToothSurfaces",
            ["SurfaceNo", "SurfaceNumber", "Surface"],
        )
        label_col = self._pick_column("ToothSurfaces", ["Label", "SurfaceLabel", "Name"])
        short_col = self._pick_column("ToothSurfaces", ["ShortLabel", "Abbrev"])
        sort_col = self._pick_column("ToothSurfaces", ["SortOrder", "Order", "DisplayOrder"])
        select_cols = [f"{tooth_col} AS tooth_id", f"{surface_col} AS surface_no"]
        if label_col:
            select_cols.append(f"{label_col} AS label")
        if short_col:
            select_cols.append(f"{short_col} AS short_label")
        if sort_col:
            select_cols.append(f"{sort_col} AS sort_order")
        rows = self._query(
            f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.ToothSurfaces WITH (NOLOCK) "
            f"ORDER BY {tooth_col}, {surface_col}",
            [limit],
        )
        samples: list[dict[str, Any]] = []
        for row in rows:
            samples.append(
                {
                    "tooth_id": row.get("tooth_id"),
                    "surface_no": row.get("surface_no"),
                    "label": row.get("label"),
                    "short_label": row.get("short_label"),
                    "sort_order": row.get("sort_order"),
                }
            )
        return samples

    def sample_chart_healing_actions(
        self,
        limit: int = 10,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> list[dict[str, Any]]:
        id_col = self._require_column(
            "ChartHealingActions",
            ["ID", "ActionID", "ChartHealingActionID"],
        )
        patient_col = self._pick_column("ChartHealingActions", ["PatientCode"])
        date_col = self._pick_column(
            "ChartHealingActions",
            ["ActionDate", "Date", "CreatedDate", "ActionedDate", "ActionedOn"],
        )
        code_col = self._pick_column("ChartHealingActions", ["CodeID", "CodeId"])
        tooth_col = self._pick_column("ChartHealingActions", ["Tooth"])
        surface_col = self._pick_column("ChartHealingActions", ["Surface"])
        status_col = self._pick_column("ChartHealingActions", ["Status", "StatusCode"])
        select_cols = [f"{id_col} AS action_id"]
        if patient_col:
            select_cols.append(f"{patient_col} AS patient_code")
        if date_col:
            select_cols.append(f"{date_col} AS action_date")
        if code_col:
            select_cols.append(f"{code_col} AS code_id")
        if tooth_col:
            select_cols.append(f"{tooth_col} AS tooth")
        if surface_col:
            select_cols.append(f"{surface_col} AS surface")
        if status_col:
            select_cols.append(f"{status_col} AS status")
        where_clause, params = ("", [])
        if patient_col:
            where_clause, params = self._build_range_filter(
                patient_col,
                patients_from,
                patients_to,
            )
        rows = self._query(
            f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.ChartHealingActions WITH (NOLOCK) "
            f"{where_clause} ORDER BY {id_col}",
            [limit, *params],
        )
        samples: list[dict[str, Any]] = []
        for row in rows:
            samples.append(
                {
                    "action_id": row.get("action_id"),
                    "patient_code": row.get("patient_code"),
                    "action_date": self._format_dt(row.get("action_date")),
                    "code_id": row.get("code_id"),
                    "tooth": row.get("tooth"),
                    "surface": row.get("surface"),
                    "status": row.get("status"),
                }
            )
        return samples

    def sample_bpe_entries(
        self,
        limit: int = 10,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> list[dict[str, Any]]:
        patient_col = self._pick_column("BPE", ["PatientCode"])
        bpe_id_col = self._pick_column("BPE", ["BPEID", "BPEId", "ID"])
        date_col = self._pick_column("BPE", ["Date", "BPEDate", "RecordedDate", "EntryDate"])
        sextant_cols = [
            self._pick_column("BPE", [f"Sextant{i}", f"Sextant{i}Score"]) for i in range(1, 7)
        ]
        select_cols = []
        if bpe_id_col:
            select_cols.append(f"{bpe_id_col} AS bpe_id")
        if patient_col:
            select_cols.append(f"{patient_col} AS patient_code")
        if date_col:
            select_cols.append(f"{date_col} AS recorded_at")
        for idx, col in enumerate(sextant_cols, start=1):
            if col:
                select_cols.append(f"{col} AS sextant_{idx}")
        if not select_cols:
            return []
        where_clause, params = ("", [])
        if patient_col:
            where_clause, params = self._build_range_filter(
                patient_col,
                patients_from,
                patients_to,
            )
        order_col = bpe_id_col or patient_col or date_col
        rows = self._query(
            f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.BPE WITH (NOLOCK) "
            f"{where_clause} ORDER BY {order_col}",
            [limit, *params],
        )
        samples: list[dict[str, Any]] = []
        for row in rows:
            entry = {
                "bpe_id": row.get("bpe_id"),
                "patient_code": row.get("patient_code"),
                "recorded_at": self._format_dt(row.get("recorded_at")),
            }
            for idx in range(1, 7):
                entry[f"sextant_{idx}"] = row.get(f"sextant_{idx}")
            samples.append(entry)
        return samples

    def sample_bpe_furcations(
        self,
        limit: int = 10,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> list[dict[str, Any]]:
        id_col = self._pick_column("BPEFurcation", ["pKey", "ID", "BPEFurcationID"])
        patient_col = self._pick_column("BPEFurcation", ["PatientCode"])
        bpe_id_col = self._pick_column("BPEFurcation", ["BPEID", "BPEId"])
        tooth_col = self._pick_column("BPEFurcation", ["Tooth"])
        furcation_col = self._pick_column("BPEFurcation", ["Furcation", "FurcationScore"])
        select_cols = []
        if id_col:
            select_cols.append(f"{id_col} AS furcation_id")
        if patient_col:
            select_cols.append(f"{patient_col} AS patient_code")
        if bpe_id_col:
            select_cols.append(f"{bpe_id_col} AS bpe_id")
        if tooth_col:
            select_cols.append(f"{tooth_col} AS tooth")
        if furcation_col:
            select_cols.append(f"{furcation_col} AS furcation")
        if not select_cols:
            return []
        where_clause, params = ("", [])
        if patient_col:
            where_clause, params = self._build_range_filter(
                patient_col,
                patients_from,
                patients_to,
            )
        order_col = id_col or bpe_id_col or patient_col
        rows = self._query(
            f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.BPEFurcation WITH (NOLOCK) "
            f"{where_clause} ORDER BY {order_col}",
            [limit, *params],
        )
        samples: list[dict[str, Any]] = []
        for row in rows:
            samples.append(
                {
                    "furcation_id": row.get("furcation_id"),
                    "patient_code": row.get("patient_code"),
                    "bpe_id": row.get("bpe_id"),
                    "tooth": row.get("tooth"),
                    "furcation": row.get("furcation"),
                }
            )
        return samples

    def sample_perio_probes(
        self,
        limit: int = 10,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> list[dict[str, Any]]:
        rows = list(
            self.list_perio_probes(
                patients_from=patients_from,
                patients_to=patients_to,
                limit=limit,
            )
        )
        samples: list[dict[str, Any]] = []
        for row in rows:
            samples.append(
                {
                    "trans_id": row.trans_id,
                    "patient_code": row.patient_code,
                    "tooth": row.tooth,
                    "probing_point": row.probing_point,
                    "depth": row.depth,
                }
            )
        return samples

    def sample_perio_plaque(
        self,
        limit: int = 10,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> list[dict[str, Any]]:
        trans_col = self._pick_column("PerioPlaque", ["TransId", "TransID"])
        patient_col = self._pick_column("PerioPlaque", ["PatientCode"])
        tooth_col = self._pick_column("PerioPlaque", ["Tooth"])
        plaque_col = self._pick_column("PerioPlaque", ["Plaque", "PlaqueScore"])
        select_cols = []
        if trans_col:
            select_cols.append(f"{trans_col} AS trans_id")
        if patient_col:
            select_cols.append(f"{patient_col} AS patient_code")
        if tooth_col:
            select_cols.append(f"{tooth_col} AS tooth")
        if plaque_col:
            select_cols.append(f"{plaque_col} AS plaque")
        if not select_cols:
            return []
        where_clause, params = ("", [])
        if patient_col:
            where_clause, params = self._build_range_filter(
                patient_col,
                patients_from,
                patients_to,
            )
        order_col = trans_col or patient_col
        rows = self._query(
            f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.PerioPlaque WITH (NOLOCK) "
            f"{where_clause} ORDER BY {order_col}",
            [limit, *params],
        )
        samples: list[dict[str, Any]] = []
        for row in rows:
            samples.append(
                {
                    "trans_id": row.get("trans_id"),
                    "patient_code": row.get("patient_code"),
                    "tooth": row.get("tooth"),
                    "plaque": row.get("plaque"),
                }
            )
        return samples

    def sample_patient_notes(
        self,
        limit: int = 10,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> list[dict[str, Any]]:
        patient_col = self._pick_column("PatientNotes", ["PatientCode"])
        note_no_col = self._pick_column("PatientNotes", ["NoteNumber", "NoteNo"])
        date_col = self._pick_column("PatientNotes", ["Date", "NoteDate", "CreatedDate"])
        note_col = self._pick_column("PatientNotes", ["Note", "Notes", "NoteText", "NoteBody"])
        select_cols = []
        if patient_col:
            select_cols.append(f"{patient_col} AS patient_code")
        if note_no_col:
            select_cols.append(f"{note_no_col} AS note_number")
        if date_col:
            select_cols.append(f"{date_col} AS note_date")
        if note_col:
            select_cols.append(f"{note_col} AS note")
        if not select_cols:
            return []
        where_clause, params = ("", [])
        if patient_col:
            where_clause, params = self._build_range_filter(
                patient_col,
                patients_from,
                patients_to,
            )
        order_col = note_no_col or patient_col or date_col
        rows = self._query(
            f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.PatientNotes WITH (NOLOCK) "
            f"{where_clause} ORDER BY {order_col}",
            [limit, *params],
        )
        samples: list[dict[str, Any]] = []
        for row in rows:
            samples.append(
                {
                    "patient_code": row.get("patient_code"),
                    "note_number": row.get("note_number"),
                    "note_date": self._format_dt(row.get("note_date")),
                    "note": row.get("note"),
                }
            )
        return samples

    def sample_fixed_notes(self, limit: int = 10) -> list[dict[str, Any]]:
        code_col = self._require_column("FixedNotes", ["FixedNoteCode"])
        desc_col = self._pick_column("FixedNotes", ["Description", "NoteDesc"])
        note_col = self._pick_column("FixedNotes", ["Note", "Notes", "NoteText"])
        select_cols = [f"{code_col} AS fixed_note_code"]
        if desc_col:
            select_cols.append(f"{desc_col} AS description")
        if note_col:
            select_cols.append(f"{note_col} AS note")
        rows = self._query(
            f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.FixedNotes WITH (NOLOCK) "
            f"ORDER BY {code_col}",
            [limit],
        )
        return [
            {
                "fixed_note_code": row.get("fixed_note_code"),
                "description": row.get("description"),
                "note": row.get("note"),
            }
            for row in rows
        ]

    def sample_note_categories(self, limit: int = 10) -> list[dict[str, Any]]:
        code_col = self._require_column("NoteCategories", ["CategoryNumber", "CategoryNo"])
        desc_col = self._pick_column("NoteCategories", ["Description", "Name"])
        select_cols = [f"{code_col} AS category_number"]
        if desc_col:
            select_cols.append(f"{desc_col} AS description")
        rows = self._query(
            f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.NoteCategories WITH (NOLOCK) "
            f"ORDER BY {code_col}",
            [limit],
        )
        return [
            {
                "category_number": row.get("category_number"),
                "description": row.get("description"),
            }
            for row in rows
        ]

    def sample_treatment_notes(
        self,
        limit: int = 10,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> list[dict[str, Any]]:
        note_id_col = self._require_column("TreatmentNotes", ["NoteID", "NoteId"])
        patient_col = self._pick_column("TreatmentNotes", ["PatientCode"])
        date_col = self._pick_column("TreatmentNotes", ["Date", "NoteDate", "CreatedDate"])
        note_col = self._pick_column("TreatmentNotes", ["Note", "Notes", "NoteText", "NoteBody"])
        select_cols = [f"{note_id_col} AS note_id"]
        if patient_col:
            select_cols.append(f"{patient_col} AS patient_code")
        if date_col:
            select_cols.append(f"{date_col} AS note_date")
        if note_col:
            select_cols.append(f"{note_col} AS note")
        where_clause, params = ("", [])
        if patient_col:
            where_clause, params = self._build_range_filter(
                patient_col,
                patients_from,
                patients_to,
            )
        rows = self._query(
            f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.TreatmentNotes WITH (NOLOCK) "
            f"{where_clause} ORDER BY {note_id_col}",
            [limit, *params],
        )
        samples: list[dict[str, Any]] = []
        for row in rows:
            samples.append(
                {
                    "note_id": row.get("note_id"),
                    "patient_code": row.get("patient_code"),
                    "note_date": self._format_dt(row.get("note_date")),
                    "note": row.get("note"),
                }
            )
        return samples

    def sample_temporary_notes(
        self,
        limit: int = 10,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> list[dict[str, Any]]:
        patient_col = self._require_column("TemporaryNotes", ["PatientCode"])
        note_col = self._pick_column("TemporaryNotes", ["Note", "Notes", "NoteText"])
        updated_col = self._pick_column("TemporaryNotes", ["UpdatedAt", "LastEditDate", "Date"])
        select_cols = [f"{patient_col} AS patient_code"]
        if note_col:
            select_cols.append(f"{note_col} AS note")
        if updated_col:
            select_cols.append(f"{updated_col} AS legacy_updated_at")
        where_clause, params = self._build_range_filter(
            patient_col,
            patients_from,
            patients_to,
        )
        rows = self._query(
            f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.TemporaryNotes WITH (NOLOCK) "
            f"{where_clause} ORDER BY {patient_col}",
            [limit, *params],
        )
        samples: list[dict[str, Any]] = []
        for row in rows:
            samples.append(
                {
                    "patient_code": row.get("patient_code"),
                    "note": row.get("note"),
                    "legacy_updated_at": self._format_dt(row.get("legacy_updated_at")),
                }
            )
        return samples

    def sample_old_patient_notes(
        self,
        limit: int = 10,
        patients_from: int | None = None,
        patients_to: int | None = None,
    ) -> list[dict[str, Any]]:
        patient_col = self._pick_column("OldPatientNotes", ["PatientCode"])
        note_no_col = self._pick_column("OldPatientNotes", ["NoteNumber", "NoteNo"])
        date_col = self._pick_column("OldPatientNotes", ["Date", "NoteDate", "CreatedDate"])
        note_col = self._pick_column("OldPatientNotes", ["Note", "Notes", "NoteText", "NoteBody"])
        select_cols = []
        if patient_col:
            select_cols.append(f"{patient_col} AS patient_code")
        if note_no_col:
            select_cols.append(f"{note_no_col} AS note_number")
        if date_col:
            select_cols.append(f"{date_col} AS note_date")
        if note_col:
            select_cols.append(f"{note_col} AS note")
        if not select_cols:
            return []
        where_clause, params = ("", [])
        if patient_col:
            where_clause, params = self._build_range_filter(
                patient_col,
                patients_from,
                patients_to,
            )
        order_col = note_no_col or patient_col or date_col
        rows = self._query(
            f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.OldPatientNotes WITH (NOLOCK) "
            f"{where_clause} ORDER BY {order_col}",
            [limit, *params],
        )
        samples: list[dict[str, Any]] = []
        for row in rows:
            samples.append(
                {
                    "patient_code": row.get("patient_code"),
                    "note_number": row.get("note_number"),
                    "note_date": self._format_dt(row.get("note_date")),
                    "note": row.get("note"),
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

    def stream_appointments(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int | None = None,
    ) -> Iterable[R4AppointmentRecord]:
        appt_id_col = self._require_column("vwAppointmentDetails", ["apptid"])
        starts_col = self._require_column("vwAppointmentDetails", ["appointmentDateTimevalue"])
        duration_col = self._pick_column("vwAppointmentDetails", ["duration"])
        patient_col = self._pick_column("vwAppointmentDetails", ["patientcode"])
        provider_col = self._pick_column("vwAppointmentDetails", ["providerCode"])
        status_col = self._pick_column("vwAppointmentDetails", ["status"])
        cancelled_col = self._pick_column("vwAppointmentDetails", ["cancelled"])
        clinic_col = self._pick_column("vwAppointmentDetails", ["cliniccode"])
        treatment_col = self._pick_column("vwAppointmentDetails", ["treatmentcode"])
        type_col = self._pick_column("vwAppointmentDetails", ["appointmentType"])
        notes_col = self._pick_column("vwAppointmentDetails", ["notes"])
        flag_col = self._pick_column("vwAppointmentDetails", ["apptflag"])

        last_id = 0
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
            if last_id:
                where_parts.append(f"{appt_id_col} > ?")
                params.append(last_id)
            where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
            select_cols = [
                f"{appt_id_col} AS appointment_id",
                f"{starts_col} AS starts_at",
            ]
            if duration_col:
                select_cols.append(f"{duration_col} AS duration_minutes")
            if patient_col:
                select_cols.append(f"{patient_col} AS patient_code")
            if provider_col:
                select_cols.append(f"{provider_col} AS clinician_code")
            if status_col:
                select_cols.append(f"{status_col} AS status")
            if cancelled_col:
                select_cols.append(f"{cancelled_col} AS cancelled")
            if clinic_col:
                select_cols.append(f"{clinic_col} AS clinic_code")
            if treatment_col:
                select_cols.append(f"{treatment_col} AS treatment_code")
            if type_col:
                select_cols.append(f"{type_col} AS appointment_type")
            if notes_col:
                select_cols.append(f"{notes_col} AS notes")
            if flag_col:
                select_cols.append(f"{flag_col} AS appt_flag")
            rows = self._query(
                f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.vwAppointmentDetails WITH (NOLOCK) "
                f"{where_sql} ORDER BY {appt_id_col} ASC",
                [batch_size, *params],
            )
            if not rows:
                break
            for row in rows:
                appointment_id = row.get("appointment_id")
                if appointment_id is None:
                    continue
                starts_at = row.get("starts_at")
                if starts_at is None:
                    continue
                last_id = int(appointment_id)
                duration_raw = row.get("duration_minutes")
                try:
                    duration_minutes = int(duration_raw) if duration_raw is not None else None
                except (TypeError, ValueError):
                    duration_minutes = None
                ends_at = (
                    starts_at + timedelta(minutes=duration_minutes)
                    if duration_minutes is not None
                    else None
                )
                patient_code = row.get("patient_code")
                clinician_code = row.get("clinician_code")
                clinic_code = row.get("clinic_code")
                treatment_code = row.get("treatment_code")
                appt_flag = row.get("appt_flag")
                yield R4AppointmentRecord(
                    appointment_id=int(appointment_id),
                    patient_code=int(patient_code) if patient_code is not None else None,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    duration_minutes=duration_minutes,
                    clinician_code=int(clinician_code) if clinician_code is not None else None,
                    status=(row.get("status") or "").strip() or None,
                    cancelled=_coerce_bool(row.get("cancelled"), default=False)
                    if row.get("cancelled") is not None
                    else None,
                    clinic_code=int(clinic_code) if clinic_code is not None else None,
                    treatment_code=int(treatment_code) if treatment_code is not None else None,
                    appointment_type=(row.get("appointment_type") or "").strip() or None,
                    notes=(row.get("notes") or "").strip() or None,
                    appt_flag=int(appt_flag) if appt_flag is not None else None,
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

    def list_users(self, limit: int | None = None) -> Iterable[R4User]:
        return self.stream_users(limit=limit)

    def stream_users(self, limit: int | None = None) -> Iterable[R4User]:
        user_code_col = self._require_column("Users", ["UserCode"])
        full_name_col = self._pick_column("Users", ["FullName"])
        title_col = self._pick_column("Users", ["Title"])
        forename_col = self._pick_column("Users", ["Forename", "FirstName"])
        surname_col = self._pick_column("Users", ["Surname", "LastName"])
        initials_col = self._pick_column("Users", ["Initials"])
        current_col = self._pick_column("Users", ["Current", "IsCurrent"])
        role_col = self._pick_column(
            "Users",
            ["Role", "UserType", "GradingUserType", "Grade", "Group", "AccessLevel"],
        )
        extended_nurse_col = self._pick_column("Users", ["IsExtendedDutyNurse"])
        promoter_col = self._pick_column("Users", ["IsOralHealthPromoter"])
        clinic_admin_col = self._pick_column("Users", ["IsClinicAdminSuperUser"])

        last_code = 0
        remaining = limit
        batch_size = 500
        while True:
            if remaining is not None:
                if remaining <= 0:
                    break
                batch_size = min(batch_size, remaining)
            select_cols = [f"{user_code_col} AS user_code"]
            if full_name_col:
                select_cols.append(f"{full_name_col} AS full_name")
            if title_col:
                select_cols.append(f"{title_col} AS title")
            if forename_col:
                select_cols.append(f"{forename_col} AS forename")
            if surname_col:
                select_cols.append(f"{surname_col} AS surname")
            if initials_col:
                select_cols.append(f"{initials_col} AS initials")
            if current_col:
                current_expr = f"[{current_col}]" if current_col.lower() == "current" else current_col
                select_cols.append(f"{current_expr} AS is_current")
            if role_col:
                role_expr = (
                    f"[{role_col}]"
                    if role_col.lower() in {"role", "group"}
                    else role_col
                )
                select_cols.append(f"{role_expr} AS role_value")
            if extended_nurse_col:
                select_cols.append(f"{extended_nurse_col} AS is_extended_duty_nurse")
            if promoter_col:
                select_cols.append(f"{promoter_col} AS is_oral_health_promoter")
            if clinic_admin_col:
                select_cols.append(f"{clinic_admin_col} AS is_clinic_admin_super_user")
            rows = self._query(
                f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.Users WITH (NOLOCK) "
                f"WHERE {user_code_col} > ? ORDER BY {user_code_col}",
                [batch_size, last_code],
            )
            if not rows:
                break
            for row in rows:
                user_code = row.get("user_code")
                if user_code is None:
                    continue
                last_code = int(user_code)
                yield R4User(
                    user_code=last_code,
                    full_name=(row.get("full_name") or "").strip() or None,
                    title=(row.get("title") or "").strip() or None,
                    forename=(row.get("forename") or "").strip() or None,
                    surname=(row.get("surname") or "").strip() or None,
                    initials=(row.get("initials") or "").strip() or None,
                    is_current=_coerce_bool(row.get("is_current"), default=False),
                    role=_build_user_role(
                        role_value=row.get("role_value"),
                        is_extended_duty_nurse=row.get("is_extended_duty_nurse"),
                        is_oral_health_promoter=row.get("is_oral_health_promoter"),
                        is_clinic_admin_super_user=row.get("is_clinic_admin_super_user"),
                    ),
                )
                if remaining is not None:
                    remaining -= 1

    def stream_treatment_transactions(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4TreatmentTransaction]:
        patient_col = self._require_column("Transactions", ["PatientCode"])
        date_col = self._require_column("Transactions", ["Date"])
        ref_col = self._require_column("Transactions", ["RefId"])
        trans_col = self._pick_column("Transactions", ["TransCode"])
        code_col = self._pick_column("Transactions", ["CodeID"])
        patient_cost_col = self._pick_column("Transactions", ["PatientCost"])
        dpb_cost_col = self._pick_column("Transactions", ["DPBCost"])
        recorded_by_col = self._pick_column("Transactions", ["RecordedBy"])
        user_code_col = self._pick_column("Transactions", ["UserCode"])
        tp_number_col = self._pick_column("Transactions", ["TPNumber"])
        tp_item_col = self._pick_column("Transactions", ["TPItem"])

        last_ref = 0
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
                patient_col,
                patients_from,
                patients_to,
            )
            if range_clause:
                where_parts.append(range_clause.replace("WHERE", "").strip())
                params.extend(range_params)
            where_parts.append(f"{ref_col} > ?")
            params.append(last_ref)
            where_sql = f"WHERE {' AND '.join(where_parts)}"
            select_cols = [
                f"{ref_col} AS transaction_id",
                f"{patient_col} AS patient_code",
                f"{date_col} AS performed_at",
            ]
            if code_col:
                select_cols.append(f"{code_col} AS treatment_code")
            if trans_col:
                select_cols.append(f"{trans_col} AS trans_code")
            if patient_cost_col:
                select_cols.append(f"{patient_cost_col} AS patient_cost")
            if dpb_cost_col:
                select_cols.append(f"{dpb_cost_col} AS dpb_cost")
            if recorded_by_col:
                select_cols.append(f"{recorded_by_col} AS recorded_by")
            if user_code_col:
                select_cols.append(f"{user_code_col} AS user_code")
            if tp_number_col:
                select_cols.append(f"{tp_number_col} AS tp_number")
            if tp_item_col:
                select_cols.append(f"{tp_item_col} AS tp_item")
            rows = self._query(
                f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.Transactions WITH (NOLOCK) "
                f"{where_sql} ORDER BY {ref_col} ASC",
                [batch_size, *params],
            )
            if not rows:
                break
            for row in rows:
                ref_id = row.get("transaction_id")
                if ref_id is None:
                    continue
                last_ref = int(ref_id)
                performed_at = row.get("performed_at")
                if performed_at is None:
                    continue
                yield R4TreatmentTransaction(
                    transaction_id=last_ref,
                    patient_code=int(row.get("patient_code")),
                    performed_at=performed_at,
                    treatment_code=row.get("treatment_code"),
                    trans_code=row.get("trans_code"),
                    patient_cost=row.get("patient_cost"),
                    dpb_cost=row.get("dpb_cost"),
                    recorded_by=row.get("recorded_by"),
                    user_code=row.get("user_code"),
                    tp_number=row.get("tp_number"),
                    tp_item=row.get("tp_item"),
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

    def list_tooth_systems(self, limit: int | None = None) -> Iterable[R4ToothSystem]:
        id_col = self._require_column(
            "ToothSystems",
            ["ToothSystemId", "ToothSystemID", "ToothSystem"],
        )
        name_col = self._pick_column("ToothSystems", ["Name", "SystemName"])
        desc_col = self._pick_column("ToothSystems", ["Description", "Notes"])
        sort_col = self._pick_column("ToothSystems", ["SortOrder", "Order", "DisplayOrder"])
        default_col = self._pick_column("ToothSystems", ["IsDefault", "DefaultSystem"])
        last_id: int | None = None
        remaining = limit
        batch_size = 500
        while True:
            if remaining is not None:
                if remaining <= 0:
                    break
                batch_size = min(batch_size, remaining)
            where_clause = ""
            params: list[Any] = []
            if last_id is not None:
                where_clause = f"WHERE {id_col} > ?"
                params.append(last_id)
            select_cols = [f"{id_col} AS tooth_system_id"]
            if name_col:
                select_cols.append(f"{name_col} AS name")
            if desc_col:
                select_cols.append(f"{desc_col} AS description")
            if sort_col:
                select_cols.append(f"{sort_col} AS sort_order")
            if default_col:
                select_cols.append(f"{default_col} AS is_default")
            rows = self._query(
                f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.ToothSystems WITH (NOLOCK) "
                f"{where_clause} ORDER BY {id_col}",
                [batch_size, *params],
            )
            if not rows:
                break
            for row in rows:
                system_id = row.get("tooth_system_id")
                if system_id is None:
                    continue
                last_id = int(system_id)
                yield R4ToothSystem(
                    tooth_system_id=last_id,
                    name=(row.get("name") or "").strip() or None,
                    description=(row.get("description") or "").strip() or None,
                    sort_order=int(row["sort_order"]) if row.get("sort_order") is not None else None,
                    is_default=_coerce_bool(row.get("is_default"), default=False),
                )
                if remaining is not None:
                    remaining -= 1

    def list_tooth_surfaces(self, limit: int | None = None) -> Iterable[R4ToothSurface]:
        tooth_col = self._require_column("ToothSurfaces", ["ToothId", "ToothID", "Tooth"])
        surface_col = self._require_column(
            "ToothSurfaces",
            ["SurfaceNo", "SurfaceNumber", "Surface"],
        )
        label_col = self._pick_column("ToothSurfaces", ["Label", "SurfaceLabel", "Name"])
        short_col = self._pick_column("ToothSurfaces", ["ShortLabel", "Abbrev"])
        sort_col = self._pick_column("ToothSurfaces", ["SortOrder", "Order", "DisplayOrder"])
        last_tooth: int | None = None
        last_surface: int | None = None
        remaining = limit
        batch_size = 500
        while True:
            if remaining is not None:
                if remaining <= 0:
                    break
                batch_size = min(batch_size, remaining)
            where_parts: list[str] = []
            params: list[Any] = []
            if last_tooth is not None and last_surface is not None:
                where_parts.append(
                    f"({tooth_col} > ? OR ({tooth_col} = ? AND {surface_col} > ?))"
                )
                params.extend([last_tooth, last_tooth, last_surface])
            where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
            select_cols = [f"{tooth_col} AS tooth_id", f"{surface_col} AS surface_no"]
            if label_col:
                select_cols.append(f"{label_col} AS label")
            if short_col:
                select_cols.append(f"{short_col} AS short_label")
            if sort_col:
                select_cols.append(f"{sort_col} AS sort_order")
            rows = self._query(
                f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.ToothSurfaces WITH (NOLOCK) "
                f"{where_sql} ORDER BY {tooth_col} ASC, {surface_col} ASC",
                [batch_size, *params],
            )
            if not rows:
                break
            for row in rows:
                tooth_id = row.get("tooth_id")
                surface_no = row.get("surface_no")
                if tooth_id is None or surface_no is None:
                    continue
                last_tooth = int(tooth_id)
                last_surface = int(surface_no)
                yield R4ToothSurface(
                    tooth_id=last_tooth,
                    surface_no=last_surface,
                    label=(row.get("label") or "").strip() or None,
                    short_label=(row.get("short_label") or "").strip() or None,
                    sort_order=int(row["sort_order"]) if row.get("sort_order") is not None else None,
                )
                if remaining is not None:
                    remaining -= 1

    def list_chart_healing_actions(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4ChartHealingAction]:
        id_col = self._require_column(
            "ChartHealingActions",
            ["ID", "ActionID", "ChartHealingActionID"],
        )
        patient_col = self._pick_column("ChartHealingActions", ["PatientCode"])
        appt_need_col = self._pick_column(
            "ChartHealingActions",
            ["AppointmentNeedId", "ApptNeedId", "AppointmentNeedID"],
        )
        tp_number_col = self._pick_column("ChartHealingActions", ["TPNumber", "TPNum", "TPNo"])
        tp_item_col = self._pick_column("ChartHealingActions", ["TPItem", "TPItemNo"])
        code_col = self._pick_column("ChartHealingActions", ["CodeID", "CodeId"])
        date_col = self._pick_column(
            "ChartHealingActions",
            ["ActionDate", "Date", "CreatedDate", "ActionedDate", "ActionedOn"],
        )
        type_col = self._pick_column("ChartHealingActions", ["ActionType", "Type", "Action"])
        tooth_col = self._pick_column("ChartHealingActions", ["Tooth"])
        surface_col = self._pick_column("ChartHealingActions", ["Surface"])
        status_col = self._pick_column("ChartHealingActions", ["Status", "StatusCode"])
        notes_col = self._pick_column("ChartHealingActions", ["Notes", "Note", "Description"])
        user_col = self._pick_column("ChartHealingActions", ["UserCode", "UserId", "RecordedBy"])
        last_id: int | None = None
        remaining = limit
        batch_size = 500
        while True:
            if remaining is not None:
                if remaining <= 0:
                    break
                batch_size = min(batch_size, remaining)
            where_parts: list[str] = []
            params: list[Any] = []
            if patient_col:
                range_clause, range_params = self._build_range_filter(
                    patient_col,
                    patients_from,
                    patients_to,
                )
                if range_clause:
                    where_parts.append(range_clause.replace("WHERE", "").strip())
                    params.extend(range_params)
            if last_id is not None:
                where_parts.append(f"{id_col} > ?")
                params.append(last_id)
            where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
            select_cols = [f"{id_col} AS action_id"]
            if patient_col:
                select_cols.append(f"{patient_col} AS patient_code")
            if appt_need_col:
                select_cols.append(f"{appt_need_col} AS appointment_need_id")
            if tp_number_col:
                select_cols.append(f"{tp_number_col} AS tp_number")
            if tp_item_col:
                select_cols.append(f"{tp_item_col} AS tp_item")
            if code_col:
                select_cols.append(f"{code_col} AS code_id")
            if date_col:
                select_cols.append(f"{date_col} AS action_date")
            if type_col:
                select_cols.append(f"{type_col} AS action_type")
            if tooth_col:
                select_cols.append(f"{tooth_col} AS tooth")
            if surface_col:
                select_cols.append(f"{surface_col} AS surface")
            if status_col:
                select_cols.append(f"{status_col} AS status")
            if notes_col:
                select_cols.append(f"{notes_col} AS notes")
            if user_col:
                select_cols.append(f"{user_col} AS user_code")
            rows = self._query(
                f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.ChartHealingActions WITH (NOLOCK) "
                f"{where_sql} ORDER BY {id_col} ASC",
                [batch_size, *params],
            )
            if not rows:
                break
            for row in rows:
                action_id = row.get("action_id")
                if action_id is None:
                    continue
                last_id = int(action_id)
                yield R4ChartHealingAction(
                    action_id=last_id,
                    patient_code=int(row["patient_code"]) if row.get("patient_code") is not None else None,
                    appointment_need_id=(
                        int(row["appointment_need_id"])
                        if row.get("appointment_need_id") is not None
                        else None
                    ),
                    tp_number=int(row["tp_number"]) if row.get("tp_number") is not None else None,
                    tp_item=int(row["tp_item"]) if row.get("tp_item") is not None else None,
                    code_id=int(row["code_id"]) if row.get("code_id") is not None else None,
                    action_date=row.get("action_date"),
                    action_type=(row.get("action_type") or "").strip() or None,
                    tooth=int(row["tooth"]) if row.get("tooth") is not None else None,
                    surface=int(row["surface"]) if row.get("surface") is not None else None,
                    status=(row.get("status") or "").strip() or None,
                    notes=(row.get("notes") or "").strip() or None,
                    user_code=int(row["user_code"]) if row.get("user_code") is not None else None,
                )
                if remaining is not None:
                    remaining -= 1

    def list_bpe_entries(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4BPEEntry]:
        patient_col = self._pick_column("BPE", ["PatientCode"])
        bpe_id_col = self._pick_column("BPE", ["BPEID", "BPEId", "ID"])
        date_col = self._pick_column("BPE", ["Date", "BPEDate", "RecordedDate", "EntryDate"])
        notes_col = self._pick_column("BPE", ["Notes", "Note", "Description"])
        user_col = self._pick_column("BPE", ["UserCode", "EnteredBy"])
        sextant_cols = [
            self._pick_column("BPE", [f"Sextant{i}", f"Sextant{i}Score"]) for i in range(1, 7)
        ]
        if not patient_col and not bpe_id_col:
            raise RuntimeError("BPE missing PatientCode/BPEID columns; cannot keyset stream.")
        if not date_col and not bpe_id_col:
            raise RuntimeError("BPE missing date column; cannot keyset stream without BPEID.")
        last_id: int | None = None
        last_patient: int | None = None
        last_date: datetime | None = None
        remaining = limit
        batch_size = 500
        while True:
            if remaining is not None:
                if remaining <= 0:
                    break
                batch_size = min(batch_size, remaining)
            where_parts: list[str] = []
            params: list[Any] = []
            if patient_col:
                range_clause, range_params = self._build_range_filter(
                    patient_col,
                    patients_from,
                    patients_to,
                )
                if range_clause:
                    where_parts.append(range_clause.replace("WHERE", "").strip())
                    params.extend(range_params)
            if bpe_id_col and last_id is not None:
                where_parts.append(f"{bpe_id_col} > ?")
                params.append(last_id)
            elif patient_col and date_col and last_patient is not None and last_date is not None:
                where_parts.append(
                    f"({patient_col} > ? OR ({patient_col} = ? AND {date_col} > ?))"
                )
                params.extend([last_patient, last_patient, last_date])
            where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
            select_cols = []
            if bpe_id_col:
                select_cols.append(f"{bpe_id_col} AS bpe_id")
            if patient_col:
                select_cols.append(f"{patient_col} AS patient_code")
            if date_col:
                select_cols.append(f"{date_col} AS recorded_at")
            if notes_col:
                select_cols.append(f"{notes_col} AS notes")
            if user_col:
                select_cols.append(f"{user_col} AS user_code")
            for idx, col in enumerate(sextant_cols, start=1):
                if col:
                    select_cols.append(f"{col} AS sextant_{idx}")
            rows = self._query(
                f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.BPE WITH (NOLOCK) "
                f"{where_sql} ORDER BY {bpe_id_col or patient_col} ASC",
                [batch_size, *params],
            )
            if not rows:
                break
            for row in rows:
                bpe_id = row.get("bpe_id")
                patient_code = row.get("patient_code")
                recorded_at = row.get("recorded_at")
                if bpe_id_col and bpe_id is not None:
                    last_id = int(bpe_id)
                elif patient_code is not None and recorded_at is not None:
                    last_patient = int(patient_code)
                    last_date = recorded_at
                yield R4BPEEntry(
                    bpe_id=int(bpe_id) if bpe_id is not None else None,
                    patient_code=int(patient_code) if patient_code is not None else None,
                    recorded_at=recorded_at,
                    sextant_1=int(row["sextant_1"]) if row.get("sextant_1") is not None else None,
                    sextant_2=int(row["sextant_2"]) if row.get("sextant_2") is not None else None,
                    sextant_3=int(row["sextant_3"]) if row.get("sextant_3") is not None else None,
                    sextant_4=int(row["sextant_4"]) if row.get("sextant_4") is not None else None,
                    sextant_5=int(row["sextant_5"]) if row.get("sextant_5") is not None else None,
                    sextant_6=int(row["sextant_6"]) if row.get("sextant_6") is not None else None,
                    notes=(row.get("notes") or "").strip() or None,
                    user_code=int(row["user_code"]) if row.get("user_code") is not None else None,
                )
                if remaining is not None:
                    remaining -= 1

    def list_bpe_furcations(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4BPEFurcation]:
        id_col = self._pick_column("BPEFurcation", ["pKey", "ID", "BPEFurcationID"])
        patient_col = self._pick_column("BPEFurcation", ["PatientCode"])
        bpe_id_col = self._pick_column("BPEFurcation", ["BPEID", "BPEId"])
        tooth_col = self._pick_column("BPEFurcation", ["Tooth"])
        furcation_col = self._pick_column("BPEFurcation", ["Furcation", "FurcationScore"])
        sextant_col = self._pick_column("BPEFurcation", ["Sextant", "SextantScore"])
        date_col = self._pick_column("BPEFurcation", ["Date", "RecordedDate", "EntryDate"])
        notes_col = self._pick_column("BPEFurcation", ["Notes", "Note", "Description"])
        user_col = self._pick_column("BPEFurcation", ["UserCode", "EnteredBy"])
        bpe_patient_col = None
        bpe_id_join_col = None
        join_sql = ""
        patient_expr = None
        if not patient_col and bpe_id_col:
            bpe_patient_col = self._pick_column("BPE", ["PatientCode"])
            bpe_id_join_col = self._pick_column("BPE", ["BPEID", "BPEId", "ID", "RefId", "RefID"])
            if bpe_patient_col and bpe_id_join_col:
                join_sql = (
                    "JOIN ("
                    f"SELECT {bpe_id_join_col} AS bpe_id, MIN({bpe_patient_col}) AS patient_code "
                    "FROM dbo.BPE WITH (NOLOCK) "
                    f"WHERE {bpe_patient_col} IS NOT NULL "
                    f"GROUP BY {bpe_id_join_col} HAVING COUNT(DISTINCT {bpe_patient_col}) = 1"
                    ") b ON b.bpe_id = bf."
                    + bpe_id_col
                )
                patient_expr = "b.patient_code"
        if not id_col and not bpe_id_col:
            raise RuntimeError("BPEFurcation missing key columns; cannot keyset stream.")
        if not id_col and (not tooth_col or not furcation_col):
            raise RuntimeError("BPEFurcation missing tooth/furcation columns for keyset.")
        last_id: int | None = None
        last_bpe: int | None = None
        last_tooth: int | None = None
        last_furcation: int | None = None
        remaining = limit
        batch_size = 500
        while True:
            if remaining is not None:
                if remaining <= 0:
                    break
                batch_size = min(batch_size, remaining)
            where_parts: list[str] = []
            params: list[Any] = []
            if patient_col:
                patient_expr = f"bf.{patient_col}"
            if patient_expr:
                range_clause, range_params = self._build_range_filter(
                    patient_expr,
                    patients_from,
                    patients_to,
                )
                if range_clause:
                    where_parts.append(range_clause.replace("WHERE", "").strip())
                    params.extend(range_params)
            if id_col and last_id is not None:
                where_parts.append(f"{id_col} > ?")
                params.append(last_id)
            elif bpe_id_col and last_bpe is not None:
                where_parts.append(
                    f"({bpe_id_col} > ? OR ({bpe_id_col} = ? AND "
                    f"({tooth_col} > ? OR ({tooth_col} = ? AND {furcation_col} > ?))))"
                )
                params.extend(
                    [last_bpe, last_bpe, last_tooth or 0, last_tooth or 0, last_furcation or 0]
                )
            where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
            select_cols = []
            if id_col:
                select_cols.append(f"bf.{id_col} AS furcation_id")
            if patient_expr:
                select_cols.append(f"{patient_expr} AS patient_code")
            if bpe_id_col:
                select_cols.append(f"bf.{bpe_id_col} AS bpe_id")
            if tooth_col:
                select_cols.append(f"bf.{tooth_col} AS tooth")
            if furcation_col:
                select_cols.append(f"bf.{furcation_col} AS furcation")
            if sextant_col:
                select_cols.append(f"bf.{sextant_col} AS sextant")
            if date_col:
                select_cols.append(f"bf.{date_col} AS recorded_at")
            if notes_col:
                select_cols.append(f"bf.{notes_col} AS notes")
            if user_col:
                select_cols.append(f"bf.{user_col} AS user_code")
            rows = self._query(
                f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.BPEFurcation bf WITH (NOLOCK) "
                f"{join_sql} {where_sql} ORDER BY bf.{id_col or bpe_id_col} ASC",
                [batch_size, *params],
            )
            if not rows:
                break
            for row in rows:
                furcation_id = row.get("furcation_id")
                bpe_id = row.get("bpe_id")
                tooth = row.get("tooth")
                furcation = row.get("furcation")
                if id_col and furcation_id is not None:
                    last_id = int(furcation_id)
                elif bpe_id is not None and tooth is not None and furcation is not None:
                    last_bpe = int(bpe_id)
                    last_tooth = int(tooth)
                    last_furcation = int(furcation)
                yield R4BPEFurcation(
                    furcation_id=int(furcation_id) if furcation_id is not None else None,
                    bpe_id=int(bpe_id) if bpe_id is not None else None,
                    patient_code=int(row["patient_code"]) if row.get("patient_code") is not None else None,
                    tooth=int(tooth) if tooth is not None else None,
                    furcation=int(furcation) if furcation is not None else None,
                    sextant=int(row["sextant"]) if row.get("sextant") is not None else None,
                    recorded_at=row.get("recorded_at"),
                    notes=(row.get("notes") or "").strip() or None,
                    user_code=int(row["user_code"]) if row.get("user_code") is not None else None,
                )
                if remaining is not None:
                    remaining -= 1

    def list_perio_probes(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4PerioProbe]:
        trans_col = self._require_column("PerioProbe", ["TransId", "TransID"])
        tooth_col = self._require_column("PerioProbe", ["Tooth"])
        point_col = self._require_column("PerioProbe", ["ProbingPoint", "Point"])
        patient_col = self._pick_column("PerioProbe", ["PatientCode"])
        depth_col = self._pick_column("PerioProbe", ["Depth", "ProbeDepth"])
        bleed_col = self._pick_column("PerioProbe", ["Bleeding", "BleedingScore"])
        plaque_col = self._pick_column("PerioProbe", ["Plaque", "PlaqueScore"])
        date_col = self._pick_column("PerioProbe", ["Date", "RecordedDate", "ProbeDate"])
        join_sql = ""
        patient_expr = None
        if patient_col:
            patient_expr = f"pp.{patient_col}"
        else:
            trans_ref_col = self._pick_column("Transactions", ["RefId"])
            trans_patient_col = self._pick_column("Transactions", ["PatientCode"])
            if trans_ref_col and trans_patient_col:
                join_sql = (
                    "JOIN ("
                    f"SELECT {trans_ref_col} AS ref_id, MIN({trans_patient_col}) AS patient_code "
                    "FROM dbo.Transactions WITH (NOLOCK) "
                    f"WHERE {trans_patient_col} IS NOT NULL "
                    f"GROUP BY {trans_ref_col} HAVING COUNT(DISTINCT {trans_patient_col}) = 1"
                    ") t ON t.ref_id = pp."
                    + trans_col
                )
                patient_expr = "t.patient_code"
        last_trans: int | None = None
        last_tooth: int | None = None
        last_point: int | None = None
        remaining = limit
        batch_size = 500
        while True:
            if remaining is not None:
                if remaining <= 0:
                    break
                batch_size = min(batch_size, remaining)
            where_parts: list[str] = []
            params: list[Any] = []
            if patient_expr:
                range_clause, range_params = self._build_range_filter(
                    patient_expr,
                    patients_from,
                    patients_to,
                )
                if range_clause:
                    where_parts.append(range_clause.replace("WHERE", "").strip())
                    params.extend(range_params)
            if last_trans is not None and last_tooth is not None and last_point is not None:
                where_parts.append(
                    f"({trans_col} > ? OR ({trans_col} = ? AND ({tooth_col} > ? OR "
                    f"({tooth_col} = ? AND {point_col} > ?))))"
                )
                params.extend([last_trans, last_trans, last_tooth, last_tooth, last_point])
            where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
            select_cols = [
                f"pp.{trans_col} AS trans_id",
                f"pp.{tooth_col} AS tooth",
                f"pp.{point_col} AS probing_point",
            ]
            if patient_expr:
                select_cols.append(f"{patient_expr} AS patient_code")
            if depth_col:
                select_cols.append(f"pp.{depth_col} AS depth")
            if bleed_col:
                select_cols.append(f"pp.{bleed_col} AS bleeding")
            if plaque_col:
                select_cols.append(f"pp.{plaque_col} AS plaque")
            if date_col:
                select_cols.append(f"pp.{date_col} AS recorded_at")
            rows = self._query(
                f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.PerioProbe pp WITH (NOLOCK) "
                f"{join_sql} {where_sql} ORDER BY pp.{trans_col} ASC, pp.{tooth_col} ASC, pp.{point_col} ASC",
                [batch_size, *params],
            )
            if not rows:
                break
            for row in rows:
                trans_id = row.get("trans_id")
                tooth = row.get("tooth")
                point = row.get("probing_point")
                if trans_id is None or tooth is None or point is None:
                    continue
                last_trans = int(trans_id)
                last_tooth = int(tooth)
                last_point = int(point)
                yield R4PerioProbe(
                    trans_id=last_trans,
                    patient_code=int(row["patient_code"]) if row.get("patient_code") is not None else None,
                    tooth=last_tooth,
                    probing_point=last_point,
                    depth=int(row["depth"]) if row.get("depth") is not None else None,
                    bleeding=int(row["bleeding"]) if row.get("bleeding") is not None else None,
                    plaque=int(row["plaque"]) if row.get("plaque") is not None else None,
                    recorded_at=row.get("recorded_at"),
                )
                if remaining is not None:
                    remaining -= 1

    def list_perio_plaque(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4PerioPlaque]:
        trans_col = self._require_column("PerioPlaque", ["TransId", "TransID"])
        tooth_col = self._require_column("PerioPlaque", ["Tooth"])
        patient_col = self._pick_column("PerioPlaque", ["PatientCode"])
        plaque_col = self._pick_column("PerioPlaque", ["Plaque", "PlaqueScore"])
        bleed_col = self._pick_column("PerioPlaque", ["Bleeding", "BleedingScore"])
        date_col = self._pick_column("PerioPlaque", ["Date", "RecordedDate"])
        join_sql = ""
        patient_expr = None
        if patient_col:
            patient_expr = f"pp.{patient_col}"
        else:
            trans_ref_col = self._pick_column("Transactions", ["RefId"])
            trans_patient_col = self._pick_column("Transactions", ["PatientCode"])
            if trans_ref_col and trans_patient_col:
                join_sql = (
                    "JOIN ("
                    f"SELECT {trans_ref_col} AS ref_id, MIN({trans_patient_col}) AS patient_code "
                    "FROM dbo.Transactions WITH (NOLOCK) "
                    f"WHERE {trans_patient_col} IS NOT NULL "
                    f"GROUP BY {trans_ref_col} HAVING COUNT(DISTINCT {trans_patient_col}) = 1"
                    ") t ON t.ref_id = pp."
                    + trans_col
                )
                patient_expr = "t.patient_code"
        last_trans: int | None = None
        last_tooth: int | None = None
        remaining = limit
        batch_size = 500
        while True:
            if remaining is not None:
                if remaining <= 0:
                    break
                batch_size = min(batch_size, remaining)
            where_parts: list[str] = []
            params: list[Any] = []
            if patient_expr:
                range_clause, range_params = self._build_range_filter(
                    patient_expr,
                    patients_from,
                    patients_to,
                )
                if range_clause:
                    where_parts.append(range_clause.replace("WHERE", "").strip())
                    params.extend(range_params)
            if last_trans is not None and last_tooth is not None:
                where_parts.append(
                    f"({trans_col} > ? OR ({trans_col} = ? AND {tooth_col} > ?))"
                )
                params.extend([last_trans, last_trans, last_tooth])
            where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
            select_cols = [f"pp.{trans_col} AS trans_id", f"pp.{tooth_col} AS tooth"]
            if patient_expr:
                select_cols.append(f"{patient_expr} AS patient_code")
            if plaque_col:
                select_cols.append(f"pp.{plaque_col} AS plaque")
            if bleed_col:
                select_cols.append(f"pp.{bleed_col} AS bleeding")
            if date_col:
                select_cols.append(f"pp.{date_col} AS recorded_at")
            rows = self._query(
                f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.PerioPlaque pp WITH (NOLOCK) "
                f"{join_sql} {where_sql} ORDER BY pp.{trans_col} ASC, pp.{tooth_col} ASC",
                [batch_size, *params],
            )
            if not rows:
                break
            for row in rows:
                trans_id = row.get("trans_id")
                tooth = row.get("tooth")
                if trans_id is None or tooth is None:
                    continue
                last_trans = int(trans_id)
                last_tooth = int(tooth)
                yield R4PerioPlaque(
                    trans_id=last_trans,
                    patient_code=int(row["patient_code"]) if row.get("patient_code") is not None else None,
                    tooth=last_tooth,
                    plaque=int(row["plaque"]) if row.get("plaque") is not None else None,
                    bleeding=int(row["bleeding"]) if row.get("bleeding") is not None else None,
                    recorded_at=row.get("recorded_at"),
                )
                if remaining is not None:
                    remaining -= 1

    def list_patient_notes(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4PatientNote]:
        patient_col = self._require_column("PatientNotes", ["PatientCode"])
        note_no_col = self._pick_column("PatientNotes", ["NoteNumber", "NoteNo"])
        if not note_no_col:
            raise RuntimeError("PatientNotes missing NoteNumber column.")
        date_col = self._pick_column("PatientNotes", ["Date", "NoteDate", "CreatedDate"])
        note_col = self._pick_column("PatientNotes", ["Note", "Notes", "NoteText", "NoteBody"])
        tooth_col = self._pick_column("PatientNotes", ["Tooth"])
        surface_col = self._pick_column("PatientNotes", ["Surface"])
        category_col = self._pick_column("PatientNotes", ["CategoryNumber", "CategoryNo"])
        fixed_note_col = self._pick_column("PatientNotes", ["FixedNoteCode", "FixedNote"])
        user_col = self._pick_column("PatientNotes", ["UserCode", "EnteredBy"])
        last_patient: int | None = None
        last_note: int | None = None
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
                patient_col,
                patients_from,
                patients_to,
            )
            if range_clause:
                where_parts.append(range_clause.replace("WHERE", "").strip())
                params.extend(range_params)
            if last_patient is not None and last_note is not None:
                where_parts.append(
                    f"({patient_col} > ? OR ({patient_col} = ? AND {note_no_col} > ?))"
                )
                params.extend([last_patient, last_patient, last_note])
            where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
            select_cols = [f"{patient_col} AS patient_code", f"{note_no_col} AS note_number"]
            if date_col:
                select_cols.append(f"{date_col} AS note_date")
            if note_col:
                select_cols.append(f"{note_col} AS note")
            if tooth_col:
                select_cols.append(f"{tooth_col} AS tooth")
            if surface_col:
                select_cols.append(f"{surface_col} AS surface")
            if category_col:
                select_cols.append(f"{category_col} AS category_number")
            if fixed_note_col:
                select_cols.append(f"{fixed_note_col} AS fixed_note_code")
            if user_col:
                select_cols.append(f"{user_col} AS user_code")
            rows = self._query(
                f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.PatientNotes WITH (NOLOCK) "
                f"{where_sql} ORDER BY {patient_col} ASC, {note_no_col} ASC",
                [batch_size, *params],
            )
            if not rows:
                break
            for row in rows:
                patient_code = row.get("patient_code")
                note_number = row.get("note_number")
                if patient_code is None or note_number is None:
                    continue
                last_patient = int(patient_code)
                last_note = int(note_number)
                yield R4PatientNote(
                    patient_code=last_patient,
                    note_number=last_note,
                    note_date=row.get("note_date"),
                    note=(row.get("note") or "").strip() or None,
                    tooth=int(row["tooth"]) if row.get("tooth") is not None else None,
                    surface=int(row["surface"]) if row.get("surface") is not None else None,
                    category_number=int(row["category_number"])
                    if row.get("category_number") is not None
                    else None,
                    fixed_note_code=int(row["fixed_note_code"])
                    if row.get("fixed_note_code") is not None
                    else None,
                    user_code=int(row["user_code"]) if row.get("user_code") is not None else None,
                )
                if remaining is not None:
                    remaining -= 1

    def list_fixed_notes(self, limit: int | None = None) -> Iterable[R4FixedNote]:
        code_col = self._require_column("FixedNotes", ["FixedNoteCode"])
        category_col = self._pick_column("FixedNotes", ["CategoryNumber", "CategoryNo"])
        desc_col = self._pick_column("FixedNotes", ["Description", "NoteDesc"])
        note_col = self._pick_column("FixedNotes", ["Note", "Notes", "NoteText"])
        tooth_col = self._pick_column("FixedNotes", ["Tooth"])
        surface_col = self._pick_column("FixedNotes", ["Surface"])
        last_code: int | None = None
        remaining = limit
        batch_size = 500
        while True:
            if remaining is not None:
                if remaining <= 0:
                    break
                batch_size = min(batch_size, remaining)
            where_clause = ""
            params: list[Any] = []
            if last_code is not None:
                where_clause = f"WHERE {code_col} > ?"
                params.append(last_code)
            select_cols = [f"{code_col} AS fixed_note_code"]
            if category_col:
                select_cols.append(f"{category_col} AS category_number")
            if desc_col:
                select_cols.append(f"{desc_col} AS description")
            if note_col:
                select_cols.append(f"{note_col} AS note")
            if tooth_col:
                select_cols.append(f"{tooth_col} AS tooth")
            if surface_col:
                select_cols.append(f"{surface_col} AS surface")
            rows = self._query(
                f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.FixedNotes WITH (NOLOCK) "
                f"{where_clause} ORDER BY {code_col}",
                [batch_size, *params],
            )
            if not rows:
                break
            for row in rows:
                code = row.get("fixed_note_code")
                if code is None:
                    continue
                last_code = int(code)
                yield R4FixedNote(
                    fixed_note_code=last_code,
                    category_number=int(row["category_number"])
                    if row.get("category_number") is not None
                    else None,
                    description=(row.get("description") or "").strip() or None,
                    note=(row.get("note") or "").strip() or None,
                    tooth=int(row["tooth"]) if row.get("tooth") is not None else None,
                    surface=int(row["surface"]) if row.get("surface") is not None else None,
                )
                if remaining is not None:
                    remaining -= 1

    def list_note_categories(self, limit: int | None = None) -> Iterable[R4NoteCategory]:
        code_col = self._require_column("NoteCategories", ["CategoryNumber", "CategoryNo"])
        desc_col = self._pick_column("NoteCategories", ["Description", "Name"])
        last_code: int | None = None
        remaining = limit
        batch_size = 500
        while True:
            if remaining is not None:
                if remaining <= 0:
                    break
                batch_size = min(batch_size, remaining)
            where_clause = ""
            params: list[Any] = []
            if last_code is not None:
                where_clause = f"WHERE {code_col} > ?"
                params.append(last_code)
            select_cols = [f"{code_col} AS category_number"]
            if desc_col:
                select_cols.append(f"{desc_col} AS description")
            rows = self._query(
                f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.NoteCategories WITH (NOLOCK) "
                f"{where_clause} ORDER BY {code_col}",
                [batch_size, *params],
            )
            if not rows:
                break
            for row in rows:
                code = row.get("category_number")
                if code is None:
                    continue
                last_code = int(code)
                yield R4NoteCategory(
                    category_number=last_code,
                    description=(row.get("description") or "").strip() or None,
                )
                if remaining is not None:
                    remaining -= 1

    def list_treatment_notes(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4TreatmentNote]:
        note_id_col = self._require_column("TreatmentNotes", ["NoteID", "NoteId"])
        patient_col = self._pick_column("TreatmentNotes", ["PatientCode"])
        tp_col = self._pick_column("TreatmentNotes", ["TPNumber", "TPNum", "TPNo"])
        tp_item_col = self._pick_column("TreatmentNotes", ["TPItem", "TPItemNo"])
        date_col = self._pick_column("TreatmentNotes", ["Date", "NoteDate", "CreatedDate"])
        note_col = self._pick_column("TreatmentNotes", ["Note", "Notes", "NoteText", "NoteBody"])
        user_col = self._pick_column("TreatmentNotes", ["UserCode", "EnteredBy"])
        last_id: int | None = None
        remaining = limit
        batch_size = 500
        while True:
            if remaining is not None:
                if remaining <= 0:
                    break
                batch_size = min(batch_size, remaining)
            where_parts: list[str] = []
            params: list[Any] = []
            if patient_col:
                range_clause, range_params = self._build_range_filter(
                    patient_col,
                    patients_from,
                    patients_to,
                )
                if range_clause:
                    where_parts.append(range_clause.replace("WHERE", "").strip())
                    params.extend(range_params)
            if last_id is not None:
                where_parts.append(f"{note_id_col} > ?")
                params.append(last_id)
            where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
            select_cols = [f"{note_id_col} AS note_id"]
            if patient_col:
                select_cols.append(f"{patient_col} AS patient_code")
            if tp_col:
                select_cols.append(f"{tp_col} AS tp_number")
            if tp_item_col:
                select_cols.append(f"{tp_item_col} AS tp_item")
            if date_col:
                select_cols.append(f"{date_col} AS note_date")
            if note_col:
                select_cols.append(f"{note_col} AS note")
            if user_col:
                select_cols.append(f"{user_col} AS user_code")
            rows = self._query(
                f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.TreatmentNotes WITH (NOLOCK) "
                f"{where_sql} ORDER BY {note_id_col} ASC",
                [batch_size, *params],
            )
            if not rows:
                break
            for row in rows:
                note_id = row.get("note_id")
                if note_id is None:
                    continue
                last_id = int(note_id)
                yield R4TreatmentNote(
                    note_id=last_id,
                    patient_code=int(row["patient_code"]) if row.get("patient_code") is not None else None,
                    tp_number=int(row["tp_number"]) if row.get("tp_number") is not None else None,
                    tp_item=int(row["tp_item"]) if row.get("tp_item") is not None else None,
                    note_date=row.get("note_date"),
                    note=(row.get("note") or "").strip() or None,
                    user_code=int(row["user_code"]) if row.get("user_code") is not None else None,
                )
                if remaining is not None:
                    remaining -= 1

    def list_temporary_notes(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4TemporaryNote]:
        patient_col = self._require_column("TemporaryNotes", ["PatientCode"])
        note_col = self._pick_column("TemporaryNotes", ["Note", "Notes", "NoteText"])
        date_col = self._pick_column("TemporaryNotes", ["UpdatedAt", "LastEditDate", "Date"])
        user_col = self._pick_column("TemporaryNotes", ["UserCode", "EnteredBy"])
        last_patient: int | None = None
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
                patient_col,
                patients_from,
                patients_to,
            )
            if range_clause:
                where_parts.append(range_clause.replace("WHERE", "").strip())
                params.extend(range_params)
            if last_patient is not None:
                where_parts.append(f"{patient_col} > ?")
                params.append(last_patient)
            where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
            select_cols = [f"{patient_col} AS patient_code"]
            if note_col:
                select_cols.append(f"{note_col} AS note")
            if date_col:
                select_cols.append(f"{date_col} AS legacy_updated_at")
            if user_col:
                select_cols.append(f"{user_col} AS user_code")
            rows = self._query(
                f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.TemporaryNotes WITH (NOLOCK) "
                f"{where_sql} ORDER BY {patient_col} ASC",
                [batch_size, *params],
            )
            if not rows:
                break
            for row in rows:
                patient_code = row.get("patient_code")
                if patient_code is None:
                    continue
                last_patient = int(patient_code)
                yield R4TemporaryNote(
                    patient_code=last_patient,
                    note=(row.get("note") or "").strip() or None,
                    legacy_updated_at=row.get("legacy_updated_at"),
                    user_code=int(row["user_code"]) if row.get("user_code") is not None else None,
                )
                if remaining is not None:
                    remaining -= 1

    def list_old_patient_notes(
        self,
        patients_from: int | None = None,
        patients_to: int | None = None,
        limit: int | None = None,
    ) -> Iterable[R4OldPatientNote]:
        patient_col = self._require_column("OldPatientNotes", ["PatientCode"])
        note_no_col = self._pick_column("OldPatientNotes", ["NoteNumber", "NoteNo"])
        if not note_no_col:
            raise RuntimeError("OldPatientNotes missing NoteNumber column.")
        date_col = self._pick_column("OldPatientNotes", ["Date", "NoteDate", "CreatedDate"])
        note_col = self._pick_column("OldPatientNotes", ["Note", "Notes", "NoteText", "NoteBody"])
        tooth_col = self._pick_column("OldPatientNotes", ["Tooth"])
        surface_col = self._pick_column("OldPatientNotes", ["Surface"])
        category_col = self._pick_column("OldPatientNotes", ["CategoryNumber", "CategoryNo"])
        fixed_note_col = self._pick_column("OldPatientNotes", ["FixedNoteCode", "FixedNote"])
        user_col = self._pick_column("OldPatientNotes", ["UserCode", "EnteredBy"])
        last_patient: int | None = None
        last_note: int | None = None
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
                patient_col,
                patients_from,
                patients_to,
            )
            if range_clause:
                where_parts.append(range_clause.replace("WHERE", "").strip())
                params.extend(range_params)
            if last_patient is not None and last_note is not None:
                where_parts.append(
                    f"({patient_col} > ? OR ({patient_col} = ? AND {note_no_col} > ?))"
                )
                params.extend([last_patient, last_patient, last_note])
            where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
            select_cols = [f"{patient_col} AS patient_code", f"{note_no_col} AS note_number"]
            if date_col:
                select_cols.append(f"{date_col} AS note_date")
            if note_col:
                select_cols.append(f"{note_col} AS note")
            if tooth_col:
                select_cols.append(f"{tooth_col} AS tooth")
            if surface_col:
                select_cols.append(f"{surface_col} AS surface")
            if category_col:
                select_cols.append(f"{category_col} AS category_number")
            if fixed_note_col:
                select_cols.append(f"{fixed_note_col} AS fixed_note_code")
            if user_col:
                select_cols.append(f"{user_col} AS user_code")
            rows = self._query(
                f"SELECT TOP (?) {', '.join(select_cols)} FROM dbo.OldPatientNotes WITH (NOLOCK) "
                f"{where_sql} ORDER BY {patient_col} ASC, {note_no_col} ASC",
                [batch_size, *params],
            )
            if not rows:
                break
            for row in rows:
                patient_code = row.get("patient_code")
                note_number = row.get("note_number")
                if patient_code is None or note_number is None:
                    continue
                last_patient = int(patient_code)
                last_note = int(note_number)
                yield R4OldPatientNote(
                    patient_code=last_patient,
                    note_number=last_note,
                    note_date=row.get("note_date"),
                    note=(row.get("note") or "").strip() or None,
                    tooth=int(row["tooth"]) if row.get("tooth") is not None else None,
                    surface=int(row["surface"]) if row.get("surface") is not None else None,
                    category_number=int(row["category_number"])
                    if row.get("category_number") is not None
                    else None,
                    fixed_note_code=int(row["fixed_note_code"])
                    if row.get("fixed_note_code") is not None
                    else None,
                    user_code=int(row["user_code"]) if row.get("user_code") is not None else None,
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

    def _count_table(
        self,
        table: str,
        where_clause: str = "",
        params: list[Any] | None = None,
    ) -> int:
        rows = self._query(
            f"SELECT COUNT(1) AS count FROM dbo.{table} WITH (NOLOCK){where_clause}",
            params or [],
        )
        if not rows:
            return 0
        return int(rows[0].get("count") or 0)

    def _date_range(
        self,
        table: str,
        date_col: str,
        where_clause: str = "",
        params: list[Any] | None = None,
    ) -> dict[str, str] | None:
        rows = self._query(
            f"SELECT MIN({date_col}) AS min_date, MAX({date_col}) AS max_date "
            f"FROM dbo.{table} WITH (NOLOCK){where_clause}",
            params or [],
        )
        if not rows:
            return None
        min_date = self._format_dt(rows[0].get("min_date"))
        max_date = self._format_dt(rows[0].get("max_date"))
        if not min_date and not max_date:
            return None
        return {"min": min_date, "max": max_date}

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

    @staticmethod
    def _format_money(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return float(value)
        return float(value)
