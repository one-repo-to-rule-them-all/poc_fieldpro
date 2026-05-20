"""Integration tests for the /api/v1/crews endpoints."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.models.crew import Crew
from app.models.tenant import SubscriptionPlan, Tenant
from app.models.user import User, UserRole

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

async def _seed_crew(
    db: AsyncSession,
    tenant: Tenant,
    name: str = "Alpha Crew",
    code: str | None = None,
) -> Crew:
    c = Crew(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name=name,
        code=code or f"CRW-{uuid.uuid4().hex[:6].upper()}",
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
async def test_list_crews_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/crews")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_crew_requires_auth(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/crews/{uuid.uuid4()}")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# List — shape and scoping
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_list_crews_returns_paginated_shape(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    await _seed_crew(db, tenant, name="Night Shift")
    await _seed_crew(db, tenant, name="Day Shift")

    resp = await client.get("/api/v1/crews", headers=_auth(admin_token))
    assert resp.status_code == 200

    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "page_size" in body
    assert "pages" in body

    names = {item["name"] for item in body["items"]}
    assert "Night Shift" in names
    assert "Day Shift" in names


@pytest.mark.asyncio
async def test_list_crews_item_fields(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    seeded = await _seed_crew(db, tenant, name="Field Crew")

    resp = await client.get("/api/v1/crews", headers=_auth(admin_token))
    assert resp.status_code == 200

    items = resp.json()["items"]
    item = next((i for i in items if i["id"] == str(seeded.id)), None)
    assert item is not None

    for field in ("id", "name", "code", "is_active", "created_at"):
        assert field in item, f"missing field: {field}"


@pytest.mark.asyncio
async def test_list_crews_search_filter(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    await _seed_crew(db, tenant, name="Special Ops")
    await _seed_crew(db, tenant, name="Maintenance")

    resp = await client.get(
        "/api/v1/crews",
        params={"search": "Special"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    names = [i["name"] for i in resp.json()["items"]]
    assert "Special Ops" in names
    assert "Maintenance" not in names


# --------------------------------------------------------------------------- #
# Create
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_create_crew_success(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    code = f"CRW-{uuid.uuid4().hex[:6].upper()}"
    resp = await client.post(
        "/api/v1/crews",
        json={"name": "New Crew", "code": code},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text

    body = resp.json()
    assert body["name"] == "New Crew"
    assert body["code"] == code
    assert body["is_active"] is True
    assert "id" in body
    assert "tenant_id" in body


@pytest.mark.asyncio
async def test_create_crew_duplicate_code_returns_409(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    seeded = await _seed_crew(db, tenant)

    resp = await client.post(
        "/api/v1/crews",
        json={"name": "Another Crew", "code": seeded.code},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_crew_employee_forbidden(
    client: AsyncClient,
    employee_token: str,
) -> None:
    resp = await client.post(
        "/api/v1/crews",
        json={"name": "Blocked", "code": "BLK-001"},
        headers=_auth(employee_token),
    )
    assert resp.status_code == 403


# --------------------------------------------------------------------------- #
# Get by ID
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_get_crew_success(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    seeded = await _seed_crew(db, tenant, name="Detail Crew")

    resp = await client.get(f"/api/v1/crews/{seeded.id}", headers=_auth(admin_token))
    assert resp.status_code == 200

    body = resp.json()
    assert body["id"] == str(seeded.id)
    assert body["name"] == "Detail Crew"
    assert "members" in body


@pytest.mark.asyncio
async def test_get_crew_not_found(
    client: AsyncClient,
    admin_token: str,
) -> None:
    resp = await client.get(f"/api/v1/crews/{uuid.uuid4()}", headers=_auth(admin_token))
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Update
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_update_crew_success(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    seeded = await _seed_crew(db, tenant, name="Old Crew Name")

    resp = await client.patch(
        f"/api/v1/crews/{seeded.id}",
        json={"name": "Renamed Crew"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed Crew"


# --------------------------------------------------------------------------- #
# Soft delete
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_delete_crew_success(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    seeded = await _seed_crew(db, tenant)

    resp = await client.delete(f"/api/v1/crews/{seeded.id}", headers=_auth(admin_token))
    assert resp.status_code == 204

    get_resp = await client.get(f"/api/v1/crews/{seeded.id}", headers=_auth(admin_token))
    assert get_resp.status_code == 404


# --------------------------------------------------------------------------- #
# Cross-tenant isolation
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_cross_tenant_crew_hidden(
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

    crew_b = Crew(
        id=uuid.uuid4(), tenant_id=tenant_b.id,
        name="Secret Crew", code=f"SC-{uuid.uuid4().hex[:6].upper()}",
        is_active=True,
    )
    db.add(crew_b)
    await db.flush()

    token_a = create_access_token({"sub": str(user_a.id)})
    resp = await client.get(
        f"/api/v1/crews/{crew_b.id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 404
