"""Retry logic with exponential backoff, jitter, and Dead-Letter Queue (DLQ) routing."""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime
from typing import Any

from ticketrush_common.logging import get_logger
from ticketrush_common.sqs import SQSClient

logger = get_logger("ticketrush.worker.retry")


def calculate_backoff(
    retry_count: int,
    base: float = 2.0,
    max_backoff: float = 60.0,
    jitter: bool = True,
) -> int:
    """Calculates exponential backoff in integer seconds with full jitter.

    Formula: min(max_backoff, base * (2 ** (retry_count - 1)))
    With full jitter: uniform random in [0.5 * exp_delay, exp_delay].
    """
    exponent = max(0, retry_count - 1)
    exp_delay = min(max_backoff, base * (2**exponent))

    delay = random.uniform(exp_delay * 0.5, exp_delay) if jitter else exp_delay
    return max(1, round(delay))


def should_send_to_dlq(retry_count: int, max_retries: int = 3) -> bool:
    """Determines if the message has exceeded maximum processing attempts."""
    return retry_count >= max_retries


async def forward_to_dlq(
    sqs_client: SQSClient,
    dlq_url: str,
    original_body: str,
    error_message: str,
    retry_count: int,
    original_message_id: str | None = None,
) -> str:
    """Publishes a failed message to the Dead-Letter Queue with diagnosis metadata."""
    parsed_payload: Any
    try:
        parsed_payload = json.loads(original_body)
    except Exception:
        parsed_payload = {"raw_content": original_body}

    dlq_payload = {
        "original_message_id": original_message_id,
        "failed_at": datetime.now(UTC).isoformat(),
        "retry_count": retry_count,
        "error_reason": error_message,
        "original_message": parsed_payload,
    }

    message_id = await sqs_client.publish_event(
        queue_url=dlq_url,
        event_type="event.dead_letter",
        payload=dlq_payload,
    )

    logger.warning(
        "message_routed_to_dlq",
        dlq_url=dlq_url,
        original_message_id=original_message_id,
        dlq_message_id=message_id,
        retry_count=retry_count,
        error=error_message,
    )
    return message_id
