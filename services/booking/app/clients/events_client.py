"""HTTP client for inter-service communication with the Events service."""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from app.config import config
from ticketrush_common.errors import AppError, ConflictError, NotFoundError


class EventsClient:
    """Async client verifying event metadata and status against the Events service."""

    def __init__(self, base_url: str | None = None, internal_secret: str | None = None) -> None:
        self.base_url = (base_url or config.events_service_url).rstrip("/")
        self.internal_secret = internal_secret or config.internal_service_secret

    async def verify_event_on_sale(self, event_id: uuid.UUID) -> dict[str, Any]:
        """Calls the Events service internal endpoint to confirm event is active and on_sale.

        Raises:
            NotFoundError: If the event does not exist.
            ConflictError: If the event status is not 'on_sale'.
            InternalError: If the Events service is unreachable or errors.
        """
        url = f"{self.base_url}/api/v1/internal/events/{event_id}"
        headers = {"X-Internal-Secret": self.internal_secret}

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(url, headers=headers)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise AppError(
                message=f"Unable to contact Events service: {exc}",
                code="EVENTS_SERVICE_UNAVAILABLE",
                status_code=503,
            ) from exc

        if response.status_code == 404:
            raise NotFoundError(
                message=f"Event {event_id} was not found",
                code="EVENT_NOT_FOUND",
            )

        if response.status_code != 200:
            raise AppError(
                message=f"Events service returned unexpected status: {response.status_code}",
                code="EVENTS_SERVICE_ERROR",
                status_code=502,
            )

        data: dict[str, Any] = response.json()
        event_status = data.get("status")

        if event_status != "on_sale":
            raise ConflictError(
                message=f"Event is not currently on sale (status: '{event_status}')",
                code="EVENT_NOT_ON_SALE",
                details={"event_id": str(event_id), "status": event_status},
            )

        return data
