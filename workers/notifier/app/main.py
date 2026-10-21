"""Entry point for the TicketRush Notifier Worker daemon."""

from __future__ import annotations

import asyncio
import contextlib
import signal
from typing import Any

import redis.asyncio as aioredis

from app.config import config
from app.consumer import SQSConsumer
from app.handlers.booking_confirmed import BookingConfirmedHandler
from app.sweeper import HoldSweeper
from ticketrush_common.logging import get_logger, setup_logging
from ticketrush_common.sqs import SQSClient

setup_logging(service_name="notifier-worker", log_level=config.log_level)
logger = get_logger("ticketrush.worker.main")


async def main() -> None:
    """Initializes clients and runs the SQS consumer and hold sweeper tasks."""
    logger.info(
        "worker_starting",
        environment=config.environment,
        queue_url=config.sqs_queue_url,
    )

    stop_event = asyncio.Event()

    # Graceful shutdown handler
    def handle_stop_signal(*_: Any) -> None:
        logger.info("shutdown_signal_received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, handle_stop_signal)
    except NotImplementedError:
        # Windows proactor event loop does not support add_signal_handler
        pass

    redis_client = aioredis.from_url(
        config.redis_url,
        decode_responses=True,
    )

    sqs_client = SQSClient(
        region_name=config.aws_region,
        endpoint_url=config.sqs_endpoint_url,
        aws_access_key_id=config.aws_access_key_id,
        aws_secret_access_key=config.aws_secret_access_key,
    )

    # In local development, ensure SQS queues exist
    try:
        await sqs_client.create_queue_if_not_exists("ticketrush-booking-events")
        await sqs_client.create_queue_if_not_exists("ticketrush-booking-events-dlq")
    except Exception as exc:
        logger.warning("queue_initialization_skipped_or_failed", error=str(exc))

    booking_confirmed_handler = BookingConfirmedHandler()
    consumer = SQSConsumer(
        sqs_client=sqs_client,
        booking_confirmed_handler=booking_confirmed_handler,
    )
    sweeper = HoldSweeper(redis_client=redis_client)

    logger.info("worker_tasks_launching")
    try:
        await asyncio.gather(
            consumer.run(stop_event),
            sweeper.run(stop_event),
        )
    except (KeyboardInterrupt, SystemExit):
        logger.info("worker_interrupted")
        stop_event.set()
    finally:
        logger.info("worker_cleaning_up")
        await redis_client.aclose()
        logger.info("worker_shutdown_complete")


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt, SystemExit):
        asyncio.run(main())
