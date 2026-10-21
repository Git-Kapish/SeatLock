"""Unit tests for the BookingConfirmedHandler."""

import pytest

from app.email import EmailAdapter
from app.handlers.booking_confirmed import BookingConfirmedHandler


@pytest.mark.asyncio
async def test_booking_confirmed_handler_success(mock_email_adapter: EmailAdapter) -> None:
    """Verifies that booking.confirmed event triggers email dispatch with formatted values."""
    handler = BookingConfirmedHandler(email_adapter=mock_email_adapter)

    payload = {
        "booking_id": "b1a2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
        "user_id": "u1a2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
        "user_email": "user@example.com",
        "event_id": "evt-789",
        "total_cents": 12500,
        "seat_ids": ["seat-1", "seat-2"],
    }

    await handler.handle(payload)

    mock_email_adapter.send_email.assert_awaited_once()  # type: ignore[attr-defined]
    call_kwargs = mock_email_adapter.send_email.await_args.kwargs  # type: ignore[attr-defined]

    assert call_kwargs["to_email"] == "user@example.com"
    assert "b1a2c3d4" in call_kwargs["subject"]
    assert "$125.00" in call_kwargs["body_text"]
    assert "seat-1, seat-2" in call_kwargs["body_text"]
    assert "Booking Confirmation</h1>" in call_kwargs["body_html"]


@pytest.mark.asyncio
async def test_booking_confirmed_handler_generates_fallback_email(
    mock_email_adapter: EmailAdapter,
) -> None:
    """Verifies that missing user_email defaults to user-{id[:8]}@example.com."""
    handler = BookingConfirmedHandler(email_adapter=mock_email_adapter)

    payload = {
        "booking_id": "b1a2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
        "user_id": "a9876543-1234-5678-90ab-cdef12345678",
        "total_cents": 5000,
        "seat_ids": ["seat-1"],
    }

    await handler.handle(payload)

    call_kwargs = mock_email_adapter.send_email.await_args.kwargs  # type: ignore[attr-defined]
    assert call_kwargs["to_email"] == "user-a9876543@example.com"
