from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PatientRecallCommunicationChannel(str, enum.Enum):
    letter = "letter"
    phone = "phone"
    email = "email"
    sms = "sms"
    other = "other"


class PatientRecallCommunicationDirection(str, enum.Enum):
    outbound = "outbound"


class PatientRecallCommunicationStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    failed = "failed"


class PatientRecallCommunication(Base):
    __tablename__ = "patient_recall_communications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id"), nullable=False, index=True
    )
    recall_id: Mapped[int] = mapped_column(
        ForeignKey("patient_recalls.id"), nullable=False, index=True
    )
    channel: Mapped[PatientRecallCommunicationChannel] = mapped_column(
        Enum(
            PatientRecallCommunicationChannel, name="patient_recall_comm_channel"
        ),
        nullable=False,
    )
    direction: Mapped[PatientRecallCommunicationDirection] = mapped_column(
        Enum(
            PatientRecallCommunicationDirection, name="patient_recall_comm_direction"
        ),
        nullable=False,
        default=PatientRecallCommunicationDirection.outbound,
    )
    status: Mapped[PatientRecallCommunicationStatus] = mapped_column(
        Enum(PatientRecallCommunicationStatus, name="patient_recall_comm_status"),
        nullable=False,
        default=PatientRecallCommunicationStatus.sent,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    other_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    contacted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    recall = relationship("PatientRecall", back_populates="communications", lazy="joined")
