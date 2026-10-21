"""Seat model representing an individual bookable seat."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Seat(Base):
    """Represents a physical or allocated seat for an event."""

    __tablename__ = "seats"
    __table_args__ = (
        UniqueConstraint(
            "event_id", "section", "row", "number", name="uq_seats_event_section_row_number"
        ),
        Index("ix_seats_event_status", "event_id", "status"),
        Index("ix_seats_event_id", "event_id"),
        {"schema": "booking"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    section: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    row: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )
    number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    price_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="available",
        nullable=False,
    )  # available, held, booked
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
