"""Configuration settings for the Notifier worker daemon."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerConfig(BaseSettings):
    """Runtime configuration for SQS consumer and hold sweeper."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"

    # Database & Redis (Booking schema)
    database_url: str = "postgresql+asyncpg://ticketrush:ticketrush@localhost:5432/ticketrush"
    redis_url: str = "redis://localhost:6379/0"

    # LocalStack / AWS SQS
    sqs_endpoint_url: str = "http://localhost:4566"
    sqs_queue_url: str = "http://localhost:4566/000000000000/ticketrush-booking-events"
    sqs_dlq_url: str = "http://localhost:4566/000000000000/ticketrush-booking-events-dlq"
    aws_region: str = "us-east-1"
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"

    # MailHog / SMTP
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_sender: str = "tickets@ticketrush.internal"

    # Sweeper & Retries
    sweeper_interval_seconds: int = 30
    max_retries: int = 3
    base_backoff_seconds: float = 2.0
    max_backoff_seconds: float = 60.0


config = WorkerConfig()
