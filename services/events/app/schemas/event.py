"""Pydantic schemas for event catalog requests and responses."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EventStatusType = Literal[
    "draft",
    "published",
    "on_sale",
    "sold_out",
    "completed",
    "cancelled",
]


class CreateEventRequest(BaseModel):
    """Payload for creating a new live event."""

    title: str = Field(..., min_length=3, max_length=255, description="Event title")
    description: str = Field(..., min_length=10, description="Detailed event description")
    venue: str = Field(..., min_length=2, max_length=255, description="Venue name")
    city: str = Field(..., min_length=2, max_length=100, description="City location")
    category: str = Field(
        ..., min_length=2, max_length=50, description="Category, e.g. Concert, Sports"
    )
    starts_at: datetime = Field(..., description="UTC start datetime")
    status: EventStatusType = Field(default="draft", description="Initial lifecycle status")


class UpdateEventRequest(BaseModel):
    """Payload for updating an existing live event."""

    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, min_length=10)
    venue: str | None = Field(default=None, min_length=2, max_length=255)
    city: str | None = Field(default=None, min_length=2, max_length=100)
    category: str | None = Field(default=None, min_length=2, max_length=50)
    starts_at: datetime | None = Field(default=None)
    status: EventStatusType | None = Field(default=None)


class EventFilterParams(BaseModel):
    """Query filters for event catalog search and browsing."""

    city: str | None = None
    category: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: str | None = "on_sale"
    q: str | None = None


class EventResponse(BaseModel):
    """Public event details response model."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str
    venue: str
    city: str
    category: str
    starts_at: datetime
    status: str
    created_at: datetime
    updated_at: datetime
