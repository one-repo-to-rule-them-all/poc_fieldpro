"""Integration tests for the /api/v1/locations endpoints."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.models.client import Client
from app.models.location import Location
from app.models.tenant import SubscriptionPlan, Tenant
from app.models.user import User, UserRole

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


async def _seed_location(
    db: AsyncSession,
    tenant: Tenant,
    svc_client: Client,
    name: str = "Site A",
) -> Location:
    loc = Location(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        client_id=svc_client.id,
        name=name,
        address={},
        geofence_radius_meters=100,
        is_active=True,
    )
    db.add(loc)
    await db.flush()
    return loc


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------- #
# Auth enforcement
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_list_locations_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/locations")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_location_requires_auth(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/locations/{uuid.uuid4()}")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# List — shape and scoping
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_list_locations_returns_paginated_shape(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    svc_client = await _seed_client(db, tenant)
    await _seed_location(db, tenant, svc_client, name="Site Alpha")
    await _seed_location(db, tenant, svc_client, name="Site Beta")

    resp = await client.get("/api/v1/locations", headers=_auth(admin_token))
    assert resp.status_code == 200

    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "page_size" in body
    assert "pages" in body

    names = {item["name"] for item in body["items"]}
    assert "Site Alpha" in names
    assert "Site Beta" in names


@pytest.mark.asyncio
async def test_list_locations_item_fields(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    svc_client = await _seed_client(db, tenant)
    seeded = await _seed_location(db, tenant, svc_client, name="Field Check Site")

    resp = await client.get("/api/v1/locations", headers=_auth(admin_token))
    assert resp.status_code == 200

    items = resp.json()["items"]
    item = next((i for i in items if i["id"] == str(seeded.id)), None)
    assert item is not None

    for field in ("id", "name", "client_id", "is_active", "created_at", "geofence_radius_meters"):
        assert field in item, f"missing field: {field}"


@pytest.mark.asyncio
async def test_list_locations_filter_by_client(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    client_a = await _seed_client(db, tenant)
    client_b = await _seed_client(db, tenant)
    loc_a = await _seed_location(db, tenant, client_a, name="A's Site")
    await _seed_location(db, tenant, client_b, name="B's Site")

    resp = await client.get(
        "/api/v1/locations",
        params={"client_id": str(client_a.id)},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    ids = {i["id"] for i in resp.json()["items"]}
    assert str(loc_a.id) in ids
    assert all(i["client_id"] == str(client_a.id) for i in resp.json()["items"])


# --------------------------------------------------------------------------- #
# Create
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_create_location_success(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    svc_client = await _seed_client(db, tenant)

    resp = await client.post(
        "/api/v1/locations",
        json={"name": "New Site", "client_id": str(svc_client.id)},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text

    body = resp.json()
    assert body["name"] == "New Site"
    assert body["client_id"] == str(svc_client.id)
    assert body["is_active"] is True
    assert "id" in body


@pytest.mark.asyncio
async def test_create_location_invalid_client_returns_404(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    resp = await client.post(
        "/api/v1/locations",
        json={"name": "Orphan Site", "client_id": str(uuid.uuid4())},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_location_employee_forbidden(
    client: AsyncClient,
    db: AsyncSession,
    employee_token: str,
    tenant: Tenant,
) -> None:
    svc_client = await _seed_client(db, tenant)
    resp = await client.post(
        "/api/v1/locations",
        json={"name": "Blocked", "client_id": str(svc_client.id)},
        headers=_auth(employee_token),
    )
    assert resp.status_code == 403


# --------------------------------------------------------------------------- #
# Get by ID
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_get_location_success(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    svc_client = await _seed_client(db, tenant)
    seeded = await _seed_location(db, tenant, svc_client, name="Detail Site")

    resp = await client.get(f"/api/v1/locations/{seeded.id}", headers=_auth(admin_token))
    assert resp.status_code == 200

    body = resp.json()
    assert body["id"] == str(seeded.id)
    assert body["name"] == "Detail Site"
    assert "access_instructions" in body
    assert "qr_code_token" in body


@pytest.mark.asyncio
async def test_get_location_not_found(
    client: AsyncClient,
    admin_token: str,
) -> None:
    resp = await client.get(f"/api/v1/locations/{uuid.uuid4()}", headers=_auth(admin_token))
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Update
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_update_location_success(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    svc_client = await _seed_client(db, tenant)
    seeded = await _seed_location(db, tenant, svc_client, name="Old Site Name")

    resp = await client.patch(
        f"/api/v1/locations/{seeded.id}",
        json={"name": "Renamed Site"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed Site"


# --------------------------------------------------------------------------- #
# Soft delete
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_delete_location_success(
    client: AsyncClient,
    db: AsyncSession,
    admin_token: str,
    tenant: Tenant,
) -> None:
    svc_client = await _seed_client(db, tenant)
    seeded = await _seed_location(db, tenant, svc_client)

    resp = await client.delete(
        f"/api/v1/locations/{seeded.id}", headers=_auth(admin_token)
    )
    assert resp.status_code == 204

    get_resp = await client.get(
        f"/api/v1/locations/{seeded.id}", headers=_auth(admin_token)
    )
    assert get_resp.status_code == 404


# --------------------------------------------------------------------------- #
# Cross-tenant isolation
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_cross_tenant_location_hidden(
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

    loc_b = Location(
        id=uuid.uuid4(), tenant_id=tenant_b.id,
        client_id=client_b.id, name="B's Secret Site",
        address={}, geofence_radius_meters=100, is_active=True,
    )
    db.add(loc_b)
    await db.flush()

    token_a = create_access_token({"sub": str(user_a.id)})
    resp = await client.get(
        f"/api/v1/locations/{loc_b.id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 404
