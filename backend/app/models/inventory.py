"""Equipment, InventoryItem, and InventoryTransaction models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import enum
import uuid

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TenantAwareModel


class EquipmentStatus(str, enum.Enum):
    available = "available"
    in_use = "in_use"
    maintenance = "maintenance"
    retired = "retired"


class TransactionType(str, enum.Enum):
    received = "received"
    used = "used"
    adjusted = "adjusted"
    returned = "returned"


# --------------------------------------------------------------------------- #
# Equipment
# --------------------------------------------------------------------------- #

class Equipment(Base, TenantAwareModel):
    __tablename__ = "equipment"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    serial_number: Mapped[str | None] = mapped_column(String(150), nullable=True)
    model: Mapped[str | None] = mapped_column(String(150), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(150), nullable=True)

    purchase_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    warranty_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    status: Mapped[EquipmentStatus] = mapped_column(
        Enum(EquipmentStatus, name="equipment_status"),
        nullable=False,
        default=EquipmentStatus.available,
        index=True,
    )

    current_crew_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crews.id", ondelete="SET NULL"),
        nullable=True,
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Equipment {self.name} status={self.status}>"


# --------------------------------------------------------------------------- #
# InventoryItem
# --------------------------------------------------------------------------- #

class InventoryItem(Base, TenantAwareModel):
    __tablename__ = "inventory_items"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    unit: Mapped[str] = mapped_column(
        String(50), nullable=False, default="each"
    )  # each, gallon, pound, bag, box, roll, etc.
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, default=0
    )

    current_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, default=0
    )
    reorder_point: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, default=0
    )
    reorder_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, default=0
    )

    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    is_consumable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    transactions: Mapped[list[InventoryTransaction]] = relationship(
        "InventoryTransaction",
        back_populates="item",
        cascade="all, delete-orphan",
    )

    @property
    def needs_reorder(self) -> bool:
        return self.current_quantity <= self.reorder_point

    def __repr__(self) -> str:
        return f"<InventoryItem {self.name} qty={self.current_quantity}>"


# --------------------------------------------------------------------------- #
# InventoryTransaction
# --------------------------------------------------------------------------- #

class InventoryTransaction(Base, TenantAwareModel):
    __tablename__ = "inventory_transactions"

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity_change: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False
        # Positive = stock in, Negative = stock out
    )
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="transaction_type"),
        nullable=False,
    )
    reference_work_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_orders.id", ondelete="SET NULL"),
        nullable=True,
    )
    performed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    item: Mapped[InventoryItem] = relationship(
        "InventoryItem", back_populates="transactions"
    )
    performer: Mapped[User] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[performed_by]
    )

    def __repr__(self) -> str:
        return (
            f"<InventoryTransaction item={self.item_id} "
            f"change={self.quantity_change} type={self.transaction_type}>"
        )
