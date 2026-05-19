"""User management Pydantic v2 schemas.

Note: Authentication-specific schemas (LoginRequest, LoginResponse, etc.)
live in app.schemas.auth.  These schemas cover user creation and management
endpoints used by tenant admins and platform owners.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# --------------------------------------------------------------------------- #
# Allowed roles for tenant-level user creation.
# platform_owner and tenant_admin can only be granted through separate flows.
# --------------------------------------------------------------------------- #

_CREATABLE_ROLES = {"manager", "employee", "client_user"}


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    role: Literal["manager", "employee", "client_user"] = "employee"

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    is_active: bool | None = None
    role: str | None = None

    @field_validator("role")
    @classmethod
    def role_must_be_creatable(cls, v: str | None) -> str | None:
        if v is not None and v not in _CREATABLE_ROLES:
            raise ValueError(
                f"role must be one of: {', '.join(sorted(_CREATABLE_ROLES))}"
            )
        return v


class UserResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    email: str
    first_name: str
    last_name: str
    full_name: str
    phone: str | None = None
    role: str
    is_active: bool
    mfa_enabled: bool
    last_login_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    """Slim representation used in paginated list views."""

    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
