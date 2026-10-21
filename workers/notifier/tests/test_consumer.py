"""Unit tests for the SQSConsumer daemon."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.consumer import SQSConsumer
from app.handlers.booking_confirmed import BookingConfirmedHandler
from ticketrush_common.sqs import SQSClient


@pytest.mark.asyncio
async def test_consumer_processes_booking_confirmed_success(
    mock_sqs_client: SQSClient,
    booking_handler: BookingConfirmedHandler,
) -> None:
    """Verifies successful event processing and subsequent SQS message deletion."""
    booking_handler.handle = AsyncMock()  # type: ignore[method-assign]

    consumer = SQSConsumer(
        sqs_client=mock_sqs_client,
        booking_confirmed_handler=booking_handler,
        queue_url="http://sqs/main",
        dlq_url="http://sqs/dlq",
    )

    msg = {
        "MessageId": "msg-123",
        "ReceiptHandle": "receipt-abc",
        "Body": json.dumps(
            {
                "event_type": "booking.confirmed",
                "payload": {"booking_id": "b-123"},
            }
        ),
        "Attributes": {"ApproximateReceiveCount": "1"},
    }

    await consumer.process_single_message(msg)

    booking_handler.handle.assert_awaited_once_with({"booking_id": "b-123"})
    mock_sqs_client.delete_message.assert_awaited_once_with("http://sqs/main", "receipt-abc")  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_consumer_ignores_unknown_event_type(
    mock_sqs_client: SQSClient,
    booking_handler: BookingConfirmedHandler,
) -> None:
    """Verifies that unknown event types do not trigger the handler and are deleted."""
    booking_handler.handle = AsyncMock()  # type: ignore[method-assign]

    consumer = SQSConsumer(
        sqs_client=mock_sqs_client,
        booking_confirmed_handler=booking_handler,
        queue_url="http://sqs/main",
        dlq_url="http://sqs/dlq",
    )

    msg = {
        "MessageId": "msg-unknown",
        "ReceiptHandle": "receipt-xyz",
        "Body": json.dumps(
            {
                "event_type": "user.registered",
                "payload": {"user_id": "u-123"},
            }
        ),
    }

    await consumer.process_single_message(msg)

    booking_handler.handle.assert_not_awaited()
    mock_sqs_client.delete_message.assert_awaited_once_with("http://sqs/main", "receipt-xyz")  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_consumer_retries_transient_failure_with_backoff(
    mock_sqs_client: SQSClient,
    booking_handler: BookingConfirmedHandler,
) -> None:
    """Verifies that transient errors increase message visibility timeout and do not delete."""
    booking_handler.handle = AsyncMock(side_effect=RuntimeError("Transient error"))  # type: ignore[method-assign]

    consumer = SQSConsumer(
        sqs_client=mock_sqs_client,
        booking_confirmed_handler=booking_handler,
        queue_url="http://sqs/main",
        dlq_url="http://sqs/dlq",
        max_retries=3,
    )

    msg = {
        "MessageId": "msg-transient",
        "ReceiptHandle": "receipt-transient",
        "Body": json.dumps(
            {
                "event_type": "booking.confirmed",
                "payload": {"booking_id": "b-123"},
            }
        ),
        "Attributes": {"ApproximateReceiveCount": "1"},
    }

    await consumer.process_single_message(msg)

    mock_sqs_client.delete_message.assert_not_awaited()  # type: ignore[attr-defined]
    mock_sqs_client.change_message_visibility.assert_awaited_once()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_consumer_forwards_to_dlq_on_exceeded_retries(
    mock_sqs_client: SQSClient,
    booking_handler: BookingConfirmedHandler,
) -> None:
    """Verifies that exceeding max_retries pushes event to DLQ and deletes from main queue."""
    booking_handler.handle = AsyncMock(side_effect=ValueError("Fatal parsing bug"))  # type: ignore[method-assign]

    consumer = SQSConsumer(
        sqs_client=mock_sqs_client,
        booking_confirmed_handler=booking_handler,
        queue_url="http://sqs/main",
        dlq_url="http://sqs/dlq",
        max_retries=3,
    )

    msg = {
        "MessageId": "msg-fatal",
        "ReceiptHandle": "receipt-fatal",
        "Body": json.dumps(
            {
                "event_type": "booking.confirmed",
                "payload": {"booking_id": "b-123"},
            }
        ),
        "Attributes": {"ApproximateReceiveCount": "3"},
    }

    with patch("app.consumer.forward_to_dlq", new_callable=AsyncMock) as mock_forward:
        await consumer.process_single_message(msg)

        mock_forward.assert_awaited_once()
        mock_sqs_client.delete_message.assert_awaited_once_with(  # type: ignore[attr-defined]
            "http://sqs/main",
            "receipt-fatal",
        )


@pytest.mark.asyncio
async def test_consumer_run_loop(
    mock_sqs_client: SQSClient,
    booking_handler: BookingConfirmedHandler,
) -> None:
    """Verifies the consumer loop polls SQS and shuts down upon stop_event."""
    consumer = SQSConsumer(
        sqs_client=mock_sqs_client,
        booking_confirmed_handler=booking_handler,
        queue_url="http://sqs/main",
    )

    stop_event = asyncio.Event()

    async def fake_receive(*args: object, **kwargs: object) -> list[object]:
        stop_event.set()
        return []

    mock_sqs_client.receive_messages.side_effect = fake_receive  # type: ignore[attr-defined]
    await consumer.run(stop_event)

    mock_sqs_client.receive_messages.assert_awaited()  # type: ignore[attr-defined]
