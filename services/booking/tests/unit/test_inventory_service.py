"""Unit tests for InventoryService."""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.models.seat import Seat
from app.schemas.inventory import CreateInventoryRequest, SectionConfig
from app.services.inventory_service import InventoryService
from ticketrush_common.errors import ConflictError


@pytest.mark.asyncio
async def test_generate_inventory_success(mock_seat_repo: AsyncMock) -> None:
    event_id = uuid.uuid4()
    mock_seat_repo.count_seats_by_event.return_value = 0

    service = InventoryService(seat_repo=mock_seat_repo)
    request = CreateInventoryRequest(
        sections=[
            SectionConfig(name="Floor", rows=2, seats_per_row=5, price_cents=10000),
            SectionConfig(name="Balcony", rows=1, seats_per_row=4, price_cents=5000),
        ]
    )

    res = await service.generate_inventory(event_id, request)

    assert res.event_id == event_id
    # Floor: 2*5 = 10, Balcony: 1*4 = 4 -> Total = 14
    assert res.total_seats_created == 14
    assert res.sections == ["Floor", "Balcony"]
    mock_seat_repo.bulk_create_seats.assert_called_once()
    created_seats = mock_seat_repo.bulk_create_seats.call_args[0][0]
    assert len(created_seats) == 14
    assert created_seats[0].event_id == event_id
    assert created_seats[0].status == "available"


@pytest.mark.asyncio
async def test_generate_inventory_conflict_if_exists(mock_seat_repo: AsyncMock) -> None:
    event_id = uuid.uuid4()
    mock_seat_repo.count_seats_by_event.return_value = 50

    service = InventoryService(seat_repo=mock_seat_repo)
    request = CreateInventoryRequest(
        sections=[SectionConfig(name="VIP", rows=1, seats_per_row=10, price_cents=15000)]
    )

    with pytest.raises(ConflictError) as exc_info:
        await service.generate_inventory(event_id, request)

    assert exc_info.value.code == "INVENTORY_ALREADY_EXISTS"
    mock_seat_repo.bulk_create_seats.assert_not_called()


@pytest.mark.asyncio
async def test_list_event_seats(mock_seat_repo: AsyncMock) -> None:
    event_id = uuid.uuid4()
    s1 = Seat(
        id=uuid.uuid4(),
        event_id=event_id,
        section="A",
        row="1",
        number=1,
        price_cents=5000,
        status="available",
    )
    s2 = Seat(
        id=uuid.uuid4(),
        event_id=event_id,
        section="A",
        row="1",
        number=2,
        price_cents=5000,
        status="held",
    )
    mock_seat_repo.list_seats_by_event.return_value = [s1, s2]

    service = InventoryService(seat_repo=mock_seat_repo)
    res = await service.list_event_seats(event_id)

    assert res.event_id == event_id
    assert res.total == 2
    assert res.available_count == 1
    assert len(res.seats) == 2
