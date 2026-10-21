"""Inventory generation and seat management service."""

from __future__ import annotations

import uuid

from app.models.seat import Seat
from app.repositories.seat_repository import SeatRepository
from app.schemas.inventory import CreateInventoryRequest, CreateInventoryResponse
from app.schemas.seat import SeatListResponse, SeatResponse
from ticketrush_common.errors import ConflictError


class InventoryService:
    """Manages seat allocation and inventory queries."""

    def __init__(self, seat_repo: SeatRepository) -> None:
        self.seat_repo = seat_repo

    async def generate_inventory(
        self,
        event_id: uuid.UUID,
        request: CreateInventoryRequest,
    ) -> CreateInventoryResponse:
        """Batch generates seat grid for an event based on section configuration."""
        existing_count = await self.seat_repo.count_seats_by_event(event_id)
        if existing_count > 0:
            raise ConflictError(
                message=f"Inventory has already been created for event {event_id} ({existing_count} existing seats)",
                code="INVENTORY_ALREADY_EXISTS",
                details={"event_id": str(event_id), "existing_seats": existing_count},
            )

        new_seats: list[Seat] = []
        section_names: list[str] = []

        for section_cfg in request.sections:
            section_names.append(section_cfg.name)
            for r in range(1, section_cfg.rows + 1):
                row_label = str(r)
                for num in range(1, section_cfg.seats_per_row + 1):
                    new_seats.append(
                        Seat(
                            id=uuid.uuid4(),
                            event_id=event_id,
                            section=section_cfg.name,
                            row=row_label,
                            number=num,
                            price_cents=section_cfg.price_cents,
                            status="available",
                            version=1,
                        )
                    )

        await self.seat_repo.bulk_create_seats(new_seats)

        return CreateInventoryResponse(
            event_id=event_id,
            total_seats_created=len(new_seats),
            sections=section_names,
        )

    async def list_event_seats(self, event_id: uuid.UUID) -> SeatListResponse:
        """Retrieves complete seat availability for an event."""
        seats = await self.seat_repo.list_seats_by_event(event_id)
        available_count = sum(1 for s in seats if s.status == "available")

        return SeatListResponse(
            event_id=event_id,
            total=len(seats),
            available_count=available_count,
            seats=[SeatResponse.model_validate(s) for s in seats],
        )
