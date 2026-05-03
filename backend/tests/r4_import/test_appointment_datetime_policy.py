from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.services.r4_import.appointment_datetime_policy import (
    DEFAULT_R4_APPOINTMENT_TIMEZONE,
    R4AppointmentDateTimePolicyError,
    map_r4_appointment_datetime,
)


def test_maps_normal_winter_local_time_to_utc_aware_datetime():
    result = map_r4_appointment_datetime(datetime(2026, 1, 15, 9, 0))

    assert result.timezone_name == DEFAULT_R4_APPOINTMENT_TIMEZONE
    assert result.source_local_naive == datetime(2026, 1, 15, 9, 0)
    assert result.local_datetime.isoformat() == "2026-01-15T09:00:00+00:00"
    assert result.utc_datetime == datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)
    assert result.input_was_timezone_aware is False


def test_maps_normal_summer_local_time_to_utc_aware_datetime():
    result = map_r4_appointment_datetime(datetime(2026, 7, 15, 9, 0))

    assert result.source_local_naive == datetime(2026, 7, 15, 9, 0)
    assert result.local_datetime.isoformat() == "2026-07-15T09:00:00+01:00"
    assert result.utc_datetime == datetime(2026, 7, 15, 8, 0, tzinfo=timezone.utc)


def test_spring_forward_boundary_maps_valid_times_around_gap():
    before_gap = map_r4_appointment_datetime(datetime(2026, 3, 29, 0, 30))
    after_gap = map_r4_appointment_datetime(datetime(2026, 3, 29, 2, 30))

    assert before_gap.local_datetime.isoformat() == "2026-03-29T00:30:00+00:00"
    assert before_gap.utc_datetime == datetime(2026, 3, 29, 0, 30, tzinfo=timezone.utc)
    assert after_gap.local_datetime.isoformat() == "2026-03-29T02:30:00+01:00"
    assert after_gap.utc_datetime == datetime(2026, 3, 29, 1, 30, tzinfo=timezone.utc)


def test_spring_forward_nonexistent_local_time_fails_closed():
    with pytest.raises(R4AppointmentDateTimePolicyError, match="not a valid"):
        map_r4_appointment_datetime(datetime(2026, 3, 29, 1, 30))


def test_fall_back_boundary_maps_valid_times_around_repeated_hour():
    before_repeated_hour = map_r4_appointment_datetime(datetime(2026, 10, 25, 0, 30))
    after_repeated_hour = map_r4_appointment_datetime(datetime(2026, 10, 25, 2, 30))

    assert before_repeated_hour.local_datetime.isoformat() == (
        "2026-10-25T00:30:00+01:00"
    )
    assert before_repeated_hour.utc_datetime == datetime(
        2026, 10, 24, 23, 30, tzinfo=timezone.utc
    )
    assert after_repeated_hour.local_datetime.isoformat() == (
        "2026-10-25T02:30:00+00:00"
    )
    assert after_repeated_hour.utc_datetime == datetime(
        2026, 10, 25, 2, 30, tzinfo=timezone.utc
    )


def test_fall_back_ambiguous_local_time_fails_closed():
    with pytest.raises(R4AppointmentDateTimePolicyError, match="ambiguous"):
        map_r4_appointment_datetime(datetime(2026, 10, 25, 1, 30))


def test_future_appointment_local_time_is_preserved_as_wall_time():
    result = map_r4_appointment_datetime(datetime(2027, 2, 1, 9, 0))

    assert result.source_local_naive == datetime(2027, 2, 1, 9, 0)
    assert result.local_datetime.isoformat() == "2027-02-01T09:00:00+00:00"
    assert result.utc_datetime == datetime(2027, 2, 1, 9, 0, tzinfo=timezone.utc)


def test_historic_appointment_local_time_is_preserved_as_wall_time():
    result = map_r4_appointment_datetime(datetime(2001, 10, 27, 11, 15))

    assert result.source_local_naive == datetime(2001, 10, 27, 11, 15)
    assert result.local_datetime.isoformat() == "2001-10-27T11:15:00+01:00"
    assert result.utc_datetime == datetime(2001, 10, 27, 10, 15, tzinfo=timezone.utc)


def test_timezone_aware_input_is_normalized_to_utc_and_london_local_view():
    result = map_r4_appointment_datetime(
        datetime(2026, 7, 15, 8, 0, tzinfo=timezone.utc)
    )

    assert result.input_was_timezone_aware is True
    assert result.source_local_naive == datetime(2026, 7, 15, 9, 0)
    assert result.local_datetime.isoformat() == "2026-07-15T09:00:00+01:00"
    assert result.utc_datetime == datetime(2026, 7, 15, 8, 0, tzinfo=timezone.utc)


def test_missing_datetime_fails_closed():
    with pytest.raises(R4AppointmentDateTimePolicyError, match="is required"):
        map_r4_appointment_datetime(None)


def test_date_only_value_fails_closed():
    with pytest.raises(R4AppointmentDateTimePolicyError, match="time component"):
        map_r4_appointment_datetime(date(2026, 1, 15))


def test_non_datetime_value_fails_closed():
    with pytest.raises(R4AppointmentDateTimePolicyError, match="datetime value"):
        map_r4_appointment_datetime("2026-01-15 09:00")  # type: ignore[arg-type]
