"""Integration tests for the /api/v1/clients endpoints."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.models.client import Client
from app.models.tenant import SubscriptionPlan, Tenant
from app.models.user import User, UserRole

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

async def _seed_client(
    db: AsyncSession,
    tenant: Tenant,
    name: str = "ACME Corp",
    code: str | None = None,
) -> Client:
    c = Client(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name=name,
        code=code or f"ACME-{uuid.uuid4().hex[:6].upper()}",
        billing_address={},
        is_active=True,
    )
    db.add(c)
    await db.flush()
    return c


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------- #
# Auth enforcement
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_list_clients_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/clients")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_client_requires_auth(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/clients/{uuid.uuid4()}")
    assert response.status_code == 401


# --------------------------------------------------------------------------- #
# List — shape and tenant scoping
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_list_clients_returns_paginated_shape(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    await _seed_client(db, tenant, name="Alpha")
    await _seed_client(db, tenant, name="Beta")

    resp = await client.get("/api/v1/clients", headers=_auth(admin_token))
    assert resp.status_code == 200

    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "page_size" in body
    assert "pages" in body

    names = {item["name"] for item in body["items"]}
    assert "Alpha" in names
    assert "Beta" in names


@pytest.mark.asyncio
async def test_list_clients_item_fields(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    seeded = await _seed_client(db, tenant, name="Field Check Corp")

    resp = await client.get("/api/v1/clients", headers=_auth(admin_token))
    assert resp.status_code == 200

    items = resp.json()["items"]
    item = next((i for i in items if i["id"] == str(seeded.id)), None)
    assert item is not None, "seeded client not found in list"

    for field in ("id", "name", "code", "is_active", "created_at"):
        assert field in item, f"missing field: {field}"


@pytest.mark.asyncio
async def test_list_clients_search_filter(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    await _seed_client(db, tenant, name="Searchable Inc")
    await _seed_client(db, tenant, name="Other Corp")

    resp = await client.get(
        "/api/v1/clients",
        params={"search": "Searchable"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    names = [i["name"] for i in resp.json()["items"]]
    assert "Searchable Inc" in names
    assert "Other Corp" not in names


# --------------------------------------------------------------------------- #
# Create
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_create_client_success(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    code = f"CLI-{uuid.uuid4().hex[:6].upper()}"
    resp = await client.post(
        "/api/v1/clients",
        json={"name": "New Client", "code": code},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text

    body = resp.json()
    assert body["name"] == "New Client"
    assert body["code"] == code
    assert body["is_active"] is True
    assert "id" in body
    assert "tenant_id" in body


@pytest.mark.asyncio
async def test_create_client_duplicate_code_returns_409(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    seeded = await _seed_client(db, tenant)

    resp = await client.post(
        "/api/v1/clients",
        json={"name": "Another Corp", "code": seeded.code},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_client_invalid_industry_returns_422(
    client: AsyncClient,
    admin_token: str,
) -> None:
    """Invalid industry enum value → clean 422 (not a 500 with a ValueError trace)."""
    resp = await client.post(
        "/api/v1/clients",
        json={"name": "Bad Industry Co", "code": "BAD-IND", "industry": "Healthcare"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 422, resp.text
    # Message should mention the bad value + at least one valid option
    body = resp.json()
    detail = body.get("error", {}).get("message", "") + str(body.get("error", {}).get("detail", ""))
    assert "Healthcare" in detail or "industry" in detail.lower()


@pytest.mark.asyncio
async def test_create_client_employee_forbidden(
    client: AsyncClient,
    db: AsyncSession,
    employee_token: str,
    tenant: Tenant,
) -> None:
    resp = await client.post(
        "/api/v1/clients",
        json={"name": "Blocked", "code": "BLK-001"},
        headers=_auth(employee_token),
    )
    assert resp.status_code == 403


# --------------------------------------------------------------------------- #
# Get by ID
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_get_client_success(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    seeded = await _seed_client(db, tenant, name="Detail Corp")

    resp = await client.get(f"/api/v1/clients/{seeded.id}", headers=_auth(admin_token))
    assert resp.status_code == 200

    body = resp.json()
    assert body["id"] == str(seeded.id)
    assert body["name"] == "Detail Corp"
    assert "location_count" in body


@pytest.mark.asyncio
async def test_get_client_not_found(
    client: AsyncClient,
    admin_token: str,
) -> None:
    resp = await client.get(f"/api/v1/clients/{uuid.uuid4()}", headers=_auth(admin_token))
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Update
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_update_client_success(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    seeded = await _seed_client(db, tenant, name="Old Name")

    resp = await client.patch(
        f"/api/v1/clients/{seeded.id}",
        json={"name": "New Name"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


# --------------------------------------------------------------------------- #
# Cross-tenant isolation
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_cross_tenant_client_hidden(
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
        name="Tenant B Client", code=f"BC-{uuid.uuid4().hex[:6].upper()}",
        billing_address={}, is_active=True,
    )
    db.add(client_b)
    await db.flush()

    token_a = create_access_token({"sub": str(user_a.id)})
    resp = await client.get(
        f"/api/v1/clients/{client_b.id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 404
