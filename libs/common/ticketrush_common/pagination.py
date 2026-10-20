"""Generic pagination request parameters and response models."""

from math import ceil

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """Query parameters for offset-based pagination."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page (max 100)")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class PaginatedResponse[T](BaseModel):
    """Standard generic wrapper for paginated collections."""

    items: list[T]
    total: int = Field(..., ge=0, description="Total count of matching items")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total pages available")

    @classmethod
    def create(cls, items: list[T], total: int, params: PaginationParams) -> "PaginatedResponse[T]":
        total_pages = ceil(total / params.page_size) if total > 0 else 0
        return cls(
            items=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=total_pages,
        )
