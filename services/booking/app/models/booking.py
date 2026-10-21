"""Booking and BookingSeat models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.seat import Seat


class Booking(Base):
    """Booking entity capturing confirmed and pending ticket purchases."""

    __tablename__ = "bookings"
    __table_args__ = (
        Index("ix_bookings_user_id", "user_id"),
        Index("ix_bookings_event_id", "event_id"),
        {"schema": "booking"},
    )

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
    hold_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("booking.holds.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="pending_payment",
        nullable=False,
    )  # pending_payment, confirmed, cancelled, failed
    total_cents: Mapped[int] = mapped_column(
        Integer,
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

    seats: Mapped[list[Seat]] = relationship(
        "Seat",
        secondary="booking.booking_seats",
        lazy="selectin",
    )


class BookingSeat(Base):
    """Junction table connecting booked seats to a booking with conflict protection."""

    __tablename__ = "booking_seats"
    __table_args__ = (
        Index(
            "ix_booking_seats_active",
            "seat_id",
            unique=True,
            postgresql_where=text("status IN ('pending_payment', 'confirmed')"),
        ),
        {"schema": "booking"},
    )

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("booking.bookings.id", ondelete="CASCADE"),
        primary_key=True,
    )
    seat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("booking.seats.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="pending_payment",
        nullable=False,
    )
