"""Integration tests for Bookings API routes and Idempotency."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest

from app.models.booking import Booking
from app.models.hold import Hold
from app.models.idempotency import IdempotencyKey
from app.models.seat import Seat


@pytest.mark.asyncio
async def test_create_booking_success(
    app_client: httpx.AsyncClient,
    mock_hold_repo: AsyncMock,
    mock_booking_repo: AsyncMock,
    mock_payment_repo: AsyncMock,
    mock_idempotency_repo: AsyncMock,
    user_auth_headers: dict[str, str],
    test_user_id: uuid.UUID,
) -> None:
    event_id = uuid.uuid4()
    hold_id = uuid.uuid4()
    seat = Seat(
        id=uuid.uuid4(),
        event_id=event_id,
        section="Floor",
        row="1",
        number=1,
        price_cents=7500,
        status="held",
    )
    hold = Hold(
        id=hold_id,
        user_id=test_user_id,
        event_id=event_id,
        status="active",
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        created_at=datetime.now(UTC),
    )
    hold.seats = [seat]
    mock_hold_repo.get_active_hold_by_id.return_value = hold
    mock_idempotency_repo.get_key.return_value = None

    payload = {"hold_id": str(hold_id)}
    response = await app_client.post(
        "/api/v1/booking/bookings",
        json=payload,
        headers={**user_auth_headers, "Idempotency-Key": "idem-key-101"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == str(test_user_id)
    assert data["status"] == "pending_payment"
    assert data["total_cents"] == 7500
    assert data["payment_intent_id"].startswith("pi_test_")
    assert data["client_secret"].startswith("cs_test_")
    # Verify idempotency key was stored
    mock_idempotency_repo.save_key.assert_called_once()


@pytest.mark.asyncio
async def test_create_booking_idempotency_replay_cached_response(
    app_client: httpx.AsyncClient,
    mock_idempotency_repo: AsyncMock,
    mock_booking_repo: AsyncMock,
    user_auth_headers: dict[str, str],
    test_user_id: uuid.UUID,
) -> None:
    hold_id = uuid.uuid4()
    key = "idem-replay-key"
    payload = {"hold_id": str(hold_id)}

    import hashlib
    import json

    payload_bytes = json.dumps(payload).encode()
    hash_val = hashlib.sha256(payload_bytes).hexdigest()

    cached_record = IdempotencyKey(
        key=key,
        user_id=test_user_id,
        request_hash=hash_val,
        response_body='{"id": "b-cached", "status": "pending_payment", "total_cents": 5000}',
        status_code=201,
        created_at=datetime.now(UTC),
    )
    mock_idempotency_repo.get_key.return_value = cached_record

    response = await app_client.post(
        "/api/v1/booking/bookings",
        content=payload_bytes,
        headers={
            **user_auth_headers,
            "Content-Type": "application/json",
            "Idempotency-Key": key,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "b-cached"
    # Booking repository create_booking should NOT have been called on replay!
    mock_booking_repo.create_booking.assert_not_called()


@pytest.mark.asyncio
async def test_list_and_get_user_bookings(
    app_client: httpx.AsyncClient,
    mock_booking_repo: AsyncMock,
    user_auth_headers: dict[str, str],
    test_user_id: uuid.UUID,
) -> None:
    booking_id = uuid.uuid4()
    booking = Booking(
        id=booking_id,
        user_id=test_user_id,
        event_id=uuid.uuid4(),
        status="confirmed",
        total_cents=10000,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    booking.seats = []
    mock_booking_repo.list_user_bookings.return_value = [booking]
    mock_booking_repo.get_booking_by_id.return_value = booking

    # List
    list_res = await app_client.get("/api/v1/booking/bookings", headers=user_auth_headers)
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 1

    # Get by ID
    get_res = await app_client.get(
        f"/api/v1/booking/bookings/{booking_id}", headers=user_auth_headers
    )
    assert get_res.status_code == 200
    assert get_res.json()["id"] == str(booking_id)


@pytest.mark.asyncio
async def test_cancel_booking_success(
    app_client: httpx.AsyncClient,
    mock_booking_repo: AsyncMock,
    user_auth_headers: dict[str, str],
    test_user_id: uuid.UUID,
) -> None:
    booking_id = uuid.uuid4()
    seat = Seat(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        section="A",
        row="1",
        number=1,
        price_cents=5000,
        status="booked",
    )
    booking = Booking(
        id=booking_id,
        user_id=test_user_id,
        event_id=seat.event_id,
        status="confirmed",
        total_cents=5000,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    booking.seats = [seat]
    mock_booking_repo.get_booking_by_id.return_value = booking

    response = await app_client.post(
        f"/api/v1/booking/bookings/{booking_id}/cancel",
        headers=user_auth_headers,
    )

    assert response.status_code == 204
    assert booking.status == "cancelled"
    assert seat.status == "available"
