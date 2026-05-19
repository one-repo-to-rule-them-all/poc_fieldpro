"""User, EmployeeProfile, and RefreshToken models."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import enum
from typing import ClassVar
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TenantAwareModel, TimestampMixin


class UserRole(str, enum.Enum):
    platform_owner = "platform_owner"
    tenant_admin = "tenant_admin"
    manager = "manager"
    employee = "employee"
    client_user = "client_user"


# --------------------------------------------------------------------------- #
# User
# --------------------------------------------------------------------------- #

class User(Base, TenantAwareModel):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )

    # Audit log: strip these fields from old_values/new_values diffs even when
    # they change. The listener in app/core/audit/listeners.py applies this on
    # top of DEFAULT_DENY_FIELDS. (hashed_password is already in defaults; this
    # ClassVar exists as the documented per-model extension pattern.)
    __audit_deny_fields__: ClassVar[frozenset[str]] = frozenset({
        "hashed_password",
        "mfa_secret",
    })

    # Override id/tenant_id from mixin — needed for composite unique constraint
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.employee,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # MFA
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    employee_profile: Mapped[EmployeeProfile | None] = relationship(
        "EmployeeProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<User {self.email} role={self.role}>"


# --------------------------------------------------------------------------- #
# EmployeeProfile
# --------------------------------------------------------------------------- #

class EmployeeProfile(Base, TenantAwareModel):
    __tablename__ = "employee_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    employee_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hire_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    hourly_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    certifications: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    emergency_contact: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="employee_profile")

    def __repr__(self) -> str:
        return f"<EmployeeProfile user={self.user_id}>"


# --------------------------------------------------------------------------- #
# RefreshToken
# --------------------------------------------------------------------------- #

class RefreshToken(Base, TimestampMixin):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Store a SHA-256 hash of the token, not the token itself
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="refresh_tokens")

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_expired(self) -> bool:
        return self.expires_at < datetime.now(tz=UTC)

    def __repr__(self) -> str:
        return f"<RefreshToken user={self.user_id} revoked={self.is_revoked}>"
