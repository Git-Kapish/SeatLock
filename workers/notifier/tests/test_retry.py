"""Unit tests for retry backoff, jitter, and Dead-Letter Queue routing."""

import pytest

from app.retry import calculate_backoff, forward_to_dlq, should_send_to_dlq
from ticketrush_common.sqs import SQSClient


def test_calculate_backoff_deterministic() -> None:
    """Verifies exponential progression without jitter."""
    # base = 2.0, retry_count = 1 -> exponent = 0 -> 2 * 2^0 = 2
    assert calculate_backoff(retry_count=1, base=2.0, jitter=False) == 2
    # retry_count = 2 -> 2 * 2^1 = 4
    assert calculate_backoff(retry_count=2, base=2.0, jitter=False) == 4
    # retry_count = 3 -> 2 * 2^2 = 8
    assert calculate_backoff(retry_count=3, base=2.0, jitter=False) == 8
    # retry_count = 4 -> 2 * 2^3 = 16
    assert calculate_backoff(retry_count=4, base=2.0, jitter=False) == 16


def test_calculate_backoff_max_cap() -> None:
    """Verifies backoff does not exceed max_backoff cap."""
    backoff = calculate_backoff(
        retry_count=10,
        base=2.0,
        max_backoff=30.0,
        jitter=False,
    )
    assert backoff == 30


def test_calculate_backoff_with_jitter() -> None:
    """Verifies backoff with jitter is bounded within expected range."""
    for _ in range(20):
        val = calculate_backoff(
            retry_count=2,
            base=4.0,
            max_backoff=60.0,
            jitter=True,
        )
        # exp_delay is 4 * 2^1 = 8. Full jitter produces value in [4, 8]
        assert 4 <= val <= 8


def test_should_send_to_dlq() -> None:
    """Verifies DLQ trigger threshold evaluation."""
    assert not should_send_to_dlq(retry_count=1, max_retries=3)
    assert not should_send_to_dlq(retry_count=2, max_retries=3)
    assert should_send_to_dlq(retry_count=3, max_retries=3)
    assert should_send_to_dlq(retry_count=4, max_retries=3)


@pytest.mark.asyncio
async def test_forward_to_dlq(mock_sqs_client: SQSClient) -> None:
    """Verifies message is formatted and forwarded to DLQ."""
    msg_id = await forward_to_dlq(
        sqs_client=mock_sqs_client,
        dlq_url="http://sqs/dlq",
        original_body='{"event_type": "booking.confirmed", "payload": {"id": "123"}}',
        error_message="SMTP connection timed out",
        retry_count=3,
        original_message_id="orig-456",
    )

    assert msg_id == "msg-dlq-123"
    mock_sqs_client.publish_event.assert_awaited_once()  # type: ignore[attr-defined]
    call_kwargs = mock_sqs_client.publish_event.await_args.kwargs  # type: ignore[attr-defined]
    assert call_kwargs["queue_url"] == "http://sqs/dlq"
    assert call_kwargs["event_type"] == "event.dead_letter"
    assert call_kwargs["payload"]["original_message_id"] == "orig-456"
    assert call_kwargs["payload"]["error_reason"] == "SMTP connection timed out"
    assert call_kwargs["payload"]["retry_count"] == 3
