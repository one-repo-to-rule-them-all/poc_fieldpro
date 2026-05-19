"""Invoices API router — invoice CRUD, billing from work orders, payments."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
import math
from typing import Annotated, Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.core.database import get_db
from app.core.dependencies import (
    CurrentTenantId,
    CurrentUser,
    require_permission,
)
from app.models.client import Client
from app.models.invoice import Invoice, InvoiceLineItem, InvoiceStatus, Payment
from app.schemas.common import PaginatedResponse
from app.schemas.invoice import InvoiceDetailResponse, InvoiceListResponse
from app.services.invoice_service import InvoiceService

logger = structlog.get_logger(__name__)
router = APIRouter()


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #


def _line_item_to_dict(item: InvoiceLineItem) -> dict:
    return {
        "id": str(item.id),
        "invoice_id": str(item.invoice_id),
        "work_order_id": str(item.work_order_id) if item.work_order_id else None,
        "description": item.description,
        "quantity": float(item.quantity),
        "unit_price": float(item.unit_price),
        "line_total": float(item.line_total),
        "sort_order": item.sort_order,
    }


def _payment_to_dict(payment: Payment) -> dict:
    return {
        "id": str(payment.id),
        "invoice_id": str(payment.invoice_id),
        "amount": float(payment.amount),
        "payment_method": payment.payment_method.value,
        "reference_number": payment.reference_number,
        "payment_date": payment.payment_date.isoformat(),
        "notes": payment.notes,
        "recorded_by": str(payment.recorded_by),
        "created_at": payment.created_at.isoformat(),
    }


def _invoice_to_dict(
    invoice: Invoice,
    include_related: bool = False,
    client_name: str | None = None,
) -> dict:
    d: dict[str, Any] = {
        "id": str(invoice.id),
        "tenant_id": str(invoice.tenant_id),
        "invoice_number": invoice.invoice_number,
        "client_id": str(invoice.client_id),
        "client_name": client_name,
        "status": invoice.status.value,
        "issue_date": invoice.issue_date.isoformat(),
        "due_date": invoice.due_date.isoformat(),
        "subtotal": float(invoice.subtotal),
        "tax_rate": float(invoice.tax_rate),
        "tax_amount": float(invoice.tax_amount),
        "discount_amount": float(invoice.discount_amount),
        "total": float(invoice.total),
        "amount_paid": float(invoice.amount_paid),
        "amount_due": float(invoice.amount_due),
        "notes": invoice.notes,
        "terms": invoice.terms,
        "sent_at": invoice.sent_at.isoformat() if invoice.sent_at else None,
        "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
        "created_at": invoice.created_at.isoformat(),
        "updated_at": invoice.updated_at.isoformat() if invoice.updated_at else None,
    }
    if include_related:
        d["line_items"] = [_line_item_to_dict(li) for li in invoice.line_items]
        d["payments"] = [_payment_to_dict(p) for p in invoice.payments]
    return d


async def _fetch_client_name(invoice: Invoice, db: AsyncSession) -> str | None:
    result = await db.execute(select(Client.name).where(Client.id == invoice.client_id))
    return result.scalar_one_or_none()


async def _get_invoice_or_404(
    invoice_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
    load_related: bool = False,
) -> Invoice:
    q = select(Invoice).where(
        Invoice.id == invoice_id,
        Invoice.tenant_id == tenant_id,
        Invoice.deleted_at.is_(None),
    )
    if load_related:
        q = q.options(
            selectinload(Invoice.line_items),
            selectinload(Invoice.payments),
        )
    result = await db.execute(q)
    invoice = result.scalar_one_or_none()
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return invoice


# --------------------------------------------------------------------------- #
# GET / — list invoices
# --------------------------------------------------------------------------- #

@router.get(
    "/",
    response_model=PaginatedResponse[InvoiceListResponse],
    dependencies=[Depends(require_permission("invoices", "read"))],
)
async def list_invoices(
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    client_id: Annotated[uuid.UUID | None, Query()] = None,
    inv_status: Annotated[str | None, Query(alias="status")] = None,
    date_from: Annotated[str | None, Query(description="ISO date YYYY-MM-DD")] = None,
    date_to: Annotated[str | None, Query(description="ISO date YYYY-MM-DD")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    """Return a paginated, filtered list of invoices."""
    filters = [
        Invoice.tenant_id == tenant_id,
        Invoice.deleted_at.is_(None),
    ]
    if client_id:
        filters.append(Invoice.client_id == client_id)
    if inv_status:
        try:
            filters.append(Invoice.status == InvoiceStatus(inv_status))
        except ValueError as err:
            raise HTTPException(
                status_code=422, detail=f"Invalid status: {inv_status}"
            ) from err
    if date_from:
        filters.append(Invoice.issue_date >= datetime.fromisoformat(date_from))
    if date_to:
        filters.append(Invoice.issue_date <= datetime.fromisoformat(date_to + "T23:59:59"))

    combined = and_(*filters)

    total = (
        await db.execute(select(func.count()).select_from(Invoice).where(combined))
    ).scalar_one()

    offset = (page - 1) * page_size
    rows = (
        await db.execute(
            select(Invoice)
            .where(combined)
            .options(selectinload(Invoice.payments))
            .order_by(Invoice.issue_date.desc())
            .offset(offset)
            .limit(page_size)
        )
    ).scalars().all()

    # Batch-fetch client names to avoid N+1
    client_ids = {inv.client_id for inv in rows if inv.client_id}
    client_names: dict[uuid.UUID, str] = {}
    if client_ids:
        cn_result = await db.execute(
            select(Client.id, Client.name).where(Client.id.in_(client_ids))
        )
        client_names = {row.id: row.name for row in cn_result}

    pages = math.ceil(total / page_size) if page_size > 0 else 0
    return {
        "items": [
            _invoice_to_dict(inv, client_name=client_names.get(inv.client_id))
            for inv in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


# --------------------------------------------------------------------------- #
# POST / — create invoice manually
# --------------------------------------------------------------------------- #

@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=InvoiceDetailResponse,
    dependencies=[Depends(require_permission("invoices", "write"))],
)
async def create_invoice(
    payload: dict,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Create a draft invoice manually."""
    client_id_val = payload.get("client_id")
    if not client_id_val:
        raise HTTPException(status_code=422, detail="client_id is required")
    client_id = uuid.UUID(str(client_id_val))

    due_date_str = payload.get("due_date")
    if not due_date_str:
        raise HTTPException(status_code=422, detail="due_date is required")

    try:
        due_date = date.fromisoformat(str(due_date_str))
    except ValueError as err:
        raise HTTPException(
            status_code=422, detail="due_date must be ISO format YYYY-MM-DD"
        ) from err

    tax_rate = Decimal(str(payload.get("tax_rate", "0")))

    service = InvoiceService(db)
    invoice_number = await service._generate_invoice_number(tenant_id)

    now = datetime.now(tz=UTC)
    invoice = Invoice(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        invoice_number=invoice_number,
        client_id=client_id,
        status=InvoiceStatus.draft,
        issue_date=now,
        due_date=datetime(due_date.year, due_date.month, due_date.day, 23, 59, 59, tzinfo=UTC),
        subtotal=Decimal("0.00"),
        tax_rate=tax_rate,
        tax_amount=Decimal("0.00"),
        discount_amount=Decimal(str(payload.get("discount_amount", "0"))),
        total=Decimal("0.00"),
        notes=payload.get("notes"),
        terms=payload.get("terms"),
    )
    db.add(invoice)
    await db.flush()

    # Add any provided line items
    line_items_raw = payload.get("line_items") or []
    for i, li in enumerate(line_items_raw):
        qty = Decimal(str(li.get("quantity", "1")))
        unit_price = Decimal(str(li.get("unit_price", "0")))
        line_total = (qty * unit_price).quantize(Decimal("0.01"))
        item = InvoiceLineItem(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            invoice_id=invoice.id,
            description=li.get("description", ""),
            quantity=qty,
            unit_price=unit_price,
            line_total=line_total,
            sort_order=li.get("sort_order", i),
        )
        db.add(item)

    await db.flush()

    # Re-fetch with eager loading so we can iterate line_items in
    # recalculate_totals without triggering a lazy load in async context.
    invoice = await _get_invoice_or_404(invoice.id, tenant_id, db, load_related=True)
    invoice.recalculate_totals()
    await db.flush()

    # Re-fetch again so server-generated columns (updated_at via onupdate)
    # are populated before _invoice_to_dict reads them.
    # db.refresh(..., [rel_names]) only reloads listed attrs, leaving
    # other expired scalar columns to trigger MissingGreenlet on access.
    invoice = await _get_invoice_or_404(invoice.id, tenant_id, db, load_related=True)

    logger.info(
        "invoice_created_manually",
        tenant_id=str(tenant_id),
        invoice_id=str(invoice.id),
        client_id=str(client_id),
        created_by=str(current_user.id),
    )

    cname = await _fetch_client_name(invoice, db)
    return _invoice_to_dict(invoice, include_related=True, client_name=cname)


