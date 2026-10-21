"""Async AWS / LocalStack SQS messaging publisher helper using aioboto3."""

from datetime import UTC, datetime
from typing import Any

import aioboto3
from pydantic import BaseModel, Field

from ticketrush_common.logging import get_logger

logger = get_logger("ticketrush.sqs")


class EventEnvelope(BaseModel):
    """Standardized event envelope published to SQS."""

    event_type: str = Field(..., description="Domain event name, e.g. booking.confirmed")
    occurred_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO 8601 UTC timestamp",
    )
    payload: dict[str, Any] = Field(..., description="Event payload data")


class SQSClient:
    """Async SQS client manager for publishing and receiving domain events."""

    def __init__(
        self,
        region_name: str = "us-east-1",
        endpoint_url: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
    ) -> None:
        self.session = aioboto3.Session()
        self.region_name = region_name
        self.endpoint_url = endpoint_url
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key

    async def publish_event(
        self,
        queue_url: str,
        event_type: str,
        payload: dict[str, Any],
        message_group_id: str | None = None,
        deduplication_id: str | None = None,
    ) -> str:
        """Publishes an event envelope to an SQS queue."""
        envelope = EventEnvelope(event_type=event_type, payload=payload)
        body = envelope.model_dump_json()

        kwargs: dict[str, Any] = {
            "QueueUrl": queue_url,
            "MessageBody": body,
        }
        if message_group_id:
            kwargs["MessageGroupId"] = message_group_id
        if deduplication_id:
            kwargs["MessageDeduplicationId"] = deduplication_id

        async with self.session.client(
            "sqs",
            region_name=self.region_name,
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
        ) as client:
            response = await client.send_message(**kwargs)
            message_id: str = response.get("MessageId", "")
            logger.info(
                "sqs_message_published",
                event_type=event_type,
                message_id=message_id,
                queue_url=queue_url,
            )
            return message_id

    async def receive_messages(
        self,
        queue_url: str,
        max_number_of_messages: int = 10,
        wait_time_seconds: int = 20,
        visibility_timeout: int | None = None,
    ) -> list[dict[str, Any]]:
        """Receives a batch of messages from an SQS queue via long polling."""
        kwargs: dict[str, Any] = {
            "QueueUrl": queue_url,
            "MaxNumberOfMessages": max(1, min(max_number_of_messages, 10)),
            "WaitTimeSeconds": max(0, min(wait_time_seconds, 20)),
            "AttributeNames": ["All"],
            "MessageAttributeNames": ["All"],
        }
        if visibility_timeout is not None:
            kwargs["VisibilityTimeout"] = visibility_timeout

        async with self.session.client(
            "sqs",
            region_name=self.region_name,
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
        ) as client:
            response = await client.receive_message(**kwargs)
            messages: list[dict[str, Any]] = response.get("Messages", [])
            return messages

    async def delete_message(self, queue_url: str, receipt_handle: str) -> None:
        """Deletes a successfully processed message from the SQS queue."""
        async with self.session.client(
            "sqs",
            region_name=self.region_name,
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
        ) as client:
            await client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle,
            )

    async def change_message_visibility(
        self,
        queue_url: str,
        receipt_handle: str,
        visibility_timeout: int,
    ) -> None:
        """Modifies the visibility timeout of a message for backoff retry."""
        async with self.session.client(
            "sqs",
            region_name=self.region_name,
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
        ) as client:
            await client.change_message_visibility(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle,
                VisibilityTimeout=visibility_timeout,
            )

    async def create_queue_if_not_exists(
        self,
        queue_name: str,
        attributes: dict[str, str] | None = None,
    ) -> str:
        """Ensures an SQS queue exists, creating it if necessary (helpful for local/test envs)."""
        async with self.session.client(
            "sqs",
            region_name=self.region_name,
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
        ) as client:
            try:
                response = await client.get_queue_url(QueueName=queue_name)
                queue_url: str = response["QueueUrl"]
                return queue_url
            except Exception:
                create_kwargs: dict[str, Any] = {"QueueName": queue_name}
                if attributes:
                    create_kwargs["Attributes"] = attributes
                res = await client.create_queue(**create_kwargs)
                created_url: str = res["QueueUrl"]
                return created_url
