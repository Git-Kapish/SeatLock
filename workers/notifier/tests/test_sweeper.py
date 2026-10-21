"""Unit tests for the hold expiration database sweeper."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models import Hold, Seat
from app.sweeper import HoldSweeper


@pytest.mark.asyncio
async def test_sweeper_expires_overdue_holds(
    sample_expired_hold: Hold,
    sample_seat: Seat,
    mock_redis: AsyncMock,
) -> None:
    """Verifies that expired holds are marked 'expired' and held seats return to 'available'."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sample_expired_hold]
    session.execute = AsyncMock(return_value=mock_result)
    session.commit = AsyncMock()

    sweeper = HoldSweeper(redis_client=mock_redis)
    count = await sweeper.sweep_once(session)

    assert count == 1
    assert sample_expired_hold.status == "expired"
    assert sample_seat.status == "available"
    assert sample_seat.version == 2

    session.commit.assert_awaited_once()

    # Verify Redis key deletion for held seat
    expected_key = f"hold:{sample_expired_hold.event_id}:{sample_seat.id}"
    mock_redis.delete.assert_awaited_once_with(expected_key)


@pytest.mark.asyncio
async def test_sweeper_no_expired_holds(mock_redis: AsyncMock) -> None:
    """Verifies that no mutations occur when all holds are active/valid."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)
    session.commit = AsyncMock()

    sweeper = HoldSweeper(redis_client=mock_redis)
    count = await sweeper.sweep_once(session)

    assert count == 0
    session.commit.assert_not_awaited()
    mock_redis.delete.assert_not_awaited()
