"""API routes for event seat inventory management."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.deps import get_inventory_service, require_admin
from app.schemas.inventory import CreateInventoryRequest, CreateInventoryResponse
from app.services.inventory_service import InventoryService
from ticketrush_common.security import UserClaims

router = APIRouter(prefix="/booking/events", tags=["Booking Inventory"])


@router.post(
    "/{event_id}/inventory",
    response_model=CreateInventoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate seat inventory for an event (Admin only)",
)
async def create_inventory(
    event_id: uuid.UUID,
    payload: CreateInventoryRequest,
    _: UserClaims = Depends(require_admin),
    inventory_service: InventoryService = Depends(get_inventory_service),
) -> CreateInventoryResponse:
    """Generates seat grid layout for an event based on provided sections configuration."""
    return await inventory_service.generate_inventory(event_id=event_id, request=payload)
