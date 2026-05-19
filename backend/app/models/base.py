"""Shared model mixins for tenant isolation, soft delete, and timestamps."""

from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

# --------------------------------------------------------------------------- #
# Timestamp mixin (for tables that don't need tenant isolation)
# --------------------------------------------------------------------------- #

class TimestampMixin:
    """Adds created_at and updated_at to any model."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )


# --------------------------------------------------------------------------- #
# Tenant-aware mixin
# --------------------------------------------------------------------------- #

class TenantAwareModel(TimestampMixin):
    """
    Mixin for all tenant-scoped resources.

    Provides:
    - id (UUID PK)
    - tenant_id (FK → tenants.id, indexed)
    - created_at / updated_at (via TimestampMixin)
    - deleted_at (soft delete)
    - filter_active() class-level helper
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    @classmethod
    def filter_active(cls):
        """Return an ORM filter expression that excludes soft-deleted rows."""
        return cls.deleted_at.is_(None)
