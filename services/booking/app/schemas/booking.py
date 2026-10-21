"""Schemas for bookings and ticket purchase workflows."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.seat import SeatResponse


class CreateBookingRequest(BaseModel):
    """Request to convert an active hold into a pending booking."""

    hold_id: uuid.UUID = Field(..., description="ID of the active seat hold to convert")


class BookingResponse(BaseModel):
    """Representation of a ticket booking."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    event_id: uuid.UUID
    hold_id: uuid.UUID | None
    status: str = Field(..., description="'pending_payment', 'confirmed', 'cancelled', 'failed'")
    total_cents: int
    created_at: datetime
    seats: list[SeatResponse] = Field(default_factory=list)
    payment_intent_id: str | None = None
    client_secret: str | None = None


class BookingListResponse(BaseModel):
    """Paginated list of bookings for a user."""

    total: int
    items: list[BookingResponse]
