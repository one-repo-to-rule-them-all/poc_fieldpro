"""Client repository — tenant-scoped CRUD + domain-specific queries."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.client import Client
from app.models.location import Location
from app.repositories.base import BaseRepository

logger = structlog.get_logger(__name__)


class ClientRepository(BaseRepository[Client]):
    """
    Extends BaseRepository with client-specific query methods.

    All queries are automatically scoped to the supplied tenant_id and
    exclude soft-deleted rows via the inherited _base_filter helper.
    """

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Client, db)

    # ---------------------------------------------------------------------- #
    # Search
    # ---------------------------------------------------------------------- #

    async def search(
        self,
        tenant_id: UUID,
        query: str,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Client], int]:
        """
        Full-text ilike search over client name and billing_email.

        Args:
            tenant_id: Tenant scope.
            query:     Search string — matched with ILIKE on both columns.
            skip:      Offset for pagination.
            limit:     Max records to return.

        Returns:
            (clients, total_count) tuple.
        """
        pattern = f"%{query}%"
        search_filter = or_(
            Client.name.ilike(pattern),
            Client.billing_email.ilike(pattern),
        )

        base = self._base_filter(tenant_id)
        combined = and_(*base, search_filter)

        count_result = await self.db.execute(
            select(func.count()).select_from(Client).where(combined)
        )
        total: int = count_result.scalar_one()

        result = await self.db.execute(
            select(Client)
            .where(combined)
            .order_by(Client.name.asc())
            .offset(skip)
            .limit(limit)
        )
        clients = list(result.scalars().all())

        logger.debug(
            "client_search",
            tenant_id=str(tenant_id),
            query=query,
            total=total,
        )
        return clients, total

    # ---------------------------------------------------------------------- #
    # Get with location count
    # ---------------------------------------------------------------------- #

    async def get_with_location_count(
        self,
        tenant_id: UUID,
        client_id: UUID,
    ) -> tuple[Client, int] | None:
        """
        Fetch a single client together with the number of its active locations.

        Returns:
            (Client, location_count) if found, otherwise None.
        """
        client = await self.get(client_id, tenant_id)
        if client is None:
            return None

        count_result = await self.db.execute(
            select(func.count())
            .select_from(Location)
            .where(
                and_(
                    Location.tenant_id == tenant_id,
                    Location.client_id == client_id,
                    Location.deleted_at.is_(None),
                    Location.is_active.is_(True),
                )
            )
        )
        location_count: int = count_result.scalar_one()

        logger.debug(
            "client_location_count",
            tenant_id=str(tenant_id),
            client_id=str(client_id),
            location_count=location_count,
        )
        return client, location_count
