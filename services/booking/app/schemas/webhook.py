"""Schemas for incoming payment provider webhook payloads."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PaymentWebhookPayload(BaseModel):
    """Payload delivered by mock or third-party payment provider webhook."""

    event_id: str = Field(..., description="Unique event identifier from payment provider")
    event_type: str = Field(..., description="'payment.succeeded' or 'payment.failed'")
    data: dict[str, Any] = Field(
        ..., description="Event payload containing booking_id and provider_ref"
    )
    created_at: str | None = None
