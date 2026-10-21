"""Schemas for seat inventory and status."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class SeatResponse(BaseModel):
    """Public representation of an individual seat."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_id: uuid.UUID
    section: str = Field(..., max_length=50)
    row: str = Field(..., max_length=10)
    number: int
    price_cents: int
    status: str = Field(..., description="'available', 'held', or 'booked'")


class SeatListResponse(BaseModel):
    """List of all seats and their availability status for an event."""

    event_id: uuid.UUID
    total: int
    available_count: int
    seats: list[SeatResponse]
