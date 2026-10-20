"""Data access repository for events catalog in events schema."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.schemas.event import CreateEventRequest, EventFilterParams
from ticketrush_common.pagination import PaginationParams


class EventRepository:
    """Encapsulates all database queries on the events schema."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, event_id: uuid.UUID, include_deleted: bool = False) -> Event | None:
        """Finds an event by UUID, filtering soft-deleted events by default."""
        stmt = select(Event).where(Event.id == event_id)
        if not include_deleted:
            stmt = stmt.where(Event.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_events(
        self,
        filters: EventFilterParams,
        pagination: PaginationParams,
    ) -> tuple[list[Event], int]:
        """Lists events matching filter criteria with pagination."""
        base_query = select(Event).where(Event.deleted_at.is_(None))

        if filters.status:
            base_query = base_query.where(Event.status == filters.status)
        if filters.city:
            base_query = base_query.where(func.lower(Event.city) == filters.city.lower())
        if filters.category:
            base_query = base_query.where(func.lower(Event.category) == filters.category.lower())
        if filters.start_date:
            base_query = base_query.where(Event.starts_at >= filters.start_date)
        if filters.end_date:
            base_query = base_query.where(Event.starts_at <= filters.end_date)
        if filters.q:
            search_term = f"%{filters.q.strip().lower()}%"
            base_query = base_query.where(
                or_(
                    func.lower(Event.title).like(search_term),
                    func.lower(Event.description).like(search_term),
                )
            )

        # Count total matching items
        count_stmt = select(func.count()).select_from(base_query.subquery())
        total_res = await self.session.execute(count_stmt)
        total: int = total_res.scalar_one() or 0

        # Fetch paginated slice ordered by starts_at
        paged_stmt = (
            base_query.order_by(Event.starts_at.asc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        items_res = await self.session.execute(paged_stmt)
        items = list(items_res.scalars().all())

        return items, total

    async def create_event(self, data: CreateEventRequest) -> Event:
        """Persists a new event record."""
        event = Event(
            id=uuid.uuid4(),
            title=data.title,
            description=data.description,
            venue=data.venue,
            city=data.city,
            category=data.category,
            starts_at=data.starts_at,
            status=data.status,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def update_event(self, event: Event, updates: dict[str, Any]) -> Event:
        """Updates attributes of an existing event."""
        for field, value in updates.items():
            if value is not None and hasattr(event, field):
                setattr(event, field, value)
        await self.session.flush()
        return event

    async def soft_delete(self, event: Event) -> None:
        """Sets deleted_at timestamp on the event."""
        event.deleted_at = datetime.now(UTC)
        await self.session.flush()
