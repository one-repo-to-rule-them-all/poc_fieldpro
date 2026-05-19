"""Invoice, InvoiceLineItem, and Payment models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TenantAwareModel


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    viewed = "viewed"
    partial = "partial"
    paid = "paid"
    overdue = "overdue"
    void = "void"


class PaymentMethod(str, enum.Enum):
    check = "check"
    ach = "ach"
    card = "card"
    cash = "cash"
    other = "other"


# --------------------------------------------------------------------------- #
# Invoice
# --------------------------------------------------------------------------- #

class Invoice(Base, TenantAwareModel):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "invoice_number", name="uq_invoices_tenant_number"
        ),
    )

    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, name="invoice_status"),
        nullable=False,
        default=InvoiceStatus.draft,
        index=True,
    )

    issue_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    due_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    terms: Mapped[str | None] = mapped_column(Text, nullable=True)

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    client: Mapped[Client] = relationship("Client")  # type: ignore[name-defined]
    line_items: Mapped[list[InvoiceLineItem]] = relationship(
        "InvoiceLineItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceLineItem.sort_order",
    )
    payments: Mapped[list[Payment]] = relationship(
        "Payment",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )

    def recalculate_totals(self) -> None:
        """Recompute subtotal, tax_amount, and total from line items."""
        self.subtotal = sum(
            (item.line_total for item in self.line_items), start=Decimal(0)
        )
        self.tax_amount = self.subtotal * self.tax_rate
        self.total = self.subtotal + self.tax_amount - self.discount_amount

    @property
    def amount_paid(self) -> Decimal:
        return sum((p.amount for p in self.payments), start=Decimal(0))

    @property
    def amount_due(self) -> Decimal:
        return self.total - self.amount_paid

    def __repr__(self) -> str:
        return f"<Invoice #{self.invoice_number} status={self.status}>"


# --------------------------------------------------------------------------- #
# InvoiceLineItem
# --------------------------------------------------------------------------- #

class InvoiceLineItem(Base, TenantAwareModel):
    __tablename__ = "invoice_line_items"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    work_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_orders.id", ondelete="SET NULL"),
        nullable=True,
    )

    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    invoice: Mapped[Invoice] = relationship("Invoice", back_populates="line_items")

    def compute_line_total(self) -> None:
        """Set line_total = quantity * unit_price."""
        self.line_total = self.quantity * self.unit_price

    def __repr__(self) -> str:
        return f"<InvoiceLineItem {self.description[:40]} total={self.line_total}>"


# --------------------------------------------------------------------------- #
# Payment
# --------------------------------------------------------------------------- #

class Payment(Base, TenantAwareModel):
    __tablename__ = "payments"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method"),
        nullable=False,
        default=PaymentMethod.other,
    )
    reference_number: Mapped[str | None] = mapped_column(String(150), nullable=True)
    payment_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Relationships
    invoice: Mapped[Invoice] = relationship("Invoice", back_populates="payments")
    recorder: Mapped[User] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[recorded_by]
    )

    def __repr__(self) -> str:
        return (
            f"<Payment invoice={self.invoice_id} "
            f"amount={self.amount} method={self.payment_method}>"
        )
