"""SQLAlchemy models for booking hold sweeper reconciliation."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Seat(Base):
    """Seat model in booking schema."""

    __tablename__ = "seats"
    __table_args__ = ({"schema": "booking"},)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    tier: Mapped[str] = mapped_column(String(64), nullable=False)
    section: Mapped[str] = mapped_column(String(64), nullable=False)
    row: Mapped[str] = mapped_column(String(32), nullable=False)
    seat_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="available", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class Hold(Base):
    """Temporary seat hold reserving inventory."""

    __tablename__ = "holds"
    __table_args__ = ({"schema": "booking"},)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="active",
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    seats: Mapped[list[Seat]] = relationship(
        "Seat",
        secondary="booking.hold_seats",
        lazy="selectin",
    )


class HoldSeat(Base):
    """Junction table associating held seats with a Hold."""

    __tablename__ = "hold_seats"
    __table_args__ = ({"schema": "booking"},)

    hold_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("booking.holds.id", ondelete="CASCADE"),
        primary_key=True,
    )
    seat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("booking.seats.id", ondelete="CASCADE"),
        primary_key=True,
    )
