"""
Generic async repository with tenant isolation.

Provides standard CRUD operations that are automatically scoped
to a specific tenant and exclude soft-deleted records.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.base import TenantAwareModel

logger = structlog.get_logger(__name__)

# Bound to TenantAwareModel so attribute accesses (tenant_id, deleted_at,
# id, created_at) type-check inside the generic repository.
T = TypeVar("T", bound=TenantAwareModel)


class BaseRepository(Generic[T]):
    """
    Generic async CRUD repository.

    All public methods automatically scope queries to the provided tenant_id
    and filter out soft-deleted records (where deleted_at IS NOT NULL).

    Usage::

        repo = BaseRepository(WorkOrder, db)
        work_order = await repo.get(some_uuid, tenant_id)
        work_orders, total = await repo.get_multi(tenant_id, skip=0, limit=20)
    """

    def __init__(self, model: type[T], db: AsyncSession) -> None:
        self.model = model
        self.db = db

    def _base_filter(self, tenant_id: UUID) -> list:
        """Return the base filter clauses applied to every query."""
        filters = [self.model.tenant_id == tenant_id]
        if hasattr(self.model, "deleted_at"):
            filters.append(self.model.deleted_at.is_(None))
        return filters

    # ---------------------------------------------------------------------- #
    # Read
    # ---------------------------------------------------------------------- #

    async def get(self, id: UUID, tenant_id: UUID) -> T | None:
        """Fetch a single record by primary key within a tenant."""
        result = await self.db.execute(
            select(self.model).where(
                and_(self.model.id == id, *self._base_filter(tenant_id))
            )
        )
        return result.scalar_one_or_none()

    async def get_or_404(self, id: UUID, tenant_id: UUID) -> T:
        """Like get(), but raises HTTP 404 if not found."""
        obj = await self.get(id, tenant_id)
        if obj is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.model.__name__} not found",
            )
        return obj

    async def get_multi(
        self,
        tenant_id: UUID,
        skip: int = 0,
        limit: int = 20,
        filters: list | None = None,
        order_by: Any = None,
    ) -> tuple[list[T], int]:
        """
        Return a page of records plus the total count.

        Args:
            tenant_id: Scopes the query to this tenant.
            skip: Number of records to skip (for offset pagination).
            limit: Maximum records to return.
            filters: Extra SQLAlchemy filter expressions (ANDed with base filters).
            order_by: SQLAlchemy order_by expression.

        Returns:
            (items, total) tuple.
        """
        base = self._base_filter(tenant_id)
        if filters:
            base.extend(filters)

        combined = and_(*base)

        count_result = await self.db.execute(
            select(func.count()).select_from(self.model).where(combined)
        )
        total = count_result.scalar_one()

        q = select(self.model).where(combined).offset(skip).limit(limit)
        if order_by is not None:
            q = q.order_by(order_by)
        else:
            if hasattr(self.model, "created_at"):
                q = q.order_by(self.model.created_at.desc())

        result = await self.db.execute(q)
        items = list(result.scalars().all())

        return items, total

    # ---------------------------------------------------------------------- #
    # Create
    # ---------------------------------------------------------------------- #

    async def create(self, obj_in: dict[str, Any], tenant_id: UUID) -> T:
        """
        Create a new record.

        obj_in must not include tenant_id; it is injected automatically.
        """
        import uuid as _uuid

        data = {**obj_in, "tenant_id": tenant_id}
        if "id" not in data:
            data["id"] = _uuid.uuid4()

        obj = self.model(**data)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)

        logger.debug(
            "repository_created",
            model=self.model.__name__,
            id=str(data["id"]),
            tenant_id=str(tenant_id),
        )
        return obj

    # ---------------------------------------------------------------------- #
    # Update
    # ---------------------------------------------------------------------- #

    async def update(
        self,
        id: UUID,
        tenant_id: UUID,
        obj_in: dict[str, Any],
    ) -> T:
        """
        Patch a record with the provided fields.

        Raises HTTP 404 if the record is not found.
        """
        obj = await self.get_or_404(id, tenant_id)
        for field, value in obj_in.items():
            setattr(obj, field, value)
        await self.db.flush()
        await self.db.refresh(obj)

        logger.debug(
            "repository_updated",
            model=self.model.__name__,
            id=str(id),
            fields=list(obj_in.keys()),
        )
        return obj

    # ---------------------------------------------------------------------- #
    # Soft delete
    # ---------------------------------------------------------------------- #

    async def soft_delete(self, id: UUID, tenant_id: UUID) -> bool:
        """
        Mark a record as deleted by setting deleted_at to now().

        Returns True if deleted, False if not found.
        Raises 400 if the model does not support soft delete.
        """
        if not hasattr(self.model, "deleted_at"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{self.model.__name__} does not support soft delete",
            )

        obj = await self.get(id, tenant_id)
        if obj is None:
            return False

        obj.deleted_at = datetime.now(tz=UTC)
        await self.db.flush()

        logger.info(
            "repository_soft_deleted",
            model=self.model.__name__,
            id=str(id),
            tenant_id=str(tenant_id),
        )
        return True

    # ---------------------------------------------------------------------- #
    # Existence check
    # ---------------------------------------------------------------------- #

    async def exists(self, tenant_id: UUID, **filter_kwargs: Any) -> bool:
        """
        Check if any record matches the given filters within the tenant.

        Usage::
            exists = await repo.exists(tenant_id, email="foo@bar.com")
        """
        filters = self._base_filter(tenant_id)
        for field, value in filter_kwargs.items():
            filters.append(getattr(self.model, field) == value)

        result = await self.db.execute(
            select(func.count()).select_from(self.model).where(and_(*filters))
        )
        return (result.scalar_one() or 0) > 0
