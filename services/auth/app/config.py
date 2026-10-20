"""Auth service configuration."""

from pydantic import Field

from ticketrush_common.config import BaseAppConfig


class AuthConfig(BaseAppConfig):
    """Configuration specific to the Auth service."""

    service_name: str = Field(default="auth-service", alias="SERVICE_NAME")
    http_port: int = Field(default=8001, alias="AUTH_HTTP_PORT")
    login_rate_limit_max: int = Field(default=5, alias="LOGIN_RATE_LIMIT_MAX")
    login_rate_limit_window_seconds: int = Field(
        default=60, alias="LOGIN_RATE_LIMIT_WINDOW_SECONDS"
    )


config = AuthConfig()
