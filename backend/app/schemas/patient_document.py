from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.actor import ActorOut


class PatientDocumentCreate(BaseModel):
    template_id: int = Field(gt=0)
    title: Optional[str] = Field(default=None, max_length=200)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Document title must not be blank")
        return normalized


class PatientDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    template_id: Optional[int] = None
    attachment_id: Optional[int] = None
    title: str
    rendered_content: str
    created_at: datetime
    created_by: ActorOut
    unknown_fields: list[str] | None = None


class PatientDocumentPreview(BaseModel):
    title: str
    rendered_content: str
    unknown_fields: list[str]
