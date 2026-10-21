"""Unit tests for HoldRepository."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.hold import Hold, HoldSeat
from app.repositories.hold_repository import HoldRepository


@pytest.mark.asyncio
async def test_create_hold_repository() -> None:
    session = MagicMock()
    session.flush = AsyncMock()
    repo = HoldRepository(session)
    hold = Hold(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        status="active",
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    hold_seat = HoldSeat(hold_id=hold.id, seat_id=uuid.uuid4())

    saved = await repo.create_hold(hold, [hold_seat])

    assert saved.id == hold.id
    session.add.assert_called_once_with(hold)
    session.add_all.assert_called_once_with([hold_seat])
    assert session.flush.call_count == 2


@pytest.mark.asyncio
async def test_count_active_holds_for_user() -> None:
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 2
    session.execute.return_value = mock_result

    repo = HoldRepository(session)
    count = await repo.count_active_holds_for_user(uuid.uuid4())

    assert count == 2
