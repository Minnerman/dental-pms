from datetime import datetime

from pydantic import ConfigDict, Field, field_validator

from app.schemas.patient_document import PrescriptionMedication


class PrescriptionTemplateWrite(PrescriptionMedication):
    name: str = Field(min_length=1, max_length=200)
    is_active: bool = True

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        return cls.normalize_details(value)


class PrescriptionTemplateOut(PrescriptionTemplateWrite):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
