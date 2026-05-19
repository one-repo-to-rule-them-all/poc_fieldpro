"""
Invoice service layer.

Encapsulates the business logic for creating invoices from work orders
and recording payments against existing invoices.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.models.invoice import Invoice, InvoiceLineItem, InvoiceStatus, Payment, PaymentMethod
from app.models.work_order import WorkOrder, WorkOrderStatus

logger = structlog.get_logger(__name__)

# Default hourly billing rate.  Will be made tenant-configurable in a future release.
_DEFAULT_HOURLY_RATE = Decimal("45.00")


def _next_invoice_number(existing_numbers: list[str]) -> str:
    """
    Derive the next sequential invoice number from a list of existing ones.
    Format: INV-YYYYMM-NNNN  (e.g. INV-202505-0042)
    """
    now = datetime.now(tz=UTC)
    prefix = f"INV-{now.strftime('%Y%m')}-"
    month_numbers = []
    for num in existing_numbers:
        if num.startswith(prefix):
            with contextlib.suppress(ValueError):
                month_numbers.append(int(num[len(prefix):]))
    next_seq = (max(month_numbers) + 1) if month_numbers else 1
    return f"{prefix}{next_seq:04d}"


class InvoiceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ---------------------------------------------------------------------- #
    # create_from_work_orders
    # ---------------------------------------------------------------------- #

    async def create_from_work_orders(
        self,
        tenant_id: uuid.UUID,
        work_order_ids: list[uuid.UUID],
        due_date: date,
        tax_rate: Decimal,
        notes: str | None,
        created_by: uuid.UUID,
    ) -> Invoice:
        """
        Generate an invoice from a list of completed work orders.

        Validations:
        - All work orders exist within the tenant.
        - All work orders have status = completed.
        - All work orders belong to the same client.
        - None of the work orders are already linked to an invoice.

        Each work order produces one line item.
        unit_price = (actual_hours or estimated_hours) * hourly_rate.
        """
        if not work_order_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="At least one work_order_id is required",
            )

        # Load work orders
        result = await self.db.execute(
            select(WorkOrder).where(
                WorkOrder.id.in_(work_order_ids),
                WorkOrder.tenant_id == tenant_id,
                WorkOrder.deleted_at.is_(None),
            )
        )
        work_orders = list(result.scalars().all())

        # All requested IDs must be found
        found_ids = {wo.id for wo in work_orders}
        missing_ids = set(work_order_ids) - found_ids
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Work orders not found: {[str(i) for i in missing_ids]}",
            )

        # Validate statuses
        non_completed = [wo for wo in work_orders if wo.status != WorkOrderStatus.completed]
        if non_completed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Work orders must be completed before invoicing. "
                    f"Non-completed IDs: {[str(wo.id) for wo in non_completed]}"
                ),
            )

        # All must share the same client
        client_ids = {wo.client_id for wo in work_orders}
        if len(client_ids) > 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "All work orders must belong to the same client "
                    "to generate a single invoice"
                ),
            )
        client_id = client_ids.pop()

        # None may already be invoiced
        already_invoiced = [
            wo for wo in work_orders
            if await self._work_order_has_invoice(wo.id, tenant_id)
        ]
        if already_invoiced:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Work orders already linked to an invoice: "
                    f"{[str(wo.id) for wo in already_invoiced]}"
                ),
            )

        # Generate invoice number (unique within tenant)
        invoice_number = await self._generate_invoice_number(tenant_id)

        # Build line items
        line_items_data: list[dict] = []
        subtotal = Decimal("0.00")
        for i, wo in enumerate(work_orders):
            hours = wo.actual_hours or wo.estimated_hours or Decimal("1.00")
            unit_price = (hours * _DEFAULT_HOURLY_RATE).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            line_total = unit_price  # quantity = 1
            subtotal += line_total
            line_items_data.append(
                {
                    "work_order_id": wo.id,
                    "description": wo.title,
                    "quantity": Decimal("1.000"),
                    "unit_price": unit_price,
                    "line_total": line_total,
                    "sort_order": i,
                }
            )

        tax_amount = (subtotal * tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total = subtotal + tax_amount

        now = datetime.now(tz=UTC)

        # Create Invoice
        invoice = Invoice(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            invoice_number=invoice_number,
            client_id=client_id,
            status=InvoiceStatus.draft,
            issue_date=now,
            due_date=datetime(
                due_date.year, due_date.month, due_date.day, 23, 59, 59, tzinfo=UTC
            ),
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            discount_amount=Decimal("0.00"),
            total=total,
            notes=notes,
        )
        self.db.add(invoice)
        await self.db.flush()  # populate invoice.id

        # Create line items
        for item_data in line_items_data:
            line_item = InvoiceLineItem(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                invoice_id=invoice.id,
                work_order_id=item_data["work_order_id"],
                description=item_data["description"],
                quantity=item_data["quantity"],
                unit_price=item_data["unit_price"],
                line_total=item_data["line_total"],
                sort_order=item_data["sort_order"],
            )
            self.db.add(line_item)

        # Link work orders back to this invoice
        # WorkOrder does not carry an invoice_id column in the current schema,
        # so we track the relationship via InvoiceLineItem.work_order_id.
        # If an invoice_id column is added to WorkOrder later, set it here.

        await self.db.flush()

        # Re-fetch with eager-loaded relationships and fresh scalar columns.
        # db.refresh(invoice, [rel_names]) only reloads the listed attrs and
        # leaves other server-generated columns (e.g. updated_at) expired —
        # the next sync access raises MissingGreenlet in async context.
        invoice = await self._reload_invoice(invoice.id)

        logger.info(
            "invoice_created_from_work_orders",
            tenant_id=str(tenant_id),
            invoice_id=str(invoice.id),
            invoice_number=invoice_number,
            client_id=str(client_id),
            work_order_count=len(work_orders),
            total=str(total),
            created_by=str(created_by),
        )

        return invoice

    # ---------------------------------------------------------------------- #
    # record_payment
    # ---------------------------------------------------------------------- #

    async def record_payment(
        self,
        tenant_id: uuid.UUID,
        invoice_id: uuid.UUID,
        amount: Decimal,
        payment_date: date,
        payment_method: str,
        reference_number: str | None,
        notes: str | None,
        recorded_by: uuid.UUID,
    ) -> Invoice:
        """
        Record a payment against an invoice.

        - Validates the invoice is not voided.
        - Creates a Payment record.
        - Recalculates amount_paid by summing all payments.
        - Updates invoice status: partial / paid.
        - Sets invoice.paid_at when fully paid.
        """
        result = await self.db.execute(
            select(Invoice)
            .where(
                Invoice.id == invoice_id,
                Invoice.tenant_id == tenant_id,
                Invoice.deleted_at.is_(None),
            )
            .options(selectinload(Invoice.payments))
        )
        invoice = result.scalar_one_or_none()
        if invoice is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found",
            )

        if invoice.status == InvoiceStatus.void:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot record a payment against a voided invoice",
            )

        if amount <= Decimal("0"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Payment amount must be greater than zero",
            )

        try:
            method = PaymentMethod(payment_method)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid payment_method: {payment_method}",
            ) from err

        now = datetime.now(tz=UTC)
        payment = Payment(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            invoice_id=invoice_id,
            amount=amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            payment_method=method,
            reference_number=reference_number,
            payment_date=datetime(
                payment_date.year, payment_date.month, payment_date.day,
                tzinfo=UTC,
            ),
            notes=notes,
            recorded_by=recorded_by,
        )
        self.db.add(payment)
        await self.db.flush()

        # Refresh to include the new payment in the relationship
        await self.db.refresh(invoice, ["payments"])

        total_paid = sum(p.amount for p in invoice.payments)

        if total_paid >= invoice.total:
            invoice.status = InvoiceStatus.paid
            invoice.paid_at = now
        elif total_paid > Decimal("0"):
            invoice.status = InvoiceStatus.partial
            invoice.paid_at = None
        # If somehow total_paid is 0 after payment (shouldn't happen), leave status alone.

        await self.db.flush()

        # Re-fetch so updated_at (server-side onupdate) is populated and
        # both line_items and payments are eager-loaded — see note in
        # create_from_work_orders for why db.refresh(..., [rels]) is unsafe.
        invoice = await self._reload_invoice(invoice_id)

        logger.info(
            "invoice_payment_recorded",
            tenant_id=str(tenant_id),
            invoice_id=str(invoice_id),
            payment_id=str(payment.id),
            amount=str(amount),
            new_status=invoice.status.value,
            recorded_by=str(recorded_by),
        )

        return invoice

    # ---------------------------------------------------------------------- #
    # Private helpers
    # ---------------------------------------------------------------------- #

    async def _reload_invoice(self, invoice_id: uuid.UUID) -> Invoice:
        """
        Re-fetch an invoice with line_items and payments eager-loaded.

        Used after mutations so callers receive an instance with all
        server-generated columns (e.g. updated_at via onupdate=func.now())
        populated and relationships ready to iterate — avoiding sync lazy
        loads that raise MissingGreenlet in async context.
        """
        result = await self.db.execute(
            select(Invoice)
            .options(
                selectinload(Invoice.line_items),
                selectinload(Invoice.payments),
            )
            .where(Invoice.id == invoice_id)
        )
        return result.scalar_one()

    async def _work_order_has_invoice(
        self, work_order_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> bool:
        """
        Return True if a completed work order is already attached to a
        non-void invoice via an InvoiceLineItem.
        """
        result = await self.db.execute(
            select(InvoiceLineItem)
            .join(Invoice, InvoiceLineItem.invoice_id == Invoice.id)
            .where(
                InvoiceLineItem.work_order_id == work_order_id,
                Invoice.tenant_id == tenant_id,
                Invoice.status != InvoiceStatus.void,
                Invoice.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none() is not None

    async def _generate_invoice_number(self, tenant_id: uuid.UUID) -> str:
        """
        Pick the next unused invoice number for the current month.
        Concurrency note: the unique constraint on (tenant_id, invoice_number)
        will catch any race condition at the DB level.
        """

        now = datetime.now(tz=UTC)
        prefix = f"INV-{now.strftime('%Y%m')}-"

        result = await self.db.execute(
            select(Invoice.invoice_number).where(
                Invoice.tenant_id == tenant_id,
                Invoice.invoice_number.like(f"{prefix}%"),
            )
        )
        existing = [row[0] for row in result.all()]
        return _next_invoice_number(existing)
