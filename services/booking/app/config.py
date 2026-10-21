"""Booking service configuration."""

from pydantic import Field

from ticketrush_common.config import BaseAppConfig


class BookingConfig(BaseAppConfig):
    """Configuration specific to the Booking service."""

    service_name: str = Field(default="booking-service", alias="SERVICE_NAME")
    http_port: int = Field(default=8003, alias="BOOKING_HTTP_PORT")

    # Hold configuration
    hold_ttl_seconds: int = Field(default=600, alias="HOLD_TTL_SECONDS")  # 10 minutes
    max_seats_per_hold: int = Field(default=6, alias="MAX_SEATS_PER_HOLD")
    max_active_holds_per_user: int = Field(default=3, alias="MAX_ACTIVE_HOLDS_PER_USER")

    # Inter-service URLs
    events_service_url: str = Field(
        default="http://localhost:8002",
        alias="EVENTS_SERVICE_URL",
    )

    # Payments & Webhooks
    payment_webhook_secret: str = Field(
        default="development-payment-webhook-secret-min-32-chars",
        alias="PAYMENT_WEBHOOK_SECRET",
    )

    # SQS Messaging
    sqs_endpoint_url: str | None = Field(
        default="http://localhost:4566",
        alias="SQS_ENDPOINT_URL",
    )
    sqs_queue_url: str = Field(
        default="http://localhost:4566/000000000000/ticketrush-booking-events",
        alias="SQS_QUEUE_URL",
    )
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    aws_access_key_id: str | None = Field(default="test", alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(default="test", alias="AWS_SECRET_ACCESS_KEY")


config = BookingConfig()
