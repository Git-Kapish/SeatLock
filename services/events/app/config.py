"""Events service configuration."""

from pydantic import Field

from ticketrush_common.config import BaseAppConfig


class EventsConfig(BaseAppConfig):
    """Configuration specific to the Events service."""

    service_name: str = Field(default="events-service", alias="SERVICE_NAME")
    http_port: int = Field(default=8002, alias="EVENTS_HTTP_PORT")
    event_cache_ttl_seconds: int = Field(default=300, alias="EVENT_CACHE_TTL_SECONDS")


config = EventsConfig()
