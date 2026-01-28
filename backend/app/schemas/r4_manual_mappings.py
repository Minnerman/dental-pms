from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class R4ManualMappingCreate(BaseModel):
    legacy_patient_code: int = Field(..., ge=1)
    target_patient_id: int
    note: str | None = None


class R4ManualMappingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    legacy_source: str
    legacy_patient_code: int
    target_patient_id: int
    note: str | None = None
    created_at: datetime
