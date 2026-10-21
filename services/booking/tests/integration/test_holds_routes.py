"""Integration tests for Holds API routes."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest

from app.models.hold import Hold
from app.models.seat import Seat


@pytest.mark.asyncio
async def test_create_hold_endpoint_success(
    app_client: httpx.AsyncClient,
    mock_hold_repo: AsyncMock,
    mock_seat_repo: AsyncMock,
    mock_redis_client: AsyncMock,
    user_auth_headers: dict[str, str],
    test_user_id: uuid.UUID,
) -> None:
    event_id = uuid.uuid4()
    seat_id = uuid.uuid4()
    seat = Seat(
        id=seat_id,
        event_id=event_id,
        section="Floor",
        row="1",
        number=1,
        price_cents=6000,
        status="available",
    )

    mock_hold_repo.count_active_holds_for_user.return_value = 0
    mock_redis_client.eval.return_value = [1, "OK"]
    mock_seat_repo.get_seats_for_update.return_value = [seat]

    payload = {
        "event_id": str(event_id),
        "seat_ids": [str(seat_id)],
    }

    response = await app_client.post(
        "/api/v1/booking/holds",
        json=payload,
        headers=user_auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == str(test_user_id)
    assert data["event_id"] == str(event_id)
    assert data["status"] == "active"
    assert data["total_price_cents"] == 6000
    assert data["seat_ids"] == [str(seat_id)]


@pytest.mark.asyncio
async def test_get_hold_endpoint(
    app_client: httpx.AsyncClient,
    mock_hold_repo: AsyncMock,
    user_auth_headers: dict[str, str],
    test_user_id: uuid.UUID,
) -> None:
    hold_id = uuid.uuid4()
    event_id = uuid.uuid4()
    seat = Seat(
        id=uuid.uuid4(),
        event_id=event_id,
        section="A",
        row="1",
        number=1,
        price_cents=5000,
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
    mock_hold_repo.get_hold_by_id.return_value = hold

    response = await app_client.get(
        f"/api/v1/booking/holds/{hold_id}",
        headers=user_auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(hold_id)
    assert data["user_id"] == str(test_user_id)


@pytest.mark.asyncio
async def test_release_hold_endpoint(
    app_client: httpx.AsyncClient,
    mock_hold_repo: AsyncMock,
    mock_seat_repo: AsyncMock,
    user_auth_headers: dict[str, str],
    test_user_id: uuid.UUID,
) -> None:
    hold_id = uuid.uuid4()
    event_id = uuid.uuid4()
    seat = Seat(
        id=uuid.uuid4(),
        event_id=event_id,
        section="A",
        row="1",
        number=1,
        price_cents=5000,
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
    mock_hold_repo.get_hold_by_id.return_value = hold
    mock_seat_repo.get_seats_for_update.return_value = [seat]

    response = await app_client.delete(
        f"/api/v1/booking/holds/{hold_id}",
        headers=user_auth_headers,
    )

    assert response.status_code == 204
