from datetime import date, time
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LocalSession(BaseModel):
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_closed: bool = False

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def require_clock_time(cls, value):
        if value is not None and not isinstance(value, (str, time)):
            raise ValueError("Session times must be local clock times")
        return value

    @field_validator("start_time", "end_time")
    @classmethod
    def require_local_time(cls, value):
        if value is not None and value.tzinfo is not None:
            raise ValueError("Session times must not include a timezone")
        return value


class PracticeHourBase(LocalSession):
    day_of_week: int = Field(ge=0, le=6, strict=True)


class PracticeHourIn(PracticeHourBase):
    model_config = ConfigDict(extra="forbid")
    # Older clients round-trip GET rows, including IDs. IDs are accepted but
    # ignored by the replace-all writer, exactly as before.
    id: int | None = None


class PracticeHourOut(PracticeHourBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class PracticeClosureBase(BaseModel):
    start_date: date
    end_date: date
    reason: Optional[str] = Field(default=None, max_length=255)


class PracticeClosureIn(PracticeClosureBase):
    model_config = ConfigDict(extra="forbid")
    id: int | None = None


class PracticeClosureOut(PracticeClosureBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class PracticeOverrideBase(LocalSession):
    date: date
    reason: Optional[str] = Field(default=None, max_length=255)


class PracticeOverrideIn(PracticeOverrideBase):
    model_config = ConfigDict(extra="forbid")
    id: int | None = None


class PracticeOverrideOut(PracticeOverrideBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class PracticeScheduleOut(BaseModel):
    hours: list[PracticeHourOut]
    closures: list[PracticeClosureOut]
    overrides: list[PracticeOverrideOut]


class PracticeScheduleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hours: list[PracticeHourIn] = Field(min_length=1)
    closures: list[PracticeClosureIn]
    overrides: list[PracticeOverrideIn]
