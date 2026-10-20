"""Internal service-to-service API routes for Events."""

import uuid

from fastapi import APIRouter, Depends, status

from app.api.deps import get_event_service, verify_internal_service
from app.schemas.event import EventResponse
from app.services.event_service import EventService

router = APIRouter(
    prefix="/internal/events",
    tags=["Internal Events"],
    dependencies=[Depends(verify_internal_service)],
)


@router.get(
    "/{event_id}",
    response_model=EventResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate event is on_sale for booking service",
)
async def validate_event(
    event_id: uuid.UUID,
    event_service: EventService = Depends(get_event_service),
) -> EventResponse:
    """Verifies event exists and is currently in 'on_sale' status."""
    return await event_service.validate_event_for_booking(event_id)
