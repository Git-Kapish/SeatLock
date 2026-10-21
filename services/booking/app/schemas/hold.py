"""Schemas for temporary seat holds."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateHoldRequest(BaseModel):
    """Request to hold one or more seats for an event."""

    event_id: uuid.UUID = Field(..., description="Target event ID")
    seat_ids: list[uuid.UUID] = Field(
        ...,
        min_length=1,
        max_length=6,
        description="List of seat IDs to hold (max 6 per request)",
    )


class HoldResponse(BaseModel):
    """Response returned upon successful seat hold acquisition."""

    id: uuid.UUID
    user_id: uuid.UUID
    event_id: uuid.UUID
    status: str
    expires_at: datetime
    created_at: datetime
    seat_ids: list[uuid.UUID]
    total_price_cents: int
