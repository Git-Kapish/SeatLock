"""Public and Admin API routes for Event catalog."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_event_service, require_admin
from app.schemas.event import (
    CreateEventRequest,
    EventFilterParams,
    EventResponse,
    UpdateEventRequest,
)
from app.services.event_service import EventService
from ticketrush_common.pagination import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/events", tags=["Events"])


@router.get(
    "",
    response_model=PaginatedResponse[EventResponse],
    status_code=status.HTTP_200_OK,
    summary="List and search events",
)
async def list_events(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    city: str | None = Query(default=None, description="Filter by city"),
    category: str | None = Query(default=None, description="Filter by category"),
    status_filter: str | None = Query(
        default="on_sale", alias="status", description="Filter by status"
    ),
    start_date: datetime | None = Query(
        default=None, description="Filter events after UTC datetime"
    ),
    end_date: datetime | None = Query(
        default=None, description="Filter events before UTC datetime"
    ),
    q: str | None = Query(
        default=None, description="Full-text search query on title or description"
    ),
    event_service: EventService = Depends(get_event_service),
) -> PaginatedResponse[EventResponse]:
    """Retrieves paginated list of live events with filtering and search."""
    filters = EventFilterParams(
        city=city,
        category=category,
        status=status_filter,
        start_date=start_date,
        end_date=end_date,
        q=q,
    )
    pagination = PaginationParams(page=page, page_size=page_size)
    return await event_service.list_events(filters, pagination)


@router.get(
    "/{event_id}",
    response_model=EventResponse,
    status_code=status.HTTP_200_OK,
    summary="Get event details",
)
async def get_event(
    event_id: uuid.UUID,
    event_service: EventService = Depends(get_event_service),
) -> EventResponse:
    """Returns single event details by UUID (cached in Redis)."""
    return await event_service.get_event(event_id)


@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new event (Admin only)",
    dependencies=[Depends(require_admin)],
)
async def create_event(
    payload: CreateEventRequest,
    event_service: EventService = Depends(get_event_service),
) -> EventResponse:
    """Creates a new event catalog entry."""
    return await event_service.create_event(payload)


@router.patch(
    "/{event_id}",
    response_model=EventResponse,
    status_code=status.HTTP_200_OK,
    summary="Update event details or status (Admin only)",
    dependencies=[Depends(require_admin)],
)
async def update_event(
    event_id: uuid.UUID,
    payload: UpdateEventRequest,
    event_service: EventService = Depends(get_event_service),
) -> EventResponse:
    """Modifies event metadata or lifecycle status."""
    return await event_service.update_event(event_id, payload)


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_200_OK,
    summary="Soft delete an event (Admin only)",
    dependencies=[Depends(require_admin)],
)
async def delete_event(
    event_id: uuid.UUID,
    event_service: EventService = Depends(get_event_service),
) -> dict[str, str]:
    """Soft deletes an event catalog item."""
    await event_service.delete_event(event_id)
    return {"message": "Event successfully deleted"}
