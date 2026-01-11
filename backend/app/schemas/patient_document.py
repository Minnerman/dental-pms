from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PatientDocumentCreate(BaseModel):
    template_id: int
    title: Optional[str] = None


class PatientDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    template_id: Optional[int] = None
    title: str
    rendered_content: str
    created_at: datetime
    unknown_fields: list[str] | None = None


class PatientDocumentPreview(BaseModel):
    title: str
    rendered_content: str
    unknown_fields: list[str]
