"""API routes for ticket bookings and checkout."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Request, Response, status

from app.api.deps import (
    get_booking_service,
    get_current_user,
    get_idempotency_service,
    rate_limit_bookings,
)
from app.schemas.booking import BookingListResponse, BookingResponse, CreateBookingRequest
from app.services.booking_service import BookingService
from app.services.idempotency_service import IdempotencyService
from ticketrush_common.security import UserClaims

router = APIRouter(prefix="/booking/bookings", tags=["Bookings"])


@router.post(
    "",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a booking from an active hold with idempotency protection",
    dependencies=[Depends(rate_limit_bookings)],
)
async def create_booking(
    request: Request,
    response: Response,
    payload: CreateBookingRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: UserClaims = Depends(get_current_user),
    booking_service: BookingService = Depends(get_booking_service),
    idempotency_service: IdempotencyService = Depends(get_idempotency_service),
) -> Response:
    """Converts an active hold into a pending booking and initiates mock payment intent.

    Supports optional or mandatory 'Idempotency-Key' header. If provided, replaying the
    identical payload returns the cached response with zero duplicate bookings. Replaying
    with a different payload yields HTTP 422 IDEMPOTENCY_CONFLICT.
    """
    user_id = uuid.UUID(current_user.user_id)
    raw_body = await request.body()

    # 1. Check idempotency cache if header supplied
    if idempotency_key:
        cached = await idempotency_service.check_idempotency(
            key=idempotency_key,
            user_id=user_id,
            payload_bytes=raw_body,
        )
        if cached:
            cached_status, cached_body = cached
            return Response(
                content=cached_body,
                status_code=cached_status,
                media_type="application/json",
                headers=dict(response.headers),
            )

    # 2. Execute domain booking workflow
    booking = await booking_service.create_booking(user_id=user_id, request=payload)
    response_body = booking.model_dump_json()

    # 3. Cache response in idempotency store
    if idempotency_key:
        await idempotency_service.save_idempotency_record(
            key=idempotency_key,
            user_id=user_id,
            payload_bytes=raw_body,
            status_code=status.HTTP_201_CREATED,
            response_body=response_body,
        )

    return Response(
        content=response_body,
        status_code=status.HTTP_201_CREATED,
        media_type="application/json",
        headers=dict(response.headers),
    )


@router.get(
    "",
    response_model=BookingListResponse,
    status_code=status.HTTP_200_OK,
    summary="List bookings for the authenticated user",
)
async def list_bookings(
    current_user: UserClaims = Depends(get_current_user),
    booking_service: BookingService = Depends(get_booking_service),
) -> BookingListResponse:
    """Returns all ticket bookings belonging to the authenticated caller."""
    user_id = uuid.UUID(current_user.user_id)
    return await booking_service.list_user_bookings(user_id=user_id)


@router.get(
    "/{booking_id}",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Get details of a booking",
)
async def get_booking(
    booking_id: uuid.UUID,
    current_user: UserClaims = Depends(get_current_user),
    booking_service: BookingService = Depends(get_booking_service),
) -> BookingResponse:
    """Fetches full details of an individual booking, verifying ownership."""
    user_id = uuid.UUID(current_user.user_id)
    return await booking_service.get_booking(booking_id=booking_id, user_id=user_id)


@router.post(
    "/{booking_id}/cancel",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a booking and release its seats",
)
async def cancel_booking(
    booking_id: uuid.UUID,
    current_user: UserClaims = Depends(get_current_user),
    booking_service: BookingService = Depends(get_booking_service),
) -> None:
    """Cancels a booking, restoring its booked seats to available status."""
    is_admin = current_user.role == "admin"
    user_id = uuid.UUID(current_user.user_id)
    await booking_service.cancel_booking(booking_id=booking_id, user_id=user_id, is_admin=is_admin)
