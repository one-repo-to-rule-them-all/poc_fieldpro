"""Client and ClientContact models."""

from __future__ import annotations

from datetime import datetime
import enum
import uuid

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TenantAwareModel


class Industry(str, enum.Enum):
    commercial_cleaning = "commercial_cleaning"
    janitorial = "janitorial"
    landscaping = "landscaping"
    hvac = "hvac"
    plumbing = "plumbing"
    electrical = "electrical"
    security = "security"
    pest_control = "pest_control"
    facility_management = "facility_management"
    construction = "construction"
    other = "other"


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #

class Client(Base, TenantAwareModel):
    __tablename__ = "clients"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_clients_tenant_code"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)

    industry: Mapped[Industry | None] = mapped_column(
        Enum(Industry, name="industry_type"), nullable=True
    )

    billing_address: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    billing_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    billing_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    contract_start_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    contract_end_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    contacts: Mapped[list[ClientContact]] = relationship(
        "ClientContact",
        back_populates="client",
        cascade="all, delete-orphan",
        primaryjoin=(
            "and_(ClientContact.client_id == Client.id, "
            "ClientContact.deleted_at.is_(None))"
        ),
    )
    locations: Mapped[list[Location]] = relationship(  # type: ignore[name-defined]
        "Location",
        back_populates="client",
        primaryjoin="and_(Location.client_id == Client.id, Location.deleted_at.is_(None))",
    )

    def __repr__(self) -> str:
        return f"<Client {self.code} - {self.name}>"


# --------------------------------------------------------------------------- #
# ClientContact
# --------------------------------------------------------------------------- #

class ClientContact(Base, TenantAwareModel):
    __tablename__ = "client_contacts"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    title: Mapped[str | None] = mapped_column(String(150), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    client: Mapped[Client] = relationship("Client", back_populates="contacts")

    def __repr__(self) -> str:
        return f"<ClientContact {self.name} client={self.client_id}>"