# --------------------------------------------------------------------------- #
# POST /from-work-orders — generate invoice from completed work orders
# --------------------------------------------------------------------------- #

@router.post(
    "/from-work-orders",
    status_code=status.HTTP_201_CREATED,
    response_model=InvoiceDetailResponse,
    dependencies=[Depends(require_permission("invoices", "write"))],
)
async def create_invoice_from_work_orders(
    payload: dict,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate an invoice from a list of completed work orders.

    All work orders must:
    - Be in status=completed
    - Belong to the same client
    - Not already be linked to a non-void invoice
    """
    wo_ids_raw = payload.get("work_order_ids")
    if not wo_ids_raw or not isinstance(wo_ids_raw, list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="work_order_ids must be a non-empty list of UUIDs",
        )
    try:
        work_order_ids = [uuid.UUID(str(wid)) for wid in wo_ids_raw]
    except ValueError as err:
        raise HTTPException(
            status_code=422, detail="work_order_ids contains invalid UUIDs"
        ) from err

    due_date_str = payload.get("due_date")
    if not due_date_str:
        raise HTTPException(status_code=422, detail="due_date is required")
    try:
        due_date = date.fromisoformat(str(due_date_str))
    except ValueError as err:
        raise HTTPException(
            status_code=422, detail="due_date must be ISO format YYYY-MM-DD"
        ) from err

    tax_rate = Decimal(str(payload.get("tax_rate", "0")))
    notes = payload.get("notes")

    service = InvoiceService(db)
    invoice = await service.create_from_work_orders(
        tenant_id=tenant_id,
        work_order_ids=work_order_ids,
        due_date=due_date,
        tax_rate=tax_rate,
        notes=notes,
        created_by=current_user.id,
    )

    cname = await _fetch_client_name(invoice, db)
    return _invoice_to_dict(invoice, include_related=True, client_name=cname)


# --------------------------------------------------------------------------- #
# GET /{id} — get invoice with line items and payments
# --------------------------------------------------------------------------- #

@router.get(
    "/{invoice_id}",
    response_model=InvoiceDetailResponse,
    dependencies=[Depends(require_permission("invoices", "read"))],
)
async def get_invoice(
    invoice_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Fetch a single invoice with its line items and payment records."""
    invoice = await _get_invoice_or_404(invoice_id, tenant_id, db, load_related=True)
    cn_result = await db.execute(
        select(Client.name).where(Client.id == invoice.client_id)
    )
    client_name = cn_result.scalar_one_or_none()
    return _invoice_to_dict(invoice, include_related=True, client_name=client_name)


# --------------------------------------------------------------------------- #
# PATCH /{id} — update draft invoice
# --------------------------------------------------------------------------- #

@router.patch(
    "/{invoice_id}",
    response_model=InvoiceDetailResponse,
    dependencies=[Depends(require_permission("invoices", "write"))],
)
async def update_invoice(
    invoice_id: uuid.UUID,
    payload: dict,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Update a draft invoice.
    Returns 409 if the invoice has already been sent or paid.
    """
    invoice = await _get_invoice_or_404(invoice_id, tenant_id, db, load_related=True)

    if invoice.status != InvoiceStatus.draft:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only draft invoices can be edited. Current status: {invoice.status.value}",
        )

    updatable = {"notes", "terms", "discount_amount"}
    for field in updatable:
        if field in payload:
            if field == "discount_amount":
                setattr(invoice, field, Decimal(str(payload[field])))
            else:
                setattr(invoice, field, payload[field])

    if "due_date" in payload:
        try:
            d = date.fromisoformat(str(payload["due_date"]))
            invoice.due_date = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=UTC)
        except ValueError as err:
            raise HTTPException(
                status_code=422, detail="due_date must be ISO format YYYY-MM-DD"
            ) from err

    if "tax_rate" in payload:
        invoice.tax_rate = Decimal(str(payload["tax_rate"]))

    invoice.recalculate_totals()
    await db.flush()

    # Re-fetch so updated_at (server-side onupdate) is loaded synchronously;
    # otherwise _invoice_to_dict triggers a MissingGreenlet on access.
    invoice = await _get_invoice_or_404(invoice_id, tenant_id, db, load_related=True)

    logger.info(
        "invoice_updated",
        tenant_id=str(tenant_id),
        invoice_id=str(invoice_id),
        updated_by=str(current_user.id),
        fields=list(payload.keys()),
    )

    cname = await _fetch_client_name(invoice, db)
    return _invoice_to_dict(invoice, include_related=True, client_name=cname)


# --------------------------------------------------------------------------- #
# POST /{id}/send — mark as sent
# --------------------------------------------------------------------------- #

@router.post(
    "/{invoice_id}/send",
    response_model=InvoiceDetailResponse,
    dependencies=[Depends(require_permission("invoices", "write"))],
)
async def send_invoice(
    invoice_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Mark an invoice as sent and enqueue an email delivery task.
    Only draft invoices may be sent.
    """
    invoice = await _get_invoice_or_404(invoice_id, tenant_id, db, load_related=True)

    if invoice.status not in (InvoiceStatus.draft, InvoiceStatus.sent):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot send invoice with status: {invoice.status.value}",
        )

    invoice.status = InvoiceStatus.sent
    invoice.sent_at = datetime.now(tz=UTC)
    await db.flush()

    # Enqueue email delivery (fire and forget — failure does not roll back the DB update)
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        from app.core.config import settings

        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        await redis.enqueue_job(
            "send_invoice_email",
            str(tenant_id),
            str(invoice_id),
        )
        await redis.close()
    except Exception as exc:
        logger.warning(
            "invoice_email_enqueue_failed",
            invoice_id=str(invoice_id),
            error=str(exc),
        )

    logger.info(
        "invoice_sent",
        tenant_id=str(tenant_id),
        invoice_id=str(invoice_id),
        sent_by=str(current_user.id),
    )

    # Re-fetch so updated_at (server-side onupdate) is loaded synchronously;
    # otherwise _invoice_to_dict triggers a MissingGreenlet on access.
    invoice = await _get_invoice_or_404(invoice_id, tenant_id, db, load_related=True)

    cname = await _fetch_client_name(invoice, db)
    return _invoice_to_dict(invoice, include_related=True, client_name=cname)


# --------------------------------------------------------------------------- #
# POST /{id}/record-payment — record a payment
# --------------------------------------------------------------------------- #

@router.post(
    "/{invoice_id}/record-payment",
    status_code=status.HTTP_201_CREATED,
    response_model=InvoiceDetailResponse,
    dependencies=[Depends(require_permission("invoices", "write"))],
)
async def record_payment(
    invoice_id: uuid.UUID,
    payload: dict,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Record a payment against an invoice.
    Updates amount_paid and adjusts status to partial or paid.
    """
    amount_raw = payload.get("amount")
    if amount_raw is None:
        raise HTTPException(status_code=422, detail="amount is required")
    try:
        amount = Decimal(str(amount_raw))
    except Exception as err:
        raise HTTPException(
            status_code=422, detail="amount must be a valid decimal number"
        ) from err

    payment_date_str = payload.get("payment_date")
    if not payment_date_str:
        raise HTTPException(status_code=422, detail="payment_date is required")
    try:
        payment_date = date.fromisoformat(str(payment_date_str))
    except ValueError as err:
        raise HTTPException(
            status_code=422, detail="payment_date must be ISO format YYYY-MM-DD"
        ) from err

    payment_method = payload.get("payment_method", "other")

    service = InvoiceService(db)
    invoice = await service.record_payment(
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        amount=amount,
        payment_date=payment_date,
        payment_method=payment_method,
        reference_number=payload.get("reference_number"),
        notes=payload.get("notes"),
        recorded_by=current_user.id,
    )

    cname = await _fetch_client_name(invoice, db)
    return _invoice_to_dict(invoice, include_related=True, client_name=cname)


# --------------------------------------------------------------------------- #
# DELETE /{id} — void invoice
# --------------------------------------------------------------------------- #

@router.delete(
    "/{invoice_id}",
    dependencies=[Depends(require_permission("invoices", "write"))],
)
async def void_invoice(
    invoice_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Void an invoice.
    Returns 409 if the invoice is already fully paid.
    """
    invoice = await _get_invoice_or_404(invoice_id, tenant_id, db)

    if invoice.status == InvoiceStatus.paid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot void a fully paid invoice",
        )
    if invoice.status == InvoiceStatus.void:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invoice is already voided",
        )

    invoice.status = InvoiceStatus.void
    await db.flush()

    logger.info(
        "invoice_voided",
        tenant_id=str(tenant_id),
        invoice_id=str(invoice_id),
        voided_by=str(current_user.id),
    )

    return {
        "data": {
            "id": str(invoice.id),
            "status": invoice.status.value,
            "message": "Invoice voided",
        }
    }
