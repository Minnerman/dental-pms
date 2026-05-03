from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

__all__ = [
    "DEFAULT_R4_APPOINTMENT_TIMEZONE",
    "R4AppointmentDateTimeConversion",
    "R4AppointmentDateTimePolicyError",
    "map_r4_appointment_datetime",
]


DEFAULT_R4_APPOINTMENT_TIMEZONE = "Europe/London"


class R4AppointmentDateTimePolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class R4AppointmentDateTimeConversion:
    source_local_naive: datetime
    local_datetime: datetime
    utc_datetime: datetime
    timezone_name: str
    input_was_timezone_aware: bool


def map_r4_appointment_datetime(
    value: datetime | date | None,
    *,
    field_name: str = "appointment datetime",
    timezone_name: str = DEFAULT_R4_APPOINTMENT_TIMEZONE,
) -> R4AppointmentDateTimeConversion:
    """Interpret R4 appointment wall time as Europe/London and store UTC-aware.

    R4 appointment source values have no offset in `vwAppointmentDetails`, so
    naive datetimes are clinic-local wall times. Ambiguous or non-existent local
    DST values fail closed until an operator can confirm the intended instant.
    """

    if value is None:
        raise R4AppointmentDateTimePolicyError(f"{field_name} is required.")
    if isinstance(value, datetime):
        return _map_datetime(
            value,
            field_name=field_name,
            timezone_name=timezone_name,
        )
    if isinstance(value, date):
        raise R4AppointmentDateTimePolicyError(
            f"{field_name} must include a time component."
        )
    raise R4AppointmentDateTimePolicyError(
        f"{field_name} must be a datetime value."
    )


def _map_datetime(
    value: datetime,
    *,
    field_name: str,
    timezone_name: str,
) -> R4AppointmentDateTimeConversion:
    local_tz = ZoneInfo(timezone_name)
    if _is_timezone_aware(value):
        utc_value = value.astimezone(timezone.utc)
        local_value = utc_value.astimezone(local_tz)
        return R4AppointmentDateTimeConversion(
            source_local_naive=local_value.replace(tzinfo=None),
            local_datetime=local_value,
            utc_datetime=utc_value,
            timezone_name=timezone_name,
            input_was_timezone_aware=True,
        )

    local_value = _resolve_naive_local(value, local_tz, field_name=field_name)
    return R4AppointmentDateTimeConversion(
        source_local_naive=value,
        local_datetime=local_value,
        utc_datetime=local_value.astimezone(timezone.utc),
        timezone_name=timezone_name,
        input_was_timezone_aware=False,
    )


def _resolve_naive_local(
    value: datetime,
    local_tz: ZoneInfo,
    *,
    field_name: str,
) -> datetime:
    valid_candidates: list[datetime] = []
    for fold in (0, 1):
        candidate = value.replace(tzinfo=local_tz, fold=fold)
        roundtrip = candidate.astimezone(timezone.utc).astimezone(local_tz)
        if roundtrip.replace(tzinfo=None) == value:
            valid_candidates.append(candidate)

    unique_utc_values = {
        candidate.astimezone(timezone.utc) for candidate in valid_candidates
    }
    if not valid_candidates:
        raise R4AppointmentDateTimePolicyError(
            f"{field_name} is not a valid {DEFAULT_R4_APPOINTMENT_TIMEZONE} "
            "local time."
        )
    if len(unique_utc_values) > 1:
        raise R4AppointmentDateTimePolicyError(
            f"{field_name} is ambiguous in {DEFAULT_R4_APPOINTMENT_TIMEZONE}."
        )
    return valid_candidates[0]


def _is_timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None
