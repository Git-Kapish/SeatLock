"""Event catalog business service managing lifecycle, search, and caching."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from redis.asyncio.client import Redis

from app.cache import EventCache
from app.repositories.event_repository import EventRepository
from app.schemas.event import (
    CreateEventRequest,
    EventFilterParams,
    EventResponse,
    UpdateEventRequest,
)
from ticketrush_common.errors import ConflictError, NotFoundError, ValidationError
from ticketrush_common.pagination import PaginatedResponse, PaginationParams

VALID_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"published", "cancelled"},
    "published": {"on_sale", "cancelled"},
    "on_sale": {"sold_out", "completed", "cancelled"},
    "sold_out": {"on_sale", "completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


class EventService:
    """Core domain service for events catalog management."""

    def __init__(self, event_repo: EventRepository, redis_client: Redis) -> None:
        self.event_repo = event_repo
        self.cache = EventCache(redis_client)

    @staticmethod
    def _compute_listing_hash(filters: EventFilterParams, pagination: PaginationParams) -> str:
        data = {
            "filters": filters.model_dump(mode="json"),
            "pagination": pagination.model_dump(mode="json"),
        }
        encoded = json.dumps(data, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    async def get_event(self, event_id: uuid.UUID) -> EventResponse:
        """Retrieves single event details with Redis cache-aside."""
        cached_data = await self.cache.get_event(str(event_id))
        if cached_data:
            return EventResponse.model_validate(cached_data)

        event = await self.event_repo.get_by_id(event_id)
        if not event:
            raise NotFoundError(message="Event not found", code="EVENT_NOT_FOUND")

        response = EventResponse.model_validate(event)
        await self.cache.set_event(str(event_id), response.model_dump(mode="json"))
        return response

    async def list_events(
        self,
        filters: EventFilterParams,
        pagination: PaginationParams,
    ) -> PaginatedResponse[EventResponse]:
        """Lists events with search, filtering, and caching."""
        cache_key = self._compute_listing_hash(filters, pagination)
        cached = await self.cache.get_listing(cache_key)
        if cached:
            return PaginatedResponse[EventResponse].model_validate(cached)

        items, total = await self.event_repo.list_events(filters, pagination)
        event_responses = [EventResponse.model_validate(item) for item in items]
        result = PaginatedResponse.create(items=event_responses, total=total, params=pagination)

        await self.cache.set_listing(cache_key, result.model_dump(mode="json"))
        return result

    async def create_event(self, data: CreateEventRequest) -> EventResponse:
        """Creates and stores a new event."""
        event = await self.event_repo.create_event(data)
        response = EventResponse.model_validate(event)
        await self.cache.invalidate_event(str(event.id))
        return response

    async def update_event(self, event_id: uuid.UUID, data: UpdateEventRequest) -> EventResponse:
        """Updates event attributes and validates status lifecycle transitions."""
        event = await self.event_repo.get_by_id(event_id)
        if not event:
            raise NotFoundError(message="Event not found", code="EVENT_NOT_FOUND")

        updates: dict[str, Any] = data.model_dump(exclude_unset=True)

        if "status" in updates and updates["status"] != event.status:
            current_status = event.status
            target_status = updates["status"]
            allowed_transitions = VALID_STATUS_TRANSITIONS.get(current_status, set())
            if target_status not in allowed_transitions:
                raise ValidationError(
                    message=f"Invalid event status transition from '{current_status}' to '{target_status}'",
                    code="INVALID_STATUS_TRANSITION",
                    details={
                        "current_status": current_status,
                        "target_status": target_status,
                        "allowed_transitions": list(allowed_transitions),
                    },
                )

        updated_event = await self.event_repo.update_event(event, updates)
        response = EventResponse.model_validate(updated_event)
        await self.cache.invalidate_event(str(event_id))
        return response

    async def delete_event(self, event_id: uuid.UUID) -> None:
        """Soft deletes an event."""
        event = await self.event_repo.get_by_id(event_id)
        if not event:
            raise NotFoundError(message="Event not found", code="EVENT_NOT_FOUND")

        await self.event_repo.soft_delete(event)
        await self.cache.invalidate_event(str(event_id))

    async def validate_event_for_booking(self, event_id: uuid.UUID) -> EventResponse:
        """Internal validation for booking-service to confirm event exists and is on_sale."""
        event = await self.event_repo.get_by_id(event_id)
        if not event:
            raise NotFoundError(message="Event not found", code="EVENT_NOT_FOUND")

        if event.status != "on_sale":
            raise ConflictError(
                message=f"Event is not available for booking (status: '{event.status}')",
                code="EVENT_NOT_ON_SALE",
                details={"event_id": str(event_id), "status": event.status},
            )

        return EventResponse.model_validate(event)
