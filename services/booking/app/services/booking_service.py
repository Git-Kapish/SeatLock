"""Booking orchestration service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.booking import Booking, BookingSeat
from app.repositories.booking_repository import BookingRepository
from app.repositories.hold_repository import HoldRepository
from app.repositories.seat_repository import SeatRepository
from app.schemas.booking import BookingListResponse, BookingResponse, CreateBookingRequest
from app.schemas.seat import SeatResponse
from app.services.payment_service import PaymentService
from ticketrush_common.errors import ConflictError, ForbiddenError, NotFoundError


class BookingService:
    """Manages booking lifecycle: creation, payment initialization, and cancellation."""

    def __init__(
        self,
        booking_repo: BookingRepository,
        hold_repo: HoldRepository,
        seat_repo: SeatRepository,
        payment_service: PaymentService,
    ) -> None:
        self.booking_repo = booking_repo
        self.hold_repo = hold_repo
        self.seat_repo = seat_repo
        self.payment_service = payment_service

    async def create_booking(
        self,
        user_id: uuid.UUID,
        request: CreateBookingRequest,
    ) -> BookingResponse:
        """Converts an active hold into a pending booking and initiates payment."""
        hold = await self.hold_repo.get_active_hold_by_id(request.hold_id)
        if not hold:
            raise NotFoundError(
                message=f"Active hold {request.hold_id} not found or has expired",
                code="HOLD_NOT_FOUND",
            )

        if hold.user_id != user_id:
            raise ForbiddenError(
                message="Not authorized to convert this hold",
                code="HOLD_ACCESS_DENIED",
            )

        now = datetime.now(UTC)
        total_cents = sum(s.price_cents for s in hold.seats)
        booking_id = uuid.uuid4()

        booking = Booking(
            id=booking_id,
            user_id=user_id,
            event_id=hold.event_id,
            hold_id=hold.id,
            total_cents=total_cents,
            status="pending_payment",
            created_at=now,
            updated_at=now,
        )

        booking_seats = [
            BookingSeat(booking_id=booking_id, seat_id=s.id, status="pending_payment")
            for s in hold.seats
        ]

        await self.booking_repo.create_booking(booking, booking_seats)

        # Create payment intent
        provider_ref, client_secret = await self.payment_service.create_payment_intent(
            booking_id=booking_id,
            amount_cents=total_cents,
        )

        return BookingResponse(
            id=booking.id,
            user_id=booking.user_id,
            event_id=booking.event_id,
            hold_id=booking.hold_id,
            status=booking.status,
            total_cents=booking.total_cents,
            created_at=booking.created_at,
            seats=[SeatResponse.model_validate(s) for s in hold.seats],
            payment_intent_id=provider_ref,
            client_secret=client_secret,
        )

    async def list_user_bookings(self, user_id: uuid.UUID) -> BookingListResponse:
        """Retrieves complete booking history for a user."""
        bookings = await self.booking_repo.list_user_bookings(user_id)
        items = [
            BookingResponse(
                id=b.id,
                user_id=b.user_id,
                event_id=b.event_id,
                hold_id=b.hold_id,
                status=b.status,
                total_cents=b.total_cents,
                created_at=b.created_at,
                seats=[SeatResponse.model_validate(s) for s in b.seats],
            )
            for b in bookings
        ]
        return BookingListResponse(total=len(items), items=items)

    async def get_booking(self, booking_id: uuid.UUID, user_id: uuid.UUID) -> BookingResponse:
        """Retrieves details of an individual booking, enforcing ownership."""
        booking = await self.booking_repo.get_booking_by_id(booking_id)
        if not booking:
            raise NotFoundError(
                message=f"Booking {booking_id} not found",
                code="BOOKING_NOT_FOUND",
            )

        if booking.user_id != user_id:
            raise ForbiddenError(
                message="Not authorized to view this booking",
                code="BOOKING_ACCESS_DENIED",
            )

        return BookingResponse(
            id=booking.id,
            user_id=booking.user_id,
            event_id=booking.event_id,
            hold_id=booking.hold_id,
            status=booking.status,
            total_cents=booking.total_cents,
            created_at=booking.created_at,
            seats=[SeatResponse.model_validate(s) for s in booking.seats],
        )

    async def cancel_booking(
        self,
        booking_id: uuid.UUID,
        user_id: uuid.UUID,
        is_admin: bool = False,
    ) -> None:
        """Cancels a booking and restores its seats to available status."""
        booking = await self.booking_repo.get_booking_by_id(booking_id)
        if not booking:
            raise NotFoundError(
                message=f"Booking {booking_id} not found",
                code="BOOKING_NOT_FOUND",
            )

        if not is_admin and booking.user_id != user_id:
            raise ForbiddenError(
                message="Not authorized to cancel this booking",
                code="BOOKING_ACCESS_DENIED",
            )

        if booking.status in ("cancelled", "failed"):
            raise ConflictError(
                message=f"Booking is already in '{booking.status}' state",
                code="BOOKING_ALREADY_CANCELLED",
            )

        booking.status = "cancelled"
        booking.updated_at = datetime.now(UTC)

        # Release seats
        for s in booking.seats:
            s.status = "available"
            s.version = (s.version or 1) + 1
