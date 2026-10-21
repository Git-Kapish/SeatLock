"""Repository for Payment records and processed webhook tracking."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.models.webhook import ProcessedWebhook


class PaymentRepository:
    """Manages payment intents and webhook event deduplication."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_payment(self, payment: Payment) -> Payment:
        """Persists a new payment intent record."""
        self.session.add(payment)
        await self.session.flush()
        return payment

    async def get_payment_by_booking_id(self, booking_id: uuid.UUID) -> Payment | None:
        """Finds the payment record associated with a booking."""
        stmt = select(Payment).where(Payment.booking_id == booking_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def is_webhook_processed(self, provider_event_id: str) -> bool:
        """Checks if a webhook event ID has already been processed."""
        stmt = select(ProcessedWebhook).where(
            ProcessedWebhook.provider_event_id == provider_event_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def mark_webhook_processed(self, provider_event_id: str) -> None:
        """Marks a webhook event ID as processed."""
        record = ProcessedWebhook(
            provider_event_id=provider_event_id, processed_at=datetime.now(UTC)
        )
        self.session.add(record)
        await self.session.flush()
