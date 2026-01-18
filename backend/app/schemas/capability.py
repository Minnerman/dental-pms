from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CapabilityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    description: str
    created_at: datetime


class UserCapabilitiesUpdate(BaseModel):
    capability_codes: list[str]
