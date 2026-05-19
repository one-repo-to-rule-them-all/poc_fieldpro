"""Invoice repository — tenant-scoped CRUD + domain-specific queries."""

from __future__ import annotations

from datetime import UTC
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.models.invoice import Invoice, InvoiceStatus, Payment
from app.repositories.base import BaseRepository

logger = structlog.get_logger(__name__)

# Statuses that represent money still owed to the tenant.
_OUTSTANDING_STATUSES = (
    InvoiceStatus.sent,
    InvoiceStatus.viewed,
    InvoiceStatus.overdue,
    InvoiceStatus.partial,
)


class InvoiceRepository(BaseRepository[Invoice]):
    """
    Extends BaseRepository with invoice-specific query methods.

    All queries are automatically scoped to the supplied tenant_id and
    exclude soft-deleted rows via the inherited _base_filter helper.
    """

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Invoice, db)

    # ---------------------------------------------------------------------- #
    # Eager-loaded single record
    # ---------------------------------------------------------------------- #

    async def get_with_line_items(
        self,
        tenant_id: UUID,
        id: UUID,
    ) -> Invoice | None:
        """
        Fetch an invoice with its line_items and payments eagerly loaded.

        Returns None if not found or if it belongs to a different tenant.
        """
        result = await self.db.execute(
            select(Invoice)
            .where(
                and_(
                    Invoice.id == id,
                    Invoice.tenant_id == tenant_id,
                    Invoice.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(Invoice.line_items),
                selectinload(Invoice.payments),
            )
        )
        return result.scalar_one_or_none()

    # ---------------------------------------------------------------------- #
    # Client-scoped list
    # ---------------------------------------------------------------------- #

    async def list_by_client(
        self,
        tenant_id: UUID,
        client_id: UUID,
        status_filter: list[str] | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Invoice], int]:
        """
        Return a paginated list of invoices for a specific client.

        Args:
            tenant_id:     Tenant scope.
            client_id:     Only invoices for this client.
            status_filter: Optional list of status strings to restrict results.
            skip:          Offset for pagination.
            limit:         Max records to return.

        Returns:
            (invoices, total_count) tuple ordered by issue_date descending.
        """
        base = self._base_filter(tenant_id)
        filters = [*base, Invoice.client_id == client_id]

        if status_filter:
            filters.append(Invoice.status.in_(status_filter))

        combined = and_(*filters)

        count_result = await self.db.execute(
            select(func.count()).select_from(Invoice).where(combined)
        )
        total: int = count_result.scalar_one()

        result = await self.db.execute(
            select(Invoice)
            .where(combined)
            .order_by(Invoice.issue_date.desc())
            .offset(skip)
            .limit(limit)
        )
        invoices = list(result.scalars().all())

        logger.debug(
            "invoice_list_by_client",
            tenant_id=str(tenant_id),
            client_id=str(client_id),
            status_filter=status_filter,
            total=total,
        )
        return invoices, total

    # ---------------------------------------------------------------------- #
    # Invoice number generation
    # ---------------------------------------------------------------------- #

    async def get_next_invoice_number(self, tenant_id: UUID) -> str:
        """
        Generate the next sequential invoice number for the tenant.

        Format: INV-{YYYY}-{NNNN} where NNNN is zero-padded to 4 digits.
        The sequence restarts at 0001 each calendar year.

        The implementation queries the current maximum numeric suffix for
        this year, then increments by one.  This is safe for concurrent use
        because the calling service should run inside a transaction that
        creates the invoice row before committing (preventing duplicates via
        the unique constraint on tenant_id + invoice_number).

        Returns:
            Next invoice number string, e.g. "INV-2026-0007".
        """
        from datetime import datetime

        year = datetime.now(tz=UTC).year
        prefix = f"INV-{year}-"

        # Find the maximum existing sequence number for this year.
        result = await self.db.execute(
            select(Invoice.invoice_number)
            .where(
                and_(
                    Invoice.tenant_id == tenant_id,
                    Invoice.invoice_number.like(f"{prefix}%"),
                )
            )
            .order_by(Invoice.invoice_number.desc())
            .limit(1)
        )
        last_number: str | None = result.scalar_one_or_none()

        if last_number is None:
            next_seq = 1
        else:
            # Extract the numeric suffix after the prefix.
            suffix = last_number[len(prefix):]
            try:
                next_seq = int(suffix) + 1
            except ValueError:
                next_seq = 1

        invoice_number = f"{prefix}{next_seq:04d}"

        logger.debug(
            "invoice_next_number",
            tenant_id=str(tenant_id),
            invoice_number=invoice_number,
        )
        return invoice_number

    # ---------------------------------------------------------------------- #
    # Outstanding balance aggregation
    # ---------------------------------------------------------------------- #

    async def get_outstanding_balance(self, tenant_id: UUID) -> Decimal:
        """
        Return the total outstanding balance across all open invoices.

        "Outstanding" = invoices with status in (sent, viewed, overdue, partial).
        The balance per invoice is computed as total - sum(payments.amount).

        Returns:
            Decimal sum of balance_due across all qualifying invoices.
        """
        # Step 1: sum of payments per invoice for outstanding invoices.
        outstanding_status_values = [s.value for s in _OUTSTANDING_STATUSES]

        # Subquery: total paid per invoice.
        paid_subq = (
            select(
                Payment.invoice_id.label("invoice_id"),
                func.coalesce(func.sum(Payment.amount), 0).label("total_paid"),
            )
            .group_by(Payment.invoice_id)
            .subquery()
        )

        # Main query: sum over (total - total_paid) for outstanding invoices.
        result = await self.db.execute(
            select(
                func.coalesce(
                    func.sum(Invoice.total - func.coalesce(paid_subq.c.total_paid, 0)),
                    0,
                ).label("outstanding")
            )
            .select_from(Invoice)
            .outerjoin(paid_subq, paid_subq.c.invoice_id == Invoice.id)
            .where(
                and_(
                    Invoice.tenant_id == tenant_id,
                    Invoice.deleted_at.is_(None),
                    Invoice.status.in_(outstanding_status_values),
                )
            )
        )
        outstanding: Decimal = Decimal(str(result.scalar_one() or 0))

        logger.debug(
            "invoice_outstanding_balance",
            tenant_id=str(tenant_id),
            outstanding=str(outstanding),
        )
        return outstanding
