"""Base configuration module using pydantic-settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseAppConfig(BaseSettings):
    """Base application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    debug: bool = Field(default=False, alias="DEBUG")

    # Database
    postgres_user: str = Field(default="ticketrush", alias="POSTGRES_USER")
    postgres_password: str = Field(default="ticketrush", alias="POSTGRES_PASSWORD")
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="ticketrush", alias="POSTGRES_DB")
    database_url: str = Field(
        default="postgresql+asyncpg://ticketrush:ticketrush@localhost:5432/ticketrush",
        alias="DATABASE_URL",
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # Security & Tokens
    jwt_secret_key: str = Field(
        default="development-insecure-secret-key-change-in-production-min-32-chars",
        alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=15, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    internal_service_secret: str = Field(
        default="development-internal-service-shared-secret-key",
        alias="INTERNAL_SERVICE_SECRET",
    )

    # Metrics
    metrics_enabled: bool = Field(default=True, alias="METRICS_ENABLED")
