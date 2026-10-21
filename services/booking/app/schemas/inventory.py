"""Schemas for event seat inventory generation."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class SectionConfig(BaseModel):
    """Configuration for a seating section."""

    name: str = Field(
        ..., min_length=1, max_length=50, description="Section name, e.g. 'VIP', 'Floor', 'Balcony'"
    )
    rows: int = Field(..., ge=1, le=100, description="Number of rows in this section")
    seats_per_row: int = Field(..., ge=1, le=100, description="Number of seats per row")
    price_cents: int = Field(..., ge=0, description="Price in cents for each seat in this section")


class CreateInventoryRequest(BaseModel):
    """Admin request to generate seating inventory for an event."""

    sections: list[SectionConfig] = Field(
        ..., min_length=1, description="List of section configurations"
    )


class CreateInventoryResponse(BaseModel):
    """Response returned upon successful inventory generation."""

    event_id: uuid.UUID
    total_seats_created: int
    sections: list[str]
