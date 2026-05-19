"""WorkOrder repository — tenant-scoped CRUD + domain-specific queries."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.models.work_order import WorkOrder, WorkOrderStatus
from app.repositories.base import BaseRepository

logger = structlog.get_logger(__name__)


class WorkOrderRepository(BaseRepository[WorkOrder]):
    """
    Extends BaseRepository with work-order-specific query methods.

    All queries are automatically scoped to the supplied tenant_id and
    exclude soft-deleted rows via the inherited _base_filter helper.
    """

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(WorkOrder, db)

    # ---------------------------------------------------------------------- #
    # Eager-loaded single record
    # ---------------------------------------------------------------------- #

    async def get_with_relations(
        self,
        tenant_id: UUID,
        id: UUID,
    ) -> WorkOrder | None:
        """
        Fetch a work order with tasks, attachments, check_ins, and crew
        eagerly loaded in a single query round-trip.

        Returns None if not found or if it belongs to a different tenant.
        """
        result = await self.db.execute(
            select(WorkOrder)
            .where(
                and_(
                    WorkOrder.id == id,
                    WorkOrder.tenant_id == tenant_id,
                    WorkOrder.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(WorkOrder.tasks),
                selectinload(WorkOrder.attachments),
                selectinload(WorkOrder.check_ins),
                selectinload(WorkOrder.crew),
            )
        )
        return result.scalar_one_or_none()

    # ---------------------------------------------------------------------- #
    # Filtered lists
    # ---------------------------------------------------------------------- #

    async def list_by_status(
        self,
        tenant_id: UUID,
        status: str | WorkOrderStatus,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[WorkOrder], int]:
        """
        Return a paginated list of work orders filtered by status.

        Args:
            tenant_id: Tenant scope.
            status:    WorkOrderStatus value or equivalent string.
            skip:      Offset for pagination.
            limit:     Max records to return.

        Returns:
            (work_orders, total_count) tuple.
        """
        status_value = status.value if isinstance(status, WorkOrderStatus) else status

        base = self._base_filter(tenant_id)
        combined = and_(*base, WorkOrder.status == status_value)

        count_result = await self.db.execute(
            select(func.count()).select_from(WorkOrder).where(combined)
        )
        total: int = count_result.scalar_one()

        result = await self.db.execute(
            select(WorkOrder)
            .where(combined)
            .order_by(WorkOrder.scheduled_date.asc().nulls_last(), WorkOrder.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        work_orders = list(result.scalars().all())

        logger.debug(
            "work_order_list_by_status",
            tenant_id=str(tenant_id),
            status=status_value,
            total=total,
        )
        return work_orders, total

    async def list_by_crew(
        self,
        tenant_id: UUID,
        crew_id: UUID,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[WorkOrder]:
        """
        Return work orders assigned to a crew, optionally bounded by a date range.

        Both date_from and date_to are compared against scheduled_date.
        If neither is supplied, all (non-deleted) work orders for the crew are returned.

        Args:
            tenant_id:  Tenant scope.
            crew_id:    Filter to this crew.
            date_from:  Inclusive lower bound on scheduled_date (timezone-aware).
            date_to:    Inclusive upper bound on scheduled_date (timezone-aware).

        Returns:
            List of WorkOrder instances ordered by scheduled_date ascending.
        """
        filters = [
            *self._base_filter(tenant_id),
            WorkOrder.crew_id == crew_id,
        ]
        if date_from is not None:
            filters.append(WorkOrder.scheduled_date >= date_from)
        if date_to is not None:
            filters.append(WorkOrder.scheduled_date <= date_to)

        result = await self.db.execute(
            select(WorkOrder)
            .where(and_(*filters))
            .order_by(WorkOrder.scheduled_date.asc().nulls_last())
        )
        return list(result.scalars().all())

    async def list_by_location(
        self,
        tenant_id: UUID,
        location_id: UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[WorkOrder], int]:
        """
        Return the service history for a location (all non-deleted work orders).

        Args:
            tenant_id:   Tenant scope.
            location_id: Location filter.
            skip:        Offset for pagination.
            limit:       Max records to return.

        Returns:
            (work_orders, total_count) tuple ordered by scheduled_date descending.
        """
        base = self._base_filter(tenant_id)
        combined = and_(*base, WorkOrder.location_id == location_id)

        count_result = await self.db.execute(
            select(func.count()).select_from(WorkOrder).where(combined)
        )
        total: int = count_result.scalar_one()

        result = await self.db.execute(
            select(WorkOrder)
            .where(combined)
            .order_by(WorkOrder.scheduled_date.desc().nulls_last())
            .offset(skip)
            .limit(limit)
        )
        work_orders = list(result.scalars().all())

        return work_orders, total

    # ---------------------------------------------------------------------- #
    # Dashboard aggregation
    # ---------------------------------------------------------------------- #

    async def count_by_status(self, tenant_id: UUID) -> dict[str, int]:
        """
        Return a count of non-deleted work orders grouped by status.

        Useful for dashboard widgets. All known WorkOrderStatus values are
        included in the result — statuses with zero work orders are set to 0.

        Returns:
            Mapping of status string → count, e.g.
            {"draft": 3, "scheduled": 12, "in_progress": 5, ...}
        """
        base = self._base_filter(tenant_id)

        result = await self.db.execute(
            select(WorkOrder.status, func.count().label("cnt"))
            .where(and_(*base))
            .group_by(WorkOrder.status)
        )
        rows = result.all()

        # Seed with zeros so callers always get every status key.
        counts: dict[str, int] = {s.value: 0 for s in WorkOrderStatus}
        for row in rows:
            status_key = row.status.value if hasattr(row.status, "value") else str(row.status)
            counts[status_key] = row.cnt

        logger.debug(
            "work_order_count_by_status",
            tenant_id=str(tenant_id),
            counts=counts,
        )
        return counts
