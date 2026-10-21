"""API routes for seat holds."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user, get_hold_service
from app.schemas.hold import CreateHoldRequest, HoldResponse
from app.services.hold_service import HoldService
from ticketrush_common.security import UserClaims

router = APIRouter(prefix="/booking/holds", tags=["Booking Holds"])


@router.post(
    "",
    response_model=HoldResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Acquire atomic hold on selected seats",
)
async def create_hold(
    payload: CreateHoldRequest,
    current_user: UserClaims = Depends(get_current_user),
    hold_service: HoldService = Depends(get_hold_service),
) -> HoldResponse:
    """Acquires a 10-minute hold on up to 6 seats using Redis Lua atomic locking and Postgres row locking."""
    user_id = uuid.UUID(current_user.user_id)
    return await hold_service.create_hold(user_id=user_id, request=payload)


@router.get(
    "/{hold_id}",
    response_model=HoldResponse,
    status_code=status.HTTP_200_OK,
    summary="Get hold details",
)
async def get_hold(
    hold_id: uuid.UUID,
    current_user: UserClaims = Depends(get_current_user),
    hold_service: HoldService = Depends(get_hold_service),
) -> HoldResponse:
    """Fetches details of an existing seat hold belonging to the caller."""
    user_id = uuid.UUID(current_user.user_id)
    return await hold_service.get_hold(hold_id=hold_id, user_id=user_id)


@router.delete(
    "/{hold_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Release an active hold early",
)
async def release_hold(
    hold_id: uuid.UUID,
    current_user: UserClaims = Depends(get_current_user),
    hold_service: HoldService = Depends(get_hold_service),
) -> None:
    """Releases an active hold, making the seats immediately available for other users."""
    is_admin = current_user.role == "admin"
    user_id = uuid.UUID(current_user.user_id)
    await hold_service.release_hold(hold_id=hold_id, user_id=user_id, is_admin=is_admin)
