"""Unit tests for EventService business logic and caching."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.models.event import Event
from app.schemas.event import (
    CreateEventRequest,
    EventFilterParams,
    UpdateEventRequest,
)
from app.services.event_service import EventService
from ticketrush_common.errors import ConflictError, NotFoundError, ValidationError
from ticketrush_common.pagination import PaginationParams


def sample_event(event_id: uuid.UUID | None = None, status: str = "draft") -> Event:
    return Event(
        id=event_id or uuid.uuid4(),
        title="Coldplay World Tour",
        description="Music of the Spheres world concert tour.",
        venue="Wembley Stadium",
        city="London",
        category="Concert",
        starts_at=datetime.now(UTC) + timedelta(days=30),
        status=status,
        deleted_at=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_get_event_cache_miss_fetches_repo(
    event_service: EventService,
    mock_event_repo: AsyncMock,
    mock_redis_client: AsyncMock,
):
    ev = sample_event()
    mock_redis_client.get.return_value = None
    mock_event_repo.get_by_id.return_value = ev

    res = await event_service.get_event(ev.id)
    assert res.title == "Coldplay World Tour"
    mock_event_repo.get_by_id.assert_called_once_with(ev.id)
    mock_redis_client.setex.assert_called_once()


@pytest.mark.asyncio
async def test_get_event_not_found_raises(event_service: EventService, mock_event_repo: AsyncMock):
    mock_event_repo.get_by_id.return_value = None
    with pytest.raises(NotFoundError) as exc_info:
        await event_service.get_event(uuid.uuid4())
    assert exc_info.value.code == "EVENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_list_events_with_pagination(event_service: EventService, mock_event_repo: AsyncMock):
    ev1 = sample_event()
    ev2 = sample_event()
    mock_event_repo.list_events.return_value = ([ev1, ev2], 2)

    filters = EventFilterParams(status="draft")
    pagination = PaginationParams(page=1, page_size=10)

    res = await event_service.list_events(filters, pagination)
    assert res.total == 2
    assert len(res.items) == 2
    assert res.page == 1
    assert res.total_pages == 1


@pytest.mark.asyncio
async def test_create_event_invalidates_cache(
    event_service: EventService,
    mock_event_repo: AsyncMock,
    mock_redis_client: AsyncMock,
):
    ev = sample_event()
    mock_event_repo.create_event.return_value = ev

    req = CreateEventRequest(
        title="Coldplay World Tour",
        description="Music of the Spheres world concert tour.",
        venue="Wembley Stadium",
        city="London",
        category="Concert",
        starts_at=datetime.now(UTC) + timedelta(days=30),
        status="draft",
    )

    res = await event_service.create_event(req)
    assert res.title == "Coldplay World Tour"
    mock_redis_client.delete.assert_called()


@pytest.mark.asyncio
async def test_update_event_valid_status_transition(
    event_service: EventService,
    mock_event_repo: AsyncMock,
):
    ev = sample_event(status="draft")
    mock_event_repo.get_by_id.return_value = ev

    updated_ev = sample_event(event_id=ev.id, status="published")
    mock_event_repo.update_event.return_value = updated_ev

    req = UpdateEventRequest(status="published")
    res = await event_service.update_event(ev.id, req)
    assert res.status == "published"


@pytest.mark.asyncio
async def test_update_event_invalid_status_transition(
    event_service: EventService,
    mock_event_repo: AsyncMock,
):
    ev = sample_event(status="draft")
    mock_event_repo.get_by_id.return_value = ev

    # draft cannot transition directly to completed
    req = UpdateEventRequest(status="completed")
    with pytest.raises(ValidationError) as exc_info:
        await event_service.update_event(ev.id, req)
    assert exc_info.value.code == "INVALID_STATUS_TRANSITION"


@pytest.mark.asyncio
async def test_validate_event_for_booking_on_sale(
    event_service: EventService,
    mock_event_repo: AsyncMock,
):
    ev = sample_event(status="on_sale")
    mock_event_repo.get_by_id.return_value = ev

    res = await event_service.validate_event_for_booking(ev.id)
    assert res.status == "on_sale"


@pytest.mark.asyncio
async def test_validate_event_for_booking_draft_raises_conflict(
    event_service: EventService,
    mock_event_repo: AsyncMock,
):
    ev = sample_event(status="draft")
    mock_event_repo.get_by_id.return_value = ev

    with pytest.raises(ConflictError) as exc_info:
        await event_service.validate_event_for_booking(ev.id)
    assert exc_info.value.code == "EVENT_NOT_ON_SALE"
