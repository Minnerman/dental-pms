from datetime import date, time
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PracticeHourBase(BaseModel):
    day_of_week: int
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_closed: bool = False


class PracticeHourIn(PracticeHourBase):
    pass


class PracticeHourOut(PracticeHourBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class PracticeClosureBase(BaseModel):
    start_date: date
    end_date: date
    reason: Optional[str] = None


class PracticeClosureIn(PracticeClosureBase):
    pass


class PracticeClosureOut(PracticeClosureBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class PracticeOverrideBase(BaseModel):
    date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_closed: bool = False
    reason: Optional[str] = None


class PracticeOverrideIn(PracticeOverrideBase):
    pass


class PracticeOverrideOut(PracticeOverrideBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class PracticeScheduleOut(BaseModel):
    hours: list[PracticeHourOut]
    closures: list[PracticeClosureOut]
    overrides: list[PracticeOverrideOut]


class PracticeScheduleUpdate(BaseModel):
    hours: list[PracticeHourIn]
    closures: list[PracticeClosureIn]
    overrides: list[PracticeOverrideIn]
