"""Tenant, SubscriptionPlan, and TenantSubscription models."""

from __future__ import annotations

from decimal import Decimal
import enum
import uuid

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    past_due = "past_due"
    cancelled = "cancelled"
    trialing = "trialing"


# --------------------------------------------------------------------------- #
# SubscriptionPlan
# --------------------------------------------------------------------------- #

class SubscriptionPlan(Base, TimestampMixin):
    __tablename__ = "subscription_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_monthly: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    price_yearly: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    max_users: Mapped[int] = mapped_column(nullable=False, default=10)
    max_locations: Mapped[int] = mapped_column(nullable=False, default=50)
    features: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    tenants: Mapped[list[Tenant]] = relationship("Tenant", back_populates="plan")
    subscriptions: Mapped[list[TenantSubscription]] = relationship(
        "TenantSubscription", back_populates="plan"
    )

    def __repr__(self) -> str:
        return f"<SubscriptionPlan {self.name}>"


# --------------------------------------------------------------------------- #
# Tenant
# --------------------------------------------------------------------------- #

class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    subscription_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Relationships
    plan: Mapped[SubscriptionPlan | None] = relationship(
        "SubscriptionPlan", back_populates="tenants"
    )
    subscriptions: Mapped[list[TenantSubscription]] = relationship(
        "TenantSubscription", back_populates="tenant", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Tenant {self.slug}>"


# --------------------------------------------------------------------------- #
# TenantSubscription
# --------------------------------------------------------------------------- #

class TenantSubscription(Base, TimestampMixin):
    __tablename__ = "tenant_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status"),
        nullable=False,
        default=SubscriptionStatus.trialing,
    )
    current_period_start: Mapped[str | None] = mapped_column(nullable=True)
    current_period_end: Mapped[str | None] = mapped_column(nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )

    # Relationships
    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="subscriptions")
    plan: Mapped[SubscriptionPlan] = relationship(
        "SubscriptionPlan", back_populates="subscriptions"
    )

    def __repr__(self) -> str:
        return f"<TenantSubscription tenant={self.tenant_id} status={self.status}>"
