"""Tenant and SubscriptionPlan Pydantic v2 schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# --------------------------------------------------------------------------- #
# Tenant schemas
# --------------------------------------------------------------------------- #

class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    industry: str | None = None
    timezone: str
    subscription_status: str
    trial_ends_at: datetime | None = None
    billing_email: str | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TenantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    industry: str | None = None
    timezone: str | None = None
    billing_email: EmailStr | None = None
    logo_url: str | None = Field(default=None, max_length=500)
    settings: dict | None = None


class TenantSettingsResponse(BaseModel):
    """Current tenant configuration and feature flags."""

    id: uuid.UUID
    name: str
    slug: str
    logo_url: str | None = None
    settings: dict
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# SubscriptionPlan schemas
# --------------------------------------------------------------------------- #

class SubscriptionPlanResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    price_monthly: Decimal
    max_employees: int | None = None
    max_clients: int | None = None
    max_locations: int | None = None
    features: dict
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class SubscriptionPlanListResponse(BaseModel):
    """Slim representation for plan selection UI."""

    id: uuid.UUID
    name: str
    slug: str
    price_monthly: Decimal
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
