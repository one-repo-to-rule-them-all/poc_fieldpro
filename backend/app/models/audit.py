"""AuditLog and Notification models."""

from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TenantAwareModel

# --------------------------------------------------------------------------- #
# AuditLog
# NOTE: Intentionally does NOT extend TenantAwareModel — platform owners need
# to query across all tenants. tenant_id is stored as a plain column with an
# index rather than a FK-enforced constraint, allowing log entries to survive
# tenant deletion.
# --------------------------------------------------------------------------- #

class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_tenant_resource_date", "tenant_id", "resource_type", "created_at"),
        Index("ix_audit_logs_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    action: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
        # e.g. "created", "updated", "deleted", "login", "login_failed", "exported"
    )
    resource_type: Mapped[str] = mapped_column(
        String(100), nullable=False
        # e.g. "WorkOrder", "User", "Invoice"
    )
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    old_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Per-request correlation id. Populated from AuditContext.request_id
    # (set upstream by RequestIDMiddleware). Lets queries thread every
    # row produced by a single HTTP request together — e.g., "show all
    # rows from request abc-123" → WHERE request_id = 'abc-123'.
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships (optional — user may be deleted)
    actor: Mapped[User | None] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[user_id]
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog action={self.action} resource={self.resource_type}"
            f"/{self.resource_id}>"
        )


# --------------------------------------------------------------------------- #
# Notification
# --------------------------------------------------------------------------- #

class Notification(Base, TenantAwareModel):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    notification_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
        # e.g. "work_order_assigned", "sla_breach_warning", "invoice_paid"
    )
    reference_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # JSONB tracking delivery status per channel
    # e.g. {"email": "sent", "sms": "failed", "push": "delivered"}
    sent_via: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Relationships
    user: Mapped[User] = relationship("User", foreign_keys=[user_id])  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return (
            f"<Notification user={self.user_id} type={self.notification_type}"
            f" read={self.is_read}>"
        )
