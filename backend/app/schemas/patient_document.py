from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.actor import ActorOut


class PrescriptionDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    medicine: str = Field(min_length=1, max_length=500)
    directions: str = Field(min_length=1, max_length=2000)
    quantity: str = Field(min_length=1, max_length=120)
    prescriber_name: str = Field(min_length=1, max_length=200)
    prescriber_gdc: str = Field(min_length=1, max_length=50)

    @field_validator("medicine", "directions", "quantity", "prescriber_name", "prescriber_gdc", mode="before")
    @classmethod
    def normalize_details(cls, value):
        if not isinstance(value, str):
            raise ValueError("Enter prescription details as text")
        value = value.strip()
        if any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ValueError("Prescription details contain unsupported control characters")
        return value


class PatientDocumentCreate(BaseModel):
    template_id: int = Field(gt=0)
    title: Optional[str] = Field(default=None, max_length=200)
    prescription: PrescriptionDetails | None = None

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
