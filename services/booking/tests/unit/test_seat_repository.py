"""Unit tests for SeatRepository."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.seat import Seat
from app.repositories.seat_repository import SeatRepository


@pytest.mark.asyncio
async def test_get_seats_for_update_executes_sorted_query() -> None:
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute.return_value = mock_result

    repo = SeatRepository(session)
    event_id = uuid.uuid4()
    s1, s2 = uuid.uuid4(), uuid.uuid4()

    seats = await repo.get_seats_for_update(event_id, [s1, s2])

    assert seats == []
    session.execute.assert_called_once()
    # Query was compiled and executed
    stmt = session.execute.call_args[0][0]
    compiled_sql = str(stmt)
    assert "FOR UPDATE" in compiled_sql
    assert "ORDER BY booking.seats.id ASC" in compiled_sql


@pytest.mark.asyncio
async def test_bulk_create_seats() -> None:
    session = MagicMock()
    session.flush = AsyncMock()
    repo = SeatRepository(session)
    seat = Seat(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        section="A",
        row="1",
        number=1,
        price_cents=1000,
        status="available",
    )

    await repo.bulk_create_seats([seat])

    session.add_all.assert_called_once_with([seat])
    session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_count_seats_by_event() -> None:
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 42
    session.execute.return_value = mock_result

    repo = SeatRepository(session)
    count = await repo.count_seats_by_event(uuid.uuid4())

    assert count == 42
