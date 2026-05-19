"""User repository — tenant-scoped CRUD + domain-specific queries."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.user import User, UserRole
from app.repositories.base import BaseRepository

logger = structlog.get_logger(__name__)


class UserRepository(BaseRepository[User]):
    """
    Extends BaseRepository with user-specific query methods.

    get_by_email is scoped to a single tenant (used in most flows).
    get_by_email_any_tenant is unscoped — for platform-admin lookups only.
    """

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(User, db)

    # ---------------------------------------------------------------------- #
    # Lookup by email (tenant-scoped)
    # ---------------------------------------------------------------------- #

    async def get_by_email(
        self,
        tenant_id: UUID,
        email: str,
    ) -> User | None:
        """
        Return the user with the given email within a tenant.

        Returns None if no active, non-deleted record is found.
        """
        result = await self.db.execute(
            select(User).where(
                and_(
                    User.tenant_id == tenant_id,
                    User.email == email.lower(),
                    User.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    # ---------------------------------------------------------------------- #
    # Lookup by email (cross-tenant — platform admin only)
    # ---------------------------------------------------------------------- #

    async def get_by_email_any_tenant(self, email: str) -> User | None:
        """
        Return any active user with the given email, across all tenants.

        Used exclusively by platform-owner tooling (e.g. support lookup).
        Do NOT expose this to tenant-level callers.
        """
        result = await self.db.execute(
            select(User).where(
                and_(
                    User.email == email.lower(),
                    User.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    # ---------------------------------------------------------------------- #
    # List by role
    # ---------------------------------------------------------------------- #

    async def list_by_role(
        self,
        tenant_id: UUID,
        role: str | UserRole,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[User], int]:
        """
        Return a paginated list of users that have the specified role.

        Args:
            tenant_id: Tenant scope.
            role:      Role string or UserRole enum value.
            skip:      Offset for pagination.
            limit:     Max records to return.

        Returns:
            (users, total_count) tuple.
        """
        role_value = role.value if isinstance(role, UserRole) else role

        base = self._base_filter(tenant_id)
        combined = and_(*base, User.role == role_value)

        count_result = await self.db.execute(
            select(func.count()).select_from(User).where(combined)
        )
        total: int = count_result.scalar_one()

        result = await self.db.execute(
            select(User)
            .where(combined)
            .order_by(User.last_name.asc(), User.first_name.asc())
            .offset(skip)
            .limit(limit)
        )
        users = list(result.scalars().all())

        logger.debug(
            "user_list_by_role",
            tenant_id=str(tenant_id),
            role=role_value,
            total=total,
        )
        return users, total
