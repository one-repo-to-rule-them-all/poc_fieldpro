"""Location and LocationServiceWindow models."""

from __future__ import annotations

from decimal import Decimal
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, Time, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TenantAwareModel

# --------------------------------------------------------------------------- #
# Location
# --------------------------------------------------------------------------- #

class Location(Base, TenantAwareModel):
    __tablename__ = "locations"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Structured address stored as JSONB: {street, city, state, zip, country}
    address: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    latitude: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 8), nullable=True
    )
    longitude: Mapped[Decimal | None] = mapped_column(
        Numeric(11, 8), nullable=True
    )
    geofence_radius_meters: Mapped[int] = mapped_column(
        Integer, nullable=False, default=200
    )

    access_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    special_requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # QR code token for on-site check-in
    qr_code_token: Mapped[str | None] = mapped_column(
        String(128), nullable=True, unique=True, index=True
    )

    # Relationships
    client: Mapped[Client] = relationship(  # type: ignore[name-defined]
        "Client", back_populates="locations"
    )
    service_windows: Mapped[list[LocationServiceWindow]] = relationship(
        "LocationServiceWindow",
        back_populates="location",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Location {self.name} client={self.client_id}>"


# --------------------------------------------------------------------------- #
# LocationServiceWindow
# --------------------------------------------------------------------------- #

class LocationServiceWindow(Base, TenantAwareModel):
    """
    Defines the allowed service hours for a location per day of week.

    day_of_week: 0 = Monday, 6 = Sunday (ISO weekday - 1)
    """

    __tablename__ = "location_service_windows"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "location_id", "day_of_week",
            name="uq_service_window_location_day"
        ),
    )

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 0 = Monday ... 6 = Sunday
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[str] = mapped_column(Time(timezone=False), nullable=False)
    end_time: Mapped[str] = mapped_column(Time(timezone=False), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    location: Mapped[Location] = relationship(
        "Location", back_populates="service_windows"
    )

    def __repr__(self) -> str:
        return f"<ServiceWindow location={self.location_id} day={self.day_of_week}>"
