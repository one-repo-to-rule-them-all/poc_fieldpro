"""Crew and CrewMember models."""

from __future__ import annotations

from datetime import datetime
import enum
import uuid

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TenantAwareModel


class CrewMemberRole(str, enum.Enum):
    lead = "lead"
    member = "member"


# --------------------------------------------------------------------------- #
# Crew
# --------------------------------------------------------------------------- #

class Crew(Base, TenantAwareModel):
    __tablename__ = "crews"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_crews_tenant_code"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    members: Mapped[list[CrewMember]] = relationship(
        "CrewMember",
        back_populates="crew",
        primaryjoin="and_(CrewMember.crew_id == Crew.id, CrewMember.left_at.is_(None))",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Crew {self.code} - {self.name}>"


# --------------------------------------------------------------------------- #
# CrewMember
# --------------------------------------------------------------------------- #

class CrewMember(Base, TenantAwareModel):
    __tablename__ = "crew_members"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "crew_id", "user_id",
            name="uq_crew_member_tenant_crew_user"
        ),
    )

    crew_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[CrewMemberRole] = mapped_column(
        Enum(CrewMemberRole, name="crew_member_role"),
        nullable=False,
        default=CrewMemberRole.member,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    left_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    crew: Mapped[Crew] = relationship("Crew", back_populates="members")
    user: Mapped[User] = relationship("User")  # type: ignore[name-defined]

    @property
    def is_active(self) -> bool:
        return self.left_at is None

    def __repr__(self) -> str:
        return f"<CrewMember crew={self.crew_id} user={self.user_id} role={self.role}>"
