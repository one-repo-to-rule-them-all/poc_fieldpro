"""Authentication Pydantic v2 schemas."""

from __future__ import annotations

from datetime import datetime
import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator

# --------------------------------------------------------------------------- #
# Login / tokens
# --------------------------------------------------------------------------- #

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    first_name: str
    last_name: str
    full_name: str
    phone: str | None = None
    role: str
    is_active: bool
    is_verified: bool
    mfa_enabled: bool
    tenant_id: uuid.UUID | None = None
    avatar_url: str | None = None
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    logo_url: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    user: UserResponse
    tenant: TenantResponse


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #

class TenantRegisterRequest(BaseModel):
    """Create a new tenant + first admin user in a single request."""

    tenant_name: str = Field(..., min_length=2, max_length=200)
    tenant_slug: str = Field(
        ...,
        min_length=2,
        max_length=50,
        pattern=r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$",
        description="URL-safe slug, lowercase letters, digits, and hyphens",
    )
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)

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

    @field_validator("tenant_slug")
    @classmethod
    def slug_not_reserved(cls, v: str) -> str:
        reserved = {"api", "admin", "app", "www", "mail", "static", "cdn", "assets"}
        if v.lower() in reserved:
            raise ValueError(f"'{v}' is a reserved slug")
        return v.lower()


# --------------------------------------------------------------------------- #
# Password management
# --------------------------------------------------------------------------- #

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


# --------------------------------------------------------------------------- #
# Profile / password management
# --------------------------------------------------------------------------- #

class UpdateProfileRequest(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


# --------------------------------------------------------------------------- #
# MFA
# --------------------------------------------------------------------------- #

class MFASetupResponse(BaseModel):
    secret: str
    qr_code_url: str
    backup_codes: list[str]


class MFAVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=8, pattern=r"^\d+$")
