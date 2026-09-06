from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

JournalCategory = Literal["notes", "diagnosis", "treatment", "medical", "correspondence"]
JournalFilter = Literal["all", "notes", "diagnosis", "treatment", "medical", "correspondence"]
Availability = Literal["available", "forbidden", "disabled"]


class JournalAuthor(BaseModel):
    name: str | None = None
    user_id: int | None = None
    source_user_code: str | None = None


class JournalProvenance(BaseModel):
    system: str
    source_table: str
    source_key: str
    source_patient_code: str | None = None
    source_author_code: str | None = None
    source_recorded_at: datetime | None = None
    source_entered_at: datetime | None = None
    imported_at: datetime | None = None
    content_hash: str | None = None


class JournalItem(BaseModel):
    key: str
    source_kind: str
    source_id: str
    category: JournalCategory
    title: str
    body: str | None = None
    occurred_at: datetime | None = None
    clinical_date: date | None = None
    date_basis: Literal["clinical_date", "source", "recorded", "unknown"] = "unknown"
    author: JournalAuthor = Field(default_factory=JournalAuthor)
    tooth: str | None = None
    surface: str | None = None
    revision: int | None = None
    can_edit: bool = False
    history_url: str | None = None
    link: str | None = None
    provenance: JournalProvenance | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class JournalAvailability(BaseModel):
    notes: Availability
    clinical: Availability
    medical: Availability
    correspondence: Availability
    documents: Availability
    recalls: Availability
    imported: Availability


class ClinicalJournalOut(BaseModel):
    patient_id: int
    items: list[JournalItem]
    next_cursor: str | None = None
    availability: JournalAvailability
    coverage_notes: list[str] = Field(default_factory=list)
