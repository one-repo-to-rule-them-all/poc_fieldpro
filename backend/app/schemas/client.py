"""Client Pydantic v2 schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# --------------------------------------------------------------------------- #
# Base
# --------------------------------------------------------------------------- #

class ClientBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    client_type: Literal["commercial", "government", "residential", "medical"] = "commercial"
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    billing_address: dict | None = None
    billing_terms: Literal["immediate", "net15", "net30", "net45", "net60"] = "net30"
    tax_id: str | None = None
    notes: str | None = None


# --------------------------------------------------------------------------- #
# Create
# --------------------------------------------------------------------------- #

class ClientCreate(ClientBase):
    pass


# --------------------------------------------------------------------------- #
# Update  (PATCH semantics — all fields optional)
# --------------------------------------------------------------------------- #

class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    client_type: Literal["commercial", "government", "residential", "medical"] | None = None
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    billing_address: dict | None = None
    billing_terms: Literal["immediate", "net15", "net30", "net45", "net60"] | None = None
    tax_id: str | None = None
    notes: str | None = None
    is_active: bool | None = None


# --------------------------------------------------------------------------- #
# Responses
# --------------------------------------------------------------------------- #

class ClientResponse(ClientBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ClientListResponse(BaseModel):
    """Slim representation used in paginated list views."""

    id: uuid.UUID
    name: str
    code: str
    industry: str | None = None
    billing_email: str | None = None
    billing_phone: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ClientDetailResponse(BaseModel):
    """Full client representation returned by get/create/update endpoints."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    code: str
    industry: str | None = None
    billing_address: dict | None = None
    billing_email: str | None = None
    billing_phone: str | None = None
    contract_start_date: str | None = None
    contract_end_date: str | None = None
    notes: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None
    location_count: int | None = None

    model_config = ConfigDict(from_attributes=True)
