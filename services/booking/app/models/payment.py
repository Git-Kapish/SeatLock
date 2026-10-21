"""Payment record model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Payment(Base):
    """Payment record linked to a booking."""

    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_booking_id", "booking_id"),
        {"schema": "booking"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("booking.bookings.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_ref: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="initiated",
        nullable=False,
    )  # initiated, succeeded, failed, refunded
    amount_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
