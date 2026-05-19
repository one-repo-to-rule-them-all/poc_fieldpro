"""Invoice, InvoiceLineItem, and Payment Pydantic v2 schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

# --------------------------------------------------------------------------- #
# Invoice line item schemas
# --------------------------------------------------------------------------- #

class InvoiceLineItemCreate(BaseModel):
    work_order_id: uuid.UUID | None = None
    description: str = Field(..., min_length=1, max_length=500)
    quantity: Decimal = Field(default=Decimal("1"), gt=Decimal("0"))
    unit_price: Decimal = Field(..., ge=Decimal("0"))
    sort_order: int = 0


class InvoiceLineItemUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=1, max_length=500)
    quantity: Decimal | None = Field(default=None, gt=Decimal("0"))
    unit_price: Decimal | None = Field(default=None, ge=Decimal("0"))
    sort_order: int | None = None


class InvoiceLineItemResponse(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    work_order_id: uuid.UUID | None = None
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Payment schemas
# --------------------------------------------------------------------------- #

PaymentMethodLiteral = Literal[
    "check", "ach", "credit_card", "cash", "wire", "other"
]


class RecordPaymentRequest(BaseModel):
    amount: Decimal = Field(..., gt=Decimal("0"))
    payment_date: date
    payment_method: PaymentMethodLiteral
    reference_number: str | None = Field(default=None, max_length=150)
    notes: str | None = None


class PaymentResponse(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    amount: Decimal
    payment_date: date
    payment_method: str
    reference_number: str | None = None
    notes: str | None = None
    recorded_by: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Invoice schemas
# --------------------------------------------------------------------------- #

class InvoiceCreate(BaseModel):
    client_id: uuid.UUID
    issue_date: date = Field(default_factory=date.today)
    due_date: date
    tax_rate: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), le=Decimal("1"))
    discount_amount: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    notes: str | None = None
    line_items: list[InvoiceLineItemCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def due_date_after_issue_date(self) -> InvoiceCreate:
        if self.due_date < self.issue_date:
            raise ValueError("due_date must be on or after issue_date")
        return self


class InvoiceUpdate(BaseModel):
    due_date: date | None = None
    tax_rate: Decimal | None = Field(
        default=None, ge=Decimal("0"), le=Decimal("1")
    )
    discount_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    notes: str | None = None


class InvoiceFromWorkOrdersRequest(BaseModel):
    """Generate an invoice from one or more completed work orders."""

    work_order_ids: list[uuid.UUID] = Field(..., min_length=1)
    due_date: date
    tax_rate: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), le=Decimal("1"))
    notes: str | None = None


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    client_id: uuid.UUID
    invoice_number: str
    status: str
    issue_date: date
    due_date: date
    subtotal: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    amount_paid: Decimal
    balance_due: Decimal
    notes: str | None = None
    pdf_url: str | None = None
    sent_at: datetime | None = None
    paid_at: datetime | None = None
    line_items: list[InvoiceLineItemResponse] = Field(default_factory=list)
    payments: list[PaymentResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_computed(cls, invoice) -> InvoiceResponse:
        """
        Build InvoiceResponse from an ORM Invoice object, computing derived
        fields (total_amount, amount_paid, balance_due) from model properties.
        """
        # The model stores `total` not `total_amount`; bridge here.
        total_amount = getattr(invoice, "total", Decimal("0"))
        amount_paid = getattr(invoice, "amount_paid", Decimal("0"))
        balance_due = getattr(invoice, "amount_due", total_amount - amount_paid)
        pdf_url: str | None = getattr(invoice, "pdf_url", None)

        return cls(
            id=invoice.id,
            tenant_id=invoice.tenant_id,
            client_id=invoice.client_id,
            invoice_number=invoice.invoice_number,
            status=invoice.status,
            issue_date=invoice.issue_date
            if isinstance(invoice.issue_date, date)
            else invoice.issue_date.date(),
            due_date=invoice.due_date
            if isinstance(invoice.due_date, date)
            else invoice.due_date.date(),
            subtotal=invoice.subtotal,
            tax_rate=invoice.tax_rate,
            tax_amount=invoice.tax_amount,
            discount_amount=invoice.discount_amount,
            total_amount=total_amount,
            amount_paid=amount_paid,
            balance_due=balance_due,
            notes=invoice.notes,
            pdf_url=pdf_url,
            sent_at=invoice.sent_at,
            paid_at=invoice.paid_at,
            line_items=[
                InvoiceLineItemResponse.model_validate(li)
                for li in (invoice.line_items or [])
            ],
            payments=[
                PaymentResponse.model_validate(p)
                for p in (invoice.payments or [])
            ],
            created_at=invoice.created_at,
            updated_at=invoice.updated_at,
        )


class InvoiceListResponse(BaseModel):
    """Slim representation used in paginated list views.

    Field names match what _invoice_to_dict() returns (total / amount_due).
    """

    id: uuid.UUID
    tenant_id: uuid.UUID
    invoice_number: str
    client_id: uuid.UUID
    client_name: str | None = None
    status: str
    issue_date: datetime
    due_date: datetime
    subtotal: float
    tax_rate: float
    tax_amount: float
    discount_amount: float
    total: float
    amount_paid: float
    amount_due: float
    notes: str | None = None
    sent_at: str | None = None
    paid_at: str | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class InvoiceLineItemDetail(BaseModel):
    """Line item as returned by _line_item_to_dict()."""

    id: uuid.UUID
    invoice_id: uuid.UUID
    work_order_id: uuid.UUID | None = None
    description: str
    quantity: float
    unit_price: float
    line_total: float
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class PaymentDetail(BaseModel):
    """Payment record as returned by _payment_to_dict()."""

    id: uuid.UUID
    invoice_id: uuid.UUID
    amount: float
    payment_method: str
    reference_number: str | None = None
    payment_date: str
    notes: str | None = None
    recorded_by: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceDetailResponse(InvoiceListResponse):
    """Full invoice with line items and payments."""

    terms: str | None = None
    line_items: list[InvoiceLineItemDetail] = []
    payments: list[PaymentDetail] = []
