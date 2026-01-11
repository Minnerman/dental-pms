from typing import Optional

from pydantic import BaseModel, ConfigDict


class PracticeProfileBase(BaseModel):
    name: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    postcode: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None


class PracticeProfileUpdate(PracticeProfileBase):
    pass


class PracticeProfileOut(PracticeProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
