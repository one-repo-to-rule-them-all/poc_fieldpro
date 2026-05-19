"""Integration tests for the /api/v1/invoices endpoints."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import uuid

from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.models.client import Client
from app.models.invoice import Invoice, InvoiceStatus
from app.models.location import Location
from app.models.tenant import SubscriptionPlan, Tenant
from app.models.user import User, UserRole
from app.models.work_order import WorkOrder, WorkOrderStatus

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

async def _seed_client(db: AsyncSession, tenant: Tenant) -> Client:
    c = Client(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name=f"Client-{uuid.uuid4().hex[:6]}",
        code=f"CLI-{uuid.uuid4().hex[:6].upper()}",
        billing_address={},
        is_active=True,
    )
    db.add(c)
    await db.flush()
    return c


def _due_date_str(days: int = 30) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


async def _create_invoice_via_api(
    client: AsyncClient,
    token: str,
    client_id: uuid.UUID,
    due_date: str | None = None,
) -> Response:  # type: ignore[name-defined]
    return await client.post(
        "/api/v1/invoices/",
        json={"client_id": str(client_id), "due_date": due_date or _due_date_str()},
        headers={"Authorization": f"Bearer {token}"},
    )


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------- #
# Auth enforcement
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_list_invoices_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/invoices/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_invoice_requires_auth(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/invoices/{uuid.uuid4()}")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# RBAC
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_create_invoice_employee_forbidden(
    client: AsyncClient,
    db: AsyncSession,
    employee_token: str,
    tenant: Tenant,
) -> None:
    svc_client = await _seed_client(db, tenant)
    resp = await _create_invoice_via_api(client, employee_token, svc_client.id)
    assert resp.status_code == 403


# --------------------------------------------------------------------------- #
# List — shape and fields
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_list_invoices_returns_paginated_shape(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    svc_client = await _seed_client(db, tenant)
    await _create_invoice_via_api(client, admin_token, svc_client.id)
    await _create_invoice_via_api(client, admin_token, svc_client.id)

    resp = await client.get("/api/v1/invoices/", headers=_auth(admin_token))
    assert resp.status_code == 200

    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "page_size" in body
    assert "pages" in body
    assert body["total"] >= 2


@pytest.mark.asyncio
async def test_list_invoices_item_fields(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    svc_client = await _seed_client(db, tenant)
    create_resp = await _create_invoice_via_api(client, admin_token, svc_client.id)
    assert create_resp.status_code == 201
    invoice_id = create_resp.json()["id"]

    resp = await client.get("/api/v1/invoices/", headers=_auth(admin_token))
    items = resp.json()["items"]
    item = next((i for i in items if i["id"] == invoice_id), None)
    assert item is not None

    for field in (
        "id", "invoice_number", "client_id", "status",
        "total", "amount_paid", "amount_due", "created_at",
    ):
        assert field in item, f"missing field: {field}"


@pytest.mark.asyncio
async def test_list_invoices_filter_by_status(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    svc_client = await _seed_client(db, tenant)
    create_resp = await _create_invoice_via_api(client, admin_token, svc_client.id)
    assert create_resp.status_code == 201

    resp = await client.get(
        "/api/v1/invoices/",
        params={"status": "draft"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    statuses = {i["status"] for i in resp.json()["items"]}
    assert statuses <= {"draft"}


# --------------------------------------------------------------------------- #
# Create
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_create_invoice_success(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    svc_client = await _seed_client(db, tenant)
    resp = await _create_invoice_via_api(client, admin_token, svc_client.id)
    assert resp.status_code == 201, resp.text

    body = resp.json()
    assert body["client_id"] == str(svc_client.id)
    assert body["status"] == "draft"
    assert "invoice_number" in body
    assert "line_items" in body
    assert "payments" in body
    # _invoice_to_dict casts Decimal columns to float for JSON; an empty
    # invoice has subtotal/total = 0.0 (not the "0.00" string the test
    # originally asserted before that cast was added).
    assert body["total"] == 0.0


# --------------------------------------------------------------------------- #
# Regression — MissingGreenlet bug fix on write endpoints
#
# After a flush, server-generated columns (updated_at via onupdate=func.now())
# are marked expired. db.refresh(invoice, [rel_names]) only reloads the listed
# relationships — accessing other expired scalar columns synchronously inside
# the response serializer triggers a sync SELECT in async context, raising
# sqlalchemy.exc.MissingGreenlet. The fix is a fresh SELECT + selectinload
# after every flush. These tests pin the contract.
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_create_invoice_with_line_items_returns_201(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    """POST /invoices/ with line items triggered MissingGreenlet before the fix.

    A non-empty line_items list forces recalculate_totals → UPDATE invoice →
    onupdate fires for updated_at → expired column accessed by _invoice_to_dict.
    """
    svc_client = await _seed_client(db, tenant)
    resp = await client.post(
        "/api/v1/invoices/",
        json={
            "client_id": str(svc_client.id),
            "due_date": _due_date_str(),
            "tax_rate": "0.0825",
            "line_items": [
                {"description": "Janitorial — May 2026", "quantity": 8, "unit_price": 55},
                {"description": "Supplies", "quantity": 1, "unit_price": 42.5},
            ],
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(body["line_items"]) == 2
    # 8 * 55 + 1 * 42.5 = 482.50; tax = 482.50 * 0.0825 = 39.81 (rounded);
    # total = 522.31. We assert the relationships are present and not zero —
    # exact rounding is exercised in unit tests, not here.
    assert Decimal(body["subtotal"]) == Decimal("482.50")
    assert Decimal(body["total"]) > Decimal("482.50")
    assert "updated_at" in body  # column exposed without crashing


@pytest.mark.asyncio
async def test_record_payment_returns_201(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
    admin_user: User,
) -> None:
    """POST /invoices/:id/record-payment exercises InvoiceService.record_payment,
    which flushes a payment row + an invoice status update. The follow-up
    db.refresh(invoice, [rel_names]) used to leave updated_at expired."""
    svc_client = await _seed_client(db, tenant)
    invoice = Invoice(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        invoice_number=f"INV-{uuid.uuid4().hex[:6].upper()}",
        client_id=svc_client.id,
        status=InvoiceStatus.sent,
        issue_date=datetime.now(tz=UTC),
        due_date=datetime.now(tz=UTC) + timedelta(days=30),
        subtotal=Decimal("100.00"),
        tax_rate=Decimal("0"),
        tax_amount=Decimal("0"),
        discount_amount=Decimal("0"),
        total=Decimal("100.00"),
    )
    db.add(invoice)
    await db.flush()

    resp = await client.post(
        f"/api/v1/invoices/{invoice.id}/record-payment",
        json={
            "amount": "60.00",
            "payment_date": date.today().isoformat(),
            "payment_method": "check",
            "reference_number": "1234",
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "partial"
    assert Decimal(body["amount_paid"]) == Decimal("60.00")
    assert Decimal(body["amount_due"]) == Decimal("40.00")

    # A second payment that closes the balance should mark it paid.
    resp2 = await client.post(
        f"/api/v1/invoices/{invoice.id}/record-payment",
        json={
            "amount": "40.00",
            "payment_date": date.today().isoformat(),
            "payment_method": "check",
        },
        headers=_auth(admin_token),
    )
    assert resp2.status_code == 201, resp2.text
    assert resp2.json()["status"] == "paid"


@pytest.mark.asyncio
async def test_create_invoice_from_work_orders_returns_201(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    """POST /invoices/from-work-orders exercises InvoiceService.create_from_work_orders.
    Same expired-column hazard as the manual create flow."""
    svc_client = await _seed_client(db, tenant)

    location = Location(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        client_id=svc_client.id,
        name="Main office",
        address={"street": "1 Test Way", "city": "Austin", "state": "TX", "zip": "78701"},
        is_active=True,
    )
    db.add(location)
    await db.flush()

    wo = WorkOrder(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        title="Weekly clean",
        client_id=svc_client.id,
        location_id=location.id,
        status=WorkOrderStatus.completed,
        actual_hours=Decimal("4.00"),
    )
    db.add(wo)
    await db.flush()

    resp = await client.post(
        "/api/v1/invoices/from-work-orders",
        json={
            "work_order_ids": [str(wo.id)],
            "due_date": _due_date_str(),
            "tax_rate": "0",
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(body["line_items"]) == 1
    assert body["line_items"][0]["work_order_id"] == str(wo.id)


# --------------------------------------------------------------------------- #
# Get by ID
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_get_invoice_success(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    svc_client = await _seed_client(db, tenant)
    create_resp = await _create_invoice_via_api(client, admin_token, svc_client.id)
    assert create_resp.status_code == 201
    invoice_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/invoices/{invoice_id}", headers=_auth(admin_token))
    assert resp.status_code == 200

    body = resp.json()
    assert body["id"] == invoice_id
    assert "line_items" in body
    assert "payments" in body


@pytest.mark.asyncio
async def test_get_invoice_not_found(
    client: AsyncClient,
    admin_token: str,
) -> None:
    resp = await client.get(f"/api/v1/invoices/{uuid.uuid4()}", headers=_auth(admin_token))
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Status transition: draft → sent → (record payment) → paid
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_invoice_send_marks_sent(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    svc_client = await _seed_client(db, tenant)
    create_resp = await _create_invoice_via_api(client, admin_token, svc_client.id)
    assert create_resp.status_code == 201
    invoice_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/invoices/{invoice_id}/send",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "sent"


@pytest.mark.asyncio
async def test_invoice_cannot_send_already_paid(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
    admin_user: User,
) -> None:
    svc_client = await _seed_client(db, tenant)

    from datetime import datetime
    from decimal import Decimal

    invoice = Invoice(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        invoice_number=f"INV-{uuid.uuid4().hex[:6].upper()}",
        client_id=svc_client.id,
        status=InvoiceStatus.paid,
        issue_date=datetime.now(tz=UTC),
        due_date=datetime.now(tz=UTC) + timedelta(days=30),
        subtotal=Decimal("100.00"),
        tax_rate=Decimal("0"),
        tax_amount=Decimal("0"),
        discount_amount=Decimal("0"),
        total=Decimal("100.00"),
    )
    db.add(invoice)
    await db.flush()

    resp = await client.post(
        f"/api/v1/invoices/{invoice.id}/send",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 409


# --------------------------------------------------------------------------- #
# Void invoice
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_void_invoice_success(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    svc_client = await _seed_client(db, tenant)
    create_resp = await _create_invoice_via_api(client, admin_token, svc_client.id)
    invoice_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/v1/invoices/{invoice_id}", headers=_auth(admin_token))
    assert resp.status_code == 200
    # void_invoice returns the envelope shape {"data": {...}} — the status
    # is nested under "data", not at the top level.
    assert resp.json()["data"]["status"] == "void"


# --------------------------------------------------------------------------- #
# Cross-tenant isolation
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_cross_tenant_invoice_hidden(
    client: AsyncClient,
    db: AsyncSession,
) -> None:
    plan = SubscriptionPlan(
        id=uuid.uuid4(), name=f"Plan-{uuid.uuid4().hex[:4]}",
        price_monthly=0, price_yearly=0, max_users=5,
        max_locations=10, features={}, is_active=True,
    )
    db.add(plan)

    tenant_a = Tenant(
        id=uuid.uuid4(), name="Tenant A",
        slug=f"tenant-a-{uuid.uuid4().hex[:6]}", settings={}, is_active=True,
    )
    tenant_b = Tenant(
        id=uuid.uuid4(), name="Tenant B",
        slug=f"tenant-b-{uuid.uuid4().hex[:6]}", settings={}, is_active=True,
    )
    db.add(tenant_a)
    db.add(tenant_b)
    await db.flush()

    user_a = User(
        id=uuid.uuid4(), tenant_id=tenant_a.id,
        email=f"a-{uuid.uuid4().hex[:6]}@a.test",
        hashed_password=get_password_hash("Pass123!"),
        first_name="A", last_name="A",
        role=UserRole.tenant_admin, is_active=True,
    )
    db.add(user_a)

    client_b = Client(
        id=uuid.uuid4(), tenant_id=tenant_b.id,
        name="B Corp", code=f"BC-{uuid.uuid4().hex[:6].upper()}",
        billing_address={}, is_active=True,
    )
    db.add(client_b)
    await db.flush()

    from datetime import datetime
    from decimal import Decimal

    invoice_b = Invoice(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        invoice_number=f"INV-{uuid.uuid4().hex[:6].upper()}",
        client_id=client_b.id,
        status=InvoiceStatus.draft,
        issue_date=datetime.now(tz=UTC),
        due_date=datetime.now(tz=UTC) + timedelta(days=30),
        subtotal=Decimal("0"),
        tax_rate=Decimal("0"),
        tax_amount=Decimal("0"),
        discount_amount=Decimal("0"),
        total=Decimal("0"),
    )
    db.add(invoice_b)
    await db.flush()

    token_a = create_access_token({"sub": str(user_a.id)})
    resp = await client.get(
        f"/api/v1/invoices/{invoice_b.id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 404
