"""Hold and HoldSeat models for temporary seat reservation."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.seat import Seat


class Hold(Base):
    """Temporary seat hold reserving inventory for checkout."""

    __tablename__ = "holds"
    __table_args__ = (
        Index("ix_holds_user_status", "user_id", "status"),
        Index("ix_holds_expires_status", "expires_at", "status"),
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
    status: Mapped[str] = mapped_column(
        String(32),
        default="active",
        nullable=False,
    )  # active, expired, released, converted
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
