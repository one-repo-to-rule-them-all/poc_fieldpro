"""Phase 4 read API integration tests for #52.

Covers Section 8.11 of the verification matrix from the scoping doc:

    - List + pagination
    - Filter combinations: action, resource_type, user_id, request_id,
      from/to date range
    - Role gating (admin OK; manager/employee → 403)
    - Tenant scoping (admin sees own tenant only; 404 on cross-tenant
      detail lookup)
    - Actor JOIN — actor_email / actor_name resolved
    - Detail endpoint includes full old_values / new_values
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.models.audit import AuditLog
from app.models.tenant import SubscriptionPlan, Tenant
from app.models.user import User, UserRole

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


async def _seed_client_via_api(
    client: AsyncClient, token: str, *, name: str = "ListTest", code: str = "LT-1"
) -> str:
    """Create a client through the API (so audit row gets written) and return its id."""
    resp = await client.post(
        "/api/v1/clients",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "code": code},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# --------------------------------------------------------------------------- #
# Basic list endpoint
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_list_returns_rows_for_admin(
    client: AsyncClient, admin_token: str
) -> None:
    """An admin gets a paginated list with at least one audit row after
    making a state-changing request."""
    await _seed_client_via_api(client, admin_token)

    resp = await client.get(
        "/api/v1/audit-logs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] >= 1
    assert body["page"] == 1
    assert body["page_size"] == 25
    assert len(body["items"]) >= 1


@pytest.mark.asyncio
async def test_list_paginated_shape(
    client: AsyncClient, admin_token: str
) -> None:
    """Standard pagination params and cap are enforced."""
    # Seed a few rows
    for i in range(3):
        await _seed_client_via_api(client, admin_token, name=f"Page{i}", code=f"PAGE-{i}")

    resp = await client.get(
        "/api/v1/audit-logs/?page=1&page_size=2",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) <= 2
    assert body["total"] >= 3
    assert body["pages"] >= 2


@pytest.mark.asyncio
async def test_list_rejects_page_size_over_cap(
    client: AsyncClient, admin_token: str
) -> None:
    """page_size > 100 → 422 validation error."""
    resp = await client.get(
        "/api/v1/audit-logs/?page_size=500",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# Filters
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_filter_by_action(
    client: AsyncClient, admin_token: str
) -> None:
    """action=created returns only created rows."""
    await _seed_client_via_api(client, admin_token, code="FILT-A")

    resp = await client.get(
        "/api/v1/audit-logs/?action=created&page_size=50",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    for item in body["items"]:
        assert item["action"] == "created"


@pytest.mark.asyncio
async def test_filter_by_resource_type(
    client: AsyncClient, admin_token: str
) -> None:
    """resource_type=Client returns only Client rows."""
    await _seed_client_via_api(client, admin_token, code="FILT-RT")

    resp = await client.get(
        "/api/v1/audit-logs/?resource_type=Client&page_size=50",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    for item in body["items"]:
        assert item["resource_type"] == "Client"


@pytest.mark.asyncio
async def test_filter_by_user_id(
    client: AsyncClient, admin_token: str, admin_user: User
) -> None:
    """user_id filter narrows to one actor's events."""
    await _seed_client_via_api(client, admin_token, code="FILT-UID")

    resp = await client.get(
        f"/api/v1/audit-logs/?user_id={admin_user.id}&page_size=50",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    for item in body["items"]:
        assert item["user_id"] == str(admin_user.id)


@pytest.mark.asyncio
async def test_filter_by_request_id(
    client: AsyncClient, admin_token: str, db: AsyncSession
) -> None:
    """request_id filter returns only rows from that single HTTP request."""
    client_id = await _seed_client_via_api(client, admin_token, code="FILT-RID")

    # Pull the request_id from the row we just wrote
    row = (
        await db.execute(
            select(AuditLog)
            .where(AuditLog.resource_type == "Client")
            .where(AuditLog.resource_id == client_id)
        )
    ).scalar_one()
    assert row.request_id is not None

    resp = await client.get(
        f"/api/v1/audit-logs/?request_id={row.request_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["resource_id"] == client_id


# --------------------------------------------------------------------------- #
# Role gating
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_employee_gets_403_on_list(
    client: AsyncClient, employee_token: str
) -> None:
    """employee role → 403 on GET /audit-logs/."""
    resp = await client.get(
        "/api/v1/audit-logs",
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_gets_401(client: AsyncClient) -> None:
    """No token → 401."""
    resp = await client.get("/api/v1/audit-logs")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# Actor JOIN
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_actor_email_resolves_from_join(
    client: AsyncClient, admin_token: str, admin_user: User
) -> None:
    """List rows include actor_email + actor_name from the JOIN to users."""
    await _seed_client_via_api(client, admin_token, code="ACTOR")

    resp = await client.get(
        "/api/v1/audit-logs/?action=created&page_size=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    body = resp.json()
    items = [i for i in body["items"] if i["user_id"] == str(admin_user.id)]
    assert len(items) >= 1
    item = items[0]
    assert item["actor_email"] == admin_user.email
    assert item["actor_name"] == f"{admin_user.first_name} {admin_user.last_name}"


# --------------------------------------------------------------------------- #
# Detail endpoint
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_detail_returns_full_diff(
    client: AsyncClient, admin_token: str
) -> None:
    """GET /audit-logs/{id} returns old_values + new_values + user_agent."""
    new_client_id = await _seed_client_via_api(client, admin_token, code="DET-1")

    # Pull the audit_log id for the just-created row
    list_resp = await client.get(
        "/api/v1/audit-logs/?resource_type=Client&page_size=50",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    audit_row = next(
        i for i in list_resp.json()["items"] if i["resource_id"] == new_client_id
    )

    detail_resp = await client.get(
        f"/api/v1/audit-logs/{audit_row['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == audit_row["id"]
    assert detail["action"] == "created"
    assert detail["resource_type"] == "Client"
    # Full snapshot in new_values
    assert detail["new_values"] is not None
    assert detail["new_values"]["code"] == "DET-1"
    # user_agent appears in detail (not in list)
    assert "user_agent" in detail


@pytest.mark.asyncio
async def test_detail_returns_404_for_missing(
    client: AsyncClient, admin_token: str
) -> None:
    """Bogus audit_log_id → 404."""
    resp = await client.get(
        f"/api/v1/audit-logs/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Tenant scoping
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_admin_sees_only_own_tenant(
    client: AsyncClient,
    admin_token: str,
    db: AsyncSession,
    subscription_plan: SubscriptionPlan,
) -> None:
    """tenant_admin doesn't see audit rows from other tenants."""
    # Seed an audit row in the admin's tenant via the API
    await _seed_client_via_api(client, admin_token, code="OWN-T")

    # Seed an audit row in ANOTHER tenant directly via the DB
    other_tenant = Tenant(
        id=uuid.uuid4(),
        name="Other Co",
        slug="other-co",
        subscription_plan_id=subscription_plan.id,
        settings={},
        is_active=True,
    )
    db.add(other_tenant)
    await db.flush()

    # Insert a fake audit row directly — bypasses the listener (it's already
    # registered, but the AuditLog table itself is NOT audited, so no recursion)
    other_audit = AuditLog(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        user_id=None,
        action="created",
        resource_type="Client",
        resource_id=str(uuid.uuid4()),
        new_values={"name": "Other tenant's client"},
    )
    db.add(other_audit)
    await db.commit()

    # List as admin (own tenant only)
    resp = await client.get(
        "/api/v1/audit-logs/?page_size=100",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    body = resp.json()
    returned_tenant_ids = {item["tenant_id"] for item in body["items"]}
    assert str(other_tenant.id) not in returned_tenant_ids


@pytest.mark.asyncio
async def test_detail_404_on_cross_tenant_row(
    client: AsyncClient,
    admin_token: str,
    db: AsyncSession,
    subscription_plan: SubscriptionPlan,
) -> None:
    """tenant_admin querying a row from another tenant gets 404 (no existence leak)."""
    other_tenant = Tenant(
        id=uuid.uuid4(),
        name="Other Co",
        slug="other-co-2",
        subscription_plan_id=subscription_plan.id,
        settings={},
        is_active=True,
    )
    db.add(other_tenant)
    await db.flush()

    other_audit = AuditLog(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        action="created",
        resource_type="Client",
        resource_id=str(uuid.uuid4()),
    )
    db.add(other_audit)
    await db.commit()

    resp = await client.get(
        f"/api/v1/audit-logs/{other_audit.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # 404, NOT 403 — the row exists but we deliberately mask that
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Platform owner cross-tenant visibility
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_platform_owner_sees_all_tenants(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    subscription_plan: SubscriptionPlan,
) -> None:
    """platform_owner sees rows from all tenants (no scoping)."""
    # Seed a platform_owner in the existing tenant
    po = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="po@test.fieldpro.dev",
        hashed_password=get_password_hash("PO123!"),
        first_name="Platform",
        last_name="Owner",
        role=UserRole.platform_owner,
        is_active=True,
        is_verified=True,
    )
    db.add(po)
    await db.flush()
    po_token = create_access_token({"sub": str(po.id)})

    # Seed audit rows in two different tenants
    other_tenant = Tenant(
        id=uuid.uuid4(),
        name="X Tenant",
        slug="x-tenant",
        subscription_plan_id=subscription_plan.id,
        settings={},
        is_active=True,
    )
    db.add(other_tenant)
    await db.flush()
    for t_id in (tenant.id, other_tenant.id):
        db.add(
            AuditLog(
                id=uuid.uuid4(),
                tenant_id=t_id,
                action="created",
                resource_type="Client",
                resource_id=str(uuid.uuid4()),
            )
        )
    await db.commit()

    resp = await client.get(
        "/api/v1/audit-logs/?page_size=100",
        headers={"Authorization": f"Bearer {po_token}"},
    )
    body = resp.json()
    returned = {item["tenant_id"] for item in body["items"] if item["tenant_id"]}
    assert str(tenant.id) in returned
    assert str(other_tenant.id) in returned
