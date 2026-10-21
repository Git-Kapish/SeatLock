"""API routes for querying seat availability."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.deps import get_inventory_service
from app.schemas.seat import SeatListResponse
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/booking/events", tags=["Booking Seats"])


@router.get(
    "/{event_id}/seats",
    response_model=SeatListResponse,
    status_code=status.HTTP_200_OK,
    summary="List seat availability for an event",
)
async def list_seats(
    event_id: uuid.UUID,
    inventory_service: InventoryService = Depends(get_inventory_service),
) -> SeatListResponse:
    """Returns the current inventory and availability status for all seats in an event."""
    return await inventory_service.list_event_seats(event_id=event_id)
