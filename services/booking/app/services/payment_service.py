"""Payment integration service and webhook processor."""

from __future__ import annotations

import hmac
import uuid
from datetime import UTC, datetime
from typing import Any

from redis.asyncio.client import Redis

from app.config import config
from app.models.payment import Payment
from app.repositories.booking_repository import BookingRepository
from app.repositories.hold_repository import HoldRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.seat_repository import SeatRepository
from app.schemas.webhook import PaymentWebhookPayload
from ticketrush_common.errors import ForbiddenError, NotFoundError
from ticketrush_common.sqs import SQSClient


class PaymentService:
    """Manages payment intents, HMAC webhook verification, and state transitions."""

    def __init__(
        self,
        payment_repo: PaymentRepository,
        booking_repo: BookingRepository,
        hold_repo: HoldRepository,
        seat_repo: SeatRepository,
        redis_client: Redis,
        sqs_client: SQSClient | None = None,
    ) -> None:
        self.payment_repo = payment_repo
        self.booking_repo = booking_repo
        self.hold_repo = hold_repo
        self.seat_repo = seat_repo
        self.redis_client = redis_client
        self.sqs_client = sqs_client or SQSClient(
            region_name=config.aws_region,
            endpoint_url=config.sqs_endpoint_url,
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key,
        )

    async def create_payment_intent(
        self,
        booking_id: uuid.UUID,
        amount_cents: int,
    ) -> tuple[str, str]:
        """Creates a mock payment intent returning provider_ref and client_secret."""
        provider_ref = f"pi_test_{uuid.uuid4().hex[:16]}"
        client_secret = f"cs_test_{uuid.uuid4().hex[:24]}"

        payment = Payment(
            id=uuid.uuid4(),
            booking_id=booking_id,
            provider_ref=provider_ref,
            status="initiated",
            amount_cents=amount_cents,
            created_at=datetime.now(UTC),
        )
        await self.payment_repo.create_payment(payment)
        return provider_ref, client_secret

    def verify_webhook_signature(
        self,
        raw_body: bytes,
        signature_header: str | None,
    ) -> None:
        """Verifies the HMAC-SHA256 signature on the raw incoming webhook request."""
        if not signature_header:
            raise ForbiddenError(
                message="Missing webhook signature header",
                code="INVALID_SIGNATURE",
            )

        expected_sig = hmac.new(
            config.payment_webhook_secret.encode("utf-8"),
            raw_body,
            "sha256",
        ).hexdigest()

        if not hmac.compare_digest(signature_header, expected_sig):
            raise ForbiddenError(
                message="Webhook HMAC signature verification failed",
                code="INVALID_SIGNATURE",
            )

    async def process_webhook(self, payload: PaymentWebhookPayload) -> dict[str, Any]:
        """Deduplicates and processes incoming payment webhook events."""
        # 1. Deduplication via processed_webhooks table
        if await self.payment_repo.is_webhook_processed(payload.event_id):
            return {
                "status": "already_processed",
                "event_id": payload.event_id,
            }

        booking_id_str = payload.data.get("booking_id")
        if not booking_id_str:
            raise NotFoundError(
                message="Missing booking_id in webhook payload data",
                code="INVALID_WEBHOOK_PAYLOAD",
            )

        booking_id = uuid.UUID(booking_id_str)
        booking = await self.booking_repo.get_booking_by_id(booking_id)
        if not booking:
            raise NotFoundError(
                message=f"Booking {booking_id} not found",
                code="BOOKING_NOT_FOUND",
            )

        # 2. State transition based on payment event
        if payload.event_type == "payment.succeeded":
            if booking.status != "confirmed":
                booking.status = "confirmed"
                booking.updated_at = datetime.now(UTC)

                # Confirm seats
                for s in booking.seats:
                    s.status = "booked"
                    s.version = (s.version or 1) + 1

                # Convert hold
                if booking.hold_id:
                    hold = await self.hold_repo.get_hold_by_id(booking.hold_id)
                    if hold:
                        hold.status = "converted"

                # Update payment record
                payment = await self.payment_repo.get_payment_by_booking_id(booking.id)
                if payment:
                    payment.status = "succeeded"

                # Release Redis hold keys (seats are now permanently booked in Postgres)
                for s in booking.seats:
                    key = f"hold:{booking.event_id}:{s.id}"
                    await self.redis_client.delete(key)

                # Publish event to SQS queue for async notification
                sqs_payload = {
                    "booking_id": str(booking.id),
                    "user_id": str(booking.user_id),
                    "event_id": str(booking.event_id),
                    "total_cents": booking.total_cents,
                    "seat_ids": [str(s.id) for s in booking.seats],
                    "occurred_at": datetime.now(UTC).isoformat(),
                }
                await self.sqs_client.publish_event(
                    queue_url=config.sqs_queue_url,
                    event_type="booking.confirmed",
                    payload=sqs_payload,
                )

        elif payload.event_type == "payment.failed" and booking.status != "failed":
            booking.status = "failed"
            booking.updated_at = datetime.now(UTC)

            # Return seats to available
            for s in booking.seats:
                s.status = "available"
                s.version = (s.version or 1) + 1

            # Release Redis hold keys
            for s in booking.seats:
                key = f"hold:{booking.event_id}:{s.id}"
                await self.redis_client.delete(key)

            payment = await self.payment_repo.get_payment_by_booking_id(booking.id)
            if payment:
                payment.status = "failed"

        # 3. Mark webhook as processed
        await self.payment_repo.mark_webhook_processed(payload.event_id)

        return {
            "status": "processed",
            "event_id": payload.event_id,
            "booking_id": str(booking.id),
            "booking_status": booking.status,
        }
