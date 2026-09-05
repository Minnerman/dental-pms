from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.models.patient import PatientCategory

DirectoryStatus = Literal["active", "archived", "all"]
DirectorySort = Literal["last_name", "first_name", "joined", "recently_edited", "last_visit"]
DirectoryDirection = Literal["asc", "desc"]


class DirectoryPatient(BaseModel):
    id: int
    first_name: str
    last_name: str
    phone: str | None
    date_of_birth: date | None
    patient_category: PatientCategory
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    balance_pence: int | None
    last_visit_at: datetime | None


class DirectoryMetadata(BaseModel):
    finance: Literal["available", "forbidden"]
    last_visit: Literal["available", "forbidden"]
    do_not_contact: Literal["unavailable"] = "unavailable"


class PatientDirectory(BaseModel):
    items: list[DirectoryPatient]
    total: int
    limit: int
    offset: int
    metadata: DirectoryMetadata
    definitions: dict[str, str]
