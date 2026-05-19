"""Shared Pydantic v2 schemas: pagination, API responses, errors."""

from __future__ import annotations

import math
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# --------------------------------------------------------------------------- #
# Pagination
# --------------------------------------------------------------------------- #

class PaginationParams(BaseModel):
    """Common query parameters for paginated endpoints."""

    page: int = Field(default=1, ge=1, description="1-based page number")
    page_size: int = Field(
        default=20, ge=1, le=100, description="Items per page (max 100)"
    )

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated list response."""

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> PaginatedResponse[T]:
        pages = math.ceil(total / page_size) if page_size > 0 else 0
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)


# --------------------------------------------------------------------------- #
# Generic API envelope
# --------------------------------------------------------------------------- #

class APIResponse(BaseModel, Generic[T]):
    """Standard success response envelope."""

    data: T
    message: str = "Success"


# --------------------------------------------------------------------------- #
# Error response
# --------------------------------------------------------------------------- #

class ErrorResponse(BaseModel):
    """Standard error response body."""

    error: str
    detail: str | list | None = None
    code: str | None = None
