"""Integration tests for Inventory and Seats API routes."""

import uuid
from unittest.mock import AsyncMock

import httpx
import pytest

from app.models.seat import Seat


@pytest.mark.asyncio
async def test_admin_create_inventory_success(
    app_client: httpx.AsyncClient,
    mock_seat_repo: AsyncMock,
    admin_auth_headers: dict[str, str],
) -> None:
    event_id = uuid.uuid4()
    mock_seat_repo.count_seats_by_event.return_value = 0

    payload = {
        "sections": [
            {"name": "VIP", "rows": 2, "seats_per_row": 5, "price_cents": 15000},
        ]
    }

    response = await app_client.post(
        f"/api/v1/booking/events/{event_id}/inventory",
        json=payload,
        headers=admin_auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["event_id"] == str(event_id)
    assert data["total_seats_created"] == 10
    assert data["sections"] == ["VIP"]


@pytest.mark.asyncio
async def test_user_cannot_create_inventory(
    app_client: httpx.AsyncClient,
    user_auth_headers: dict[str, str],
) -> None:
    event_id = uuid.uuid4()
    payload = {"sections": [{"name": "GA", "rows": 1, "seats_per_row": 10, "price_cents": 2000}]}

    response = await app_client.post(
        f"/api/v1/booking/events/{event_id}/inventory",
        json=payload,
        headers=user_auth_headers,
    )

    assert response.status_code == 403
    data = response.json()
    assert data["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


@pytest.mark.asyncio
async def test_unauthenticated_cannot_create_inventory(
    app_client: httpx.AsyncClient,
) -> None:
    event_id = uuid.uuid4()
    payload = {"sections": [{"name": "GA", "rows": 1, "seats_per_row": 10, "price_cents": 2000}]}

    response = await app_client.post(
        f"/api/v1/booking/events/{event_id}/inventory",
        json=payload,
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_public_can_list_event_seats(
    app_client: httpx.AsyncClient,
    mock_seat_repo: AsyncMock,
) -> None:
    event_id = uuid.uuid4()
    seat = Seat(
        id=uuid.uuid4(),
        event_id=event_id,
        section="A",
        row="1",
        number=1,
        price_cents=3000,
        status="available",
    )
    mock_seat_repo.list_seats_by_event.return_value = [seat]

    response = await app_client.get(f"/api/v1/booking/events/{event_id}/seats")

    assert response.status_code == 200
    data = response.json()
    assert data["event_id"] == str(event_id)
    assert data["total"] == 1
    assert data["available_count"] == 1
    assert data["seats"][0]["id"] == str(seat.id)
