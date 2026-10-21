"""Async SQS consumer daemon for domain events."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.config import config
from app.handlers.booking_confirmed import BookingConfirmedHandler
from app.retry import calculate_backoff, forward_to_dlq, should_send_to_dlq
from ticketrush_common.logging import get_logger
from ticketrush_common.sqs import SQSClient

logger = get_logger("ticketrush.worker.consumer")


class SQSConsumer:
    """Long-polling SQS message consumer with retry backoff and DLQ routing."""

    def __init__(
        self,
        sqs_client: SQSClient,
        booking_confirmed_handler: BookingConfirmedHandler,
        queue_url: str | None = None,
        dlq_url: str | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.sqs_client = sqs_client
        self.booking_confirmed_handler = booking_confirmed_handler
        self.queue_url = queue_url or config.sqs_queue_url
        self.dlq_url = dlq_url or config.sqs_dlq_url
        self.max_retries = max_retries or config.max_retries

    async def process_single_message(self, message: dict[str, Any]) -> None:
        """Processes one SQS message with error handling and retry / DLQ logic."""
        message_id = message.get("MessageId", "unknown")
        receipt_handle = message.get("ReceiptHandle", "")
        raw_body = message.get("Body", "{}")

        # Extract receive count from SQS message attributes
        attrs = message.get("Attributes", {})
        try:
            receive_count = int(attrs.get("ApproximateReceiveCount", 1))
        except (ValueError, TypeError):
            receive_count = 1

        try:
            data = json.loads(raw_body)
            event_type = data.get("event_type")
            payload = data.get("payload", {})

            if event_type == "booking.confirmed":
                await self.booking_confirmed_handler.handle(payload)
            else:
                logger.warning(
                    "unrecognized_event_type_skipped",
                    event_type=event_type,
                    message_id=message_id,
                )

            # Successfully processed -> delete from queue
            await self.sqs_client.delete_message(self.queue_url, receipt_handle)
            logger.info("message_processed_and_deleted", message_id=message_id)

        except Exception as exc:
            logger.error(
                "message_processing_failed",
                message_id=message_id,
                receive_count=receive_count,
                error=str(exc),
            )

            if should_send_to_dlq(receive_count, max_retries=self.max_retries):
                # Route to dead letter queue and purge from primary queue
                await forward_to_dlq(
                    sqs_client=self.sqs_client,
                    dlq_url=self.dlq_url,
                    original_body=raw_body,
                    error_message=str(exc),
                    retry_count=receive_count,
                    original_message_id=message_id,
                )
                await self.sqs_client.delete_message(self.queue_url, receipt_handle)
            else:
                # Apply exponential backoff with jitter via visibility timeout
                backoff_seconds = calculate_backoff(
                    retry_count=receive_count,
                    base=config.base_backoff_seconds,
                    max_backoff=config.max_backoff_seconds,
                )
                await self.sqs_client.change_message_visibility(
                    queue_url=self.queue_url,
                    receipt_handle=receipt_handle,
                    visibility_timeout=backoff_seconds,
                )
                logger.info(
                    "message_visibility_adjusted_for_retry",
                    message_id=message_id,
                    backoff_seconds=backoff_seconds,
                )

    async def run(self, stop_event: asyncio.Event) -> None:
        """Continuous long-polling consumption loop."""
        logger.info(
            "sqs_consumer_started",
            queue_url=self.queue_url,
            dlq_url=self.dlq_url,
        )

        while not stop_event.is_set():
            try:
                messages = await self.sqs_client.receive_messages(
                    queue_url=self.queue_url,
                    max_number_of_messages=10,
                    wait_time_seconds=10,
                )

                if messages:
                    # Process current batch concurrently
                    tasks = [self.process_single_message(msg) for msg in messages]
                    await asyncio.gather(*tasks, return_exceptions=True)
                else:
                    await asyncio.sleep(0.01)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("sqs_polling_error", error=str(exc))
                await asyncio.sleep(2)

        logger.info("sqs_consumer_stopped")
