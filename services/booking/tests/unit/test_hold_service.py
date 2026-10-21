"""Unit tests for HoldService."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.models.hold import Hold
from app.models.seat import Seat
from app.schemas.hold import CreateHoldRequest
from app.services.hold_service import HoldService
from ticketrush_common.errors import ConflictError, ForbiddenError, ValidationError


@pytest.mark.asyncio
async def test_create_hold_success(
    hold_service: HoldService,
    mock_hold_repo: AsyncMock,
    mock_seat_repo: AsyncMock,
    mock_redis_client: AsyncMock,
    mock_events_client: AsyncMock,
    test_user_id: uuid.UUID,
) -> None:
    event_id = uuid.uuid4()
    seat_1 = Seat(
        id=uuid.uuid4(),
        event_id=event_id,
        section="A",
        row="1",
        number=1,
        price_cents=5000,
        status="available",
    )
    seat_2 = Seat(
        id=uuid.uuid4(),
        event_id=event_id,
        section="A",
        row="1",
        number=2,
        price_cents=7500,
        status="available",
    )

    mock_hold_repo.count_active_holds_for_user.return_value = 0
    mock_redis_client.eval.return_value = [1, "OK"]
    mock_seat_repo.get_seats_for_update.return_value = [seat_1, seat_2]

    req = CreateHoldRequest(event_id=event_id, seat_ids=[seat_1.id, seat_2.id])
    res = await hold_service.create_hold(user_id=test_user_id, request=req)

    assert res.user_id == test_user_id
    assert res.event_id == event_id
    assert res.status == "active"
    assert res.total_price_cents == 12500
    assert set(res.seat_ids) == {seat_1.id, seat_2.id}
    assert seat_1.status == "held"
    assert seat_2.status == "held"
    mock_hold_repo.create_hold.assert_called_once()


@pytest.mark.asyncio
async def test_create_hold_limit_exceeded(
    hold_service: HoldService,
    test_user_id: uuid.UUID,
) -> None:
    event_id = uuid.uuid4()
    req = CreateHoldRequest.model_construct(
        event_id=event_id, seat_ids=[uuid.uuid4() for _ in range(7)]
    )

    with pytest.raises(ValidationError) as exc_info:
        await hold_service.create_hold(test_user_id, req)

    assert exc_info.value.code == "HOLD_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_create_hold_duplicate_seats_rejected(
    hold_service: HoldService,
    test_user_id: uuid.UUID,
) -> None:
    event_id = uuid.uuid4()
    duplicate_id = uuid.uuid4()
    req = CreateHoldRequest(event_id=event_id, seat_ids=[duplicate_id, duplicate_id])

    with pytest.raises(ValidationError) as exc_info:
        await hold_service.create_hold(test_user_id, req)

    assert exc_info.value.code == "DUPLICATE_SEAT_SELECTION"


@pytest.mark.asyncio
async def test_create_hold_user_max_active_holds_reached(
    hold_service: HoldService,
    mock_hold_repo: AsyncMock,
    test_user_id: uuid.UUID,
) -> None:
    event_id = uuid.uuid4()
    mock_hold_repo.count_active_holds_for_user.return_value = 3

    req = CreateHoldRequest(event_id=event_id, seat_ids=[uuid.uuid4()])
    with pytest.raises(ConflictError) as exc_info:
        await hold_service.create_hold(test_user_id, req)

    assert exc_info.value.code == "MAX_ACTIVE_HOLDS_REACHED"


@pytest.mark.asyncio
async def test_create_hold_redis_conflict(
    hold_service: HoldService,
    mock_hold_repo: AsyncMock,
    mock_redis_client: AsyncMock,
    test_user_id: uuid.UUID,
) -> None:
    event_id = uuid.uuid4()
    seat_id = uuid.uuid4()
    mock_hold_repo.count_active_holds_for_user.return_value = 0
    # Lua script returns conflict [0, "hold:..."]
    mock_redis_client.eval.return_value = [0, f"hold:{event_id}:{seat_id}"]

    req = CreateHoldRequest(event_id=event_id, seat_ids=[seat_id])
    with pytest.raises(ConflictError) as exc_info:
        await hold_service.create_hold(test_user_id, req)

    assert exc_info.value.code == "SEAT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_create_hold_db_seat_already_held_rolls_back_redis(
    hold_service: HoldService,
    mock_hold_repo: AsyncMock,
    mock_seat_repo: AsyncMock,
    mock_redis_client: AsyncMock,
    test_user_id: uuid.UUID,
) -> None:
    event_id = uuid.uuid4()
    seat = Seat(
        id=uuid.uuid4(),
        event_id=event_id,
        section="A",
        row="1",
        number=1,
        price_cents=5000,
        status="held",  # Already held in DB
    )
    mock_hold_repo.count_active_holds_for_user.return_value = 0
    mock_redis_client.eval.return_value = [1, "OK"]
    mock_seat_repo.get_seats_for_update.return_value = [seat]

    req = CreateHoldRequest(event_id=event_id, seat_ids=[seat.id])
    with pytest.raises(ConflictError) as exc_info:
        await hold_service.create_hold(test_user_id, req)

    assert exc_info.value.code == "SEAT_UNAVAILABLE"
    # Verify rollback lua script was invoked
    assert mock_redis_client.eval.call_count == 2


@pytest.mark.asyncio
async def test_release_hold_success(
    hold_service: HoldService,
    mock_hold_repo: AsyncMock,
    mock_seat_repo: AsyncMock,
    mock_redis_client: AsyncMock,
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
    )
    hold.seats = [seat]
    mock_hold_repo.get_hold_by_id.return_value = hold
    mock_seat_repo.get_seats_for_update.return_value = [seat]

    await hold_service.release_hold(hold_id=hold_id, user_id=test_user_id)

    assert hold.status == "released"
    assert seat.status == "available"
    mock_redis_client.eval.assert_called_once()


@pytest.mark.asyncio
async def test_release_hold_forbidden_for_other_user(
    hold_service: HoldService,
    mock_hold_repo: AsyncMock,
    test_user_id: uuid.UUID,
) -> None:
    hold_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    hold = Hold(
        id=hold_id,
        user_id=other_user_id,
        event_id=uuid.uuid4(),
        status="active",
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    mock_hold_repo.get_hold_by_id.return_value = hold

    with pytest.raises(ForbiddenError):
        await hold_service.release_hold(hold_id=hold_id, user_id=test_user_id, is_admin=False)
