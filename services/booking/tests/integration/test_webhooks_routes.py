"""Integration tests for Payment Webhook API routes."""

import hmac
import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import httpx
import pytest

from app.config import config
from app.models.booking import Booking
from app.models.seat import Seat


def compute_test_signature(body: bytes) -> str:
    return hmac.new(config.payment_webhook_secret.encode(), body, "sha256").hexdigest()


@pytest.mark.asyncio
async def test_webhook_missing_signature_rejected(
    app_client: httpx.AsyncClient,
) -> None:
    payload = {"event_id": "evt-1", "event_type": "payment.succeeded", "data": {}}
    response = await app_client.post("/api/v1/booking/payments/webhook", json=payload)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INVALID_SIGNATURE"


@pytest.mark.asyncio
async def test_webhook_invalid_signature_rejected(
    app_client: httpx.AsyncClient,
) -> None:
    payload = {"event_id": "evt-1", "event_type": "payment.succeeded", "data": {}}
    response = await app_client.post(
        "/api/v1/booking/payments/webhook",
        json=payload,
        headers={"X-Signature-256": "fake-invalid-signature"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INVALID_SIGNATURE"


@pytest.mark.asyncio
async def test_webhook_valid_signature_processes_success(
    app_client: httpx.AsyncClient,
    mock_payment_repo: AsyncMock,
    mock_booking_repo: AsyncMock,
    mock_sqs_client: AsyncMock,
) -> None:
    mock_payment_repo.is_webhook_processed.return_value = False

    event_id = uuid.uuid4()
    booking_id = uuid.uuid4()
    seat = Seat(
        id=uuid.uuid4(),
        event_id=event_id,
        section="Floor",
        row="1",
        number=1,
        price_cents=6000,
        status="held",
    )
    booking = Booking(
        id=booking_id,
        user_id=uuid.uuid4(),
        event_id=event_id,
        status="pending_payment",
        total_cents=6000,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    booking.seats = [seat]
    mock_booking_repo.get_booking_by_id.return_value = booking

    payload = {
        "event_id": "evt_hook_001",
        "event_type": "payment.succeeded",
        "data": {"booking_id": str(booking_id)},
    }
    raw_body = json.dumps(payload).encode()
    signature = compute_test_signature(raw_body)

    response = await app_client.post(
        "/api/v1/booking/payments/webhook",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Signature-256": signature},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["booking_status"] == "confirmed"
    assert booking.status == "confirmed"
    assert seat.status == "booked"
    mock_sqs_client.publish_event.assert_called_once()
    mock_payment_repo.mark_webhook_processed.assert_called_once_with("evt_hook_001")


@pytest.mark.asyncio
async def test_webhook_duplicate_event_id_ignored(
    app_client: httpx.AsyncClient,
    mock_payment_repo: AsyncMock,
    mock_booking_repo: AsyncMock,
) -> None:
    # Event ID already processed
    mock_payment_repo.is_webhook_processed.return_value = True

    payload = {
        "event_id": "evt_hook_duplicate",
        "event_type": "payment.succeeded",
        "data": {"booking_id": str(uuid.uuid4())},
    }
    raw_body = json.dumps(payload).encode()
    signature = compute_test_signature(raw_body)

    response = await app_client.post(
        "/api/v1/booking/payments/webhook",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Signature-256": signature},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "already_processed"
    # Booking repository should not have been queried
    mock_booking_repo.get_booking_by_id.assert_not_called()
