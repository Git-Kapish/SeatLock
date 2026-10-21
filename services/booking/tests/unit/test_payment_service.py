"""Unit tests for PaymentService."""

import hmac
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.config import config
from app.models.booking import Booking
from app.models.payment import Payment
from app.models.seat import Seat
from app.schemas.webhook import PaymentWebhookPayload
from app.services.payment_service import PaymentService
from ticketrush_common.errors import ForbiddenError


@pytest.mark.asyncio
async def test_create_payment_intent() -> None:
    payment_repo = AsyncMock()
    booking_repo = AsyncMock()
    hold_repo = AsyncMock()
    seat_repo = AsyncMock()
    redis_client = AsyncMock()
    sqs_client = AsyncMock()

    service = PaymentService(
        payment_repo=payment_repo,
        booking_repo=booking_repo,
        hold_repo=hold_repo,
        seat_repo=seat_repo,
        redis_client=redis_client,
        sqs_client=sqs_client,
    )

    booking_id = uuid.uuid4()
    provider_ref, client_secret = await service.create_payment_intent(booking_id, 10000)

    assert provider_ref.startswith("pi_test_")
    assert client_secret.startswith("cs_test_")
    payment_repo.create_payment.assert_called_once()
    created_payment = payment_repo.create_payment.call_args[0][0]
    assert created_payment.booking_id == booking_id
    assert created_payment.amount_cents == 10000
    assert created_payment.status == "initiated"


def test_verify_webhook_signature_valid() -> None:
    service = PaymentService(
        payment_repo=AsyncMock(),
        booking_repo=AsyncMock(),
        hold_repo=AsyncMock(),
        seat_repo=AsyncMock(),
        redis_client=AsyncMock(),
        sqs_client=AsyncMock(),
    )

    raw_body = b'{"event_id": "evt-123"}'
    valid_sig = hmac.new(config.payment_webhook_secret.encode(), raw_body, "sha256").hexdigest()

    # Should not raise
    service.verify_webhook_signature(raw_body, valid_sig)


def test_verify_webhook_signature_invalid_raises() -> None:
    service = PaymentService(
        payment_repo=AsyncMock(),
        booking_repo=AsyncMock(),
        hold_repo=AsyncMock(),
        seat_repo=AsyncMock(),
        redis_client=AsyncMock(),
        sqs_client=AsyncMock(),
    )

    raw_body = b'{"event_id": "evt-123"}'
    with pytest.raises(ForbiddenError):
        service.verify_webhook_signature(raw_body, "tampered-signature-value")


@pytest.mark.asyncio
async def test_process_webhook_payment_succeeded() -> None:
    payment_repo = AsyncMock()
    booking_repo = AsyncMock()
    hold_repo = AsyncMock()
    seat_repo = AsyncMock()
    redis_client = AsyncMock()
    sqs_client = AsyncMock()

    payment_repo.is_webhook_processed.return_value = False

    event_id = uuid.uuid4()
    booking_id = uuid.uuid4()
    seat = Seat(
        id=uuid.uuid4(),
        event_id=event_id,
        section="A",
        row="1",
        number=1,
        price_cents=5000,
        status="held",
        version=1,
    )
    booking = Booking(
        id=booking_id,
        user_id=uuid.uuid4(),
        event_id=event_id,
        status="pending_payment",
        total_cents=5000,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    booking.seats = [seat]
    booking_repo.get_booking_by_id.return_value = booking

    payment = Payment(
        id=uuid.uuid4(),
        booking_id=booking_id,
        amount_cents=5000,
        status="initiated",
        created_at=datetime.now(UTC),
    )
    payment_repo.get_payment_by_booking_id.return_value = payment

    service = PaymentService(
        payment_repo=payment_repo,
        booking_repo=booking_repo,
        hold_repo=hold_repo,
        seat_repo=seat_repo,
        redis_client=redis_client,
        sqs_client=sqs_client,
    )

    payload = PaymentWebhookPayload(
        event_id="evt_test_101",
        event_type="payment.succeeded",
        data={"booking_id": str(booking_id)},
    )

    res = await service.process_webhook(payload)

    assert res["status"] == "processed"
    assert res["booking_status"] == "confirmed"
    assert booking.status == "confirmed"
    assert seat.status == "booked"
    assert seat.version == 2
    assert payment.status == "succeeded"

    # Verify Redis key deleted
    redis_client.delete.assert_called_once_with(f"hold:{event_id}:{seat.id}")
    # Verify SQS message published
    sqs_client.publish_event.assert_called_once()
    # Verify webhook marked processed
    payment_repo.mark_webhook_processed.assert_called_once_with("evt_test_101")
