"""Test fixtures and mock utilities for notifier worker."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.email import EmailAdapter
from app.handlers.booking_confirmed import BookingConfirmedHandler
from app.models import Hold, Seat
from ticketrush_common.sqs import SQSClient


@pytest.fixture
def mock_sqs_client() -> SQSClient:
    """Mock SQSClient instance."""
    client = MagicMock(spec=SQSClient)
    client.publish_event = AsyncMock(return_value="msg-dlq-123")
    client.delete_message = AsyncMock()
    client.change_message_visibility = AsyncMock()
    client.receive_messages = AsyncMock(return_value=[])
    client.create_queue_if_not_exists = AsyncMock(return_value="http://queue-url")
    return client


@pytest.fixture
def mock_email_adapter() -> EmailAdapter:
    """Mock EmailAdapter instance."""
    adapter = MagicMock(spec=EmailAdapter)
    adapter.send_email = AsyncMock(return_value=True)
    return adapter


@pytest.fixture
def booking_handler(mock_email_adapter: EmailAdapter) -> BookingConfirmedHandler:
    """BookingConfirmedHandler initialized with mocked email adapter."""
    return BookingConfirmedHandler(email_adapter=mock_email_adapter)


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Mock Redis client."""
    client = AsyncMock()
    client.delete = AsyncMock(return_value=1)
    return client


@pytest.fixture
def sample_seat() -> Seat:
    """Sample held seat."""
    return Seat(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        tier="VIP",
        section="A",
        row="1",
        seat_number=10,
        status="held",
        version=1,
    )


@pytest.fixture
def sample_expired_hold(sample_seat: Seat) -> Hold:
    """Sample expired hold with associated seat."""
    hold = Hold(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        event_id=sample_seat.event_id,
        status="active",
        expires_at=datetime(2020, 1, 1, 0, 0, tzinfo=UTC),
    )
    hold.seats = [sample_seat]
    return hold
