"""
Integration tests for the crew assignment management feature.

Covers:
- Work order list / detail / patch responses include crew_name
- Work order list endpoint filters by crew_id
- Crew detail endpoint embeds member.user info (first_name, last_name, email)
- Add member endpoint embeds user info on the response
- Remove member endpoint embeds user info on the response and soft-deletes
- Duplicate active-membership prevention
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.client import Client
from app.models.crew import Crew, CrewMember, CrewMemberRole
from app.models.location import Location
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.work_order import WorkOrder, WorkOrderStatus

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _seed_client(db: AsyncSession, tenant: Tenant) -> Client:
    c = Client(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Acme Corp",
        code=f"AC-{uuid.uuid4().hex[:6].upper()}",
        billing_address={},
        is_active=True,
    )
    db.add(c)
    await db.flush()
    return c


async def _seed_location(db: AsyncSession, tenant: Tenant, client: Client) -> Location:
    loc = Location(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        client_id=client.id,
        name="HQ",
        address={"street": "1", "city": "X", "state": "TX", "zip": "00000"},
        geofence_radius_meters=200,
        is_active=True,
    )
    db.add(loc)
    await db.flush()
    return loc


async def _seed_crew(
    db: AsyncSession, tenant: Tenant, name: str = "Alpha Crew"
) -> Crew:
    crew = Crew(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name=name,
        code=f"CRW-{uuid.uuid4().hex[:6].upper()}",
        is_active=True,
    )
    db.add(crew)
    await db.flush()
    return crew


async def _seed_user(
    db: AsyncSession,
    tenant: Tenant,
    *,
    first_name: str = "Riley",
    last_name: str = "Stone",
    role: UserRole = UserRole.employee,
) -> User:
    u = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=f"{first_name.lower()}-{uuid.uuid4().hex[:6]}@test.dev",
        hashed_password=get_password_hash("Pass123!"),
        first_name=first_name,
        last_name=last_name,
        role=role,
        is_active=True,
        is_verified=True,
    )
    db.add(u)
    await db.flush()
    return u


async def _seed_work_order(
    db: AsyncSession,
    tenant: Tenant,
    client: Client,
    location: Location,
    *,
    title: str = "Mow lawn",
    crew: Crew | None = None,
) -> WorkOrder:
    wo = WorkOrder(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        title=title,
        client_id=client.id,
        location_id=location.id,
        crew_id=crew.id if crew else None,
        status=WorkOrderStatus.scheduled,
        priority="normal",
        work_type="one_time",
        scheduled_date=datetime.now(UTC) + timedelta(days=1),
    )
    db.add(wo)
    await db.flush()
    return wo


# --------------------------------------------------------------------------- #
# Work order responses include crew_name
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_work_order_list_includes_crew_name(
    client: AsyncClient, db: AsyncSession, admin_token: str, tenant: Tenant
) -> None:
    cli = await _seed_client(db, tenant)
    loc = await _seed_location(db, tenant, cli)
    crew = await _seed_crew(db, tenant, name="Lawn Squad")
    await _seed_work_order(db, tenant, cli, loc, crew=crew)

    resp = await client.get("/api/v1/work-orders", headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text

    items = resp.json()["items"]
    assert items, "expected at least one work order"
    item = items[0]
    assert item["crew_id"] == str(crew.id)
    assert item["crew_name"] == "Lawn Squad"


@pytest.mark.asyncio
async def test_work_order_list_crew_name_null_when_unassigned(
    client: AsyncClient, db: AsyncSession, admin_token: str, tenant: Tenant
) -> None:
    cli = await _seed_client(db, tenant)
    loc = await _seed_location(db, tenant, cli)
    await _seed_work_order(db, tenant, cli, loc, crew=None)

    resp = await client.get("/api/v1/work-orders", headers=_auth(admin_token))
    assert resp.status_code == 200

    item = resp.json()["items"][0]
    assert item["crew_id"] is None
    assert item["crew_name"] is None


@pytest.mark.asyncio
async def test_work_order_detail_includes_crew_name(
    client: AsyncClient, db: AsyncSession, admin_token: str, tenant: Tenant
) -> None:
    cli = await _seed_client(db, tenant)
    loc = await _seed_location(db, tenant, cli)
    crew = await _seed_crew(db, tenant, name="Night Shift")
    wo = await _seed_work_order(db, tenant, cli, loc, crew=crew)

    resp = await client.get(
        f"/api/v1/work-orders/{wo.id}", headers=_auth(admin_token)
    )
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["crew_id"] == str(crew.id)
    assert body["crew_name"] == "Night Shift"


# --------------------------------------------------------------------------- #
# crew_id filter on the list endpoint
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_work_order_list_filters_by_crew_id(
    client: AsyncClient, db: AsyncSession, admin_token: str, tenant: Tenant
) -> None:
    cli = await _seed_client(db, tenant)
    loc = await _seed_location(db, tenant, cli)
    crew_a = await _seed_crew(db, tenant, name="A")
    crew_b = await _seed_crew(db, tenant, name="B")

    await _seed_work_order(db, tenant, cli, loc, title="WO-A", crew=crew_a)
    await _seed_work_order(db, tenant, cli, loc, title="WO-B", crew=crew_b)
    await _seed_work_order(db, tenant, cli, loc, title="WO-None", crew=None)

    resp = await client.get(
        "/api/v1/work-orders",
        params={"crew_id": str(crew_a.id)},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    titles = {item["title"] for item in resp.json()["items"]}
    assert titles == {"WO-A"}


# --------------------------------------------------------------------------- #
# PATCH response reflects new crew assignment
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_patch_work_order_returns_updated_crew_name(
    client: AsyncClient, db: AsyncSession, admin_token: str, tenant: Tenant
) -> None:
    cli = await _seed_client(db, tenant)
    loc = await _seed_location(db, tenant, cli)
    crew_old = await _seed_crew(db, tenant, name="Old Crew")
    crew_new = await _seed_crew(db, tenant, name="New Crew")
    wo = await _seed_work_order(db, tenant, cli, loc, crew=crew_old)

    resp = await client.patch(
        f"/api/v1/work-orders/{wo.id}",
        json={"crew_id": str(crew_new.id)},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["crew_id"] == str(crew_new.id)
    assert body["crew_name"] == "New Crew"


@pytest.mark.asyncio
async def test_patch_work_order_unassign_crew(
    client: AsyncClient, db: AsyncSession, admin_token: str, tenant: Tenant
) -> None:
    cli = await _seed_client(db, tenant)
    loc = await _seed_location(db, tenant, cli)
    crew = await _seed_crew(db, tenant)
    wo = await _seed_work_order(db, tenant, cli, loc, crew=crew)

    resp = await client.patch(
        f"/api/v1/work-orders/{wo.id}",
        json={"crew_id": None},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["crew_id"] is None
    assert body["crew_name"] is None


# --------------------------------------------------------------------------- #
# Crew detail embeds user info on members
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_crew_detail_embeds_member_user_info(
    client: AsyncClient, db: AsyncSession, admin_token: str, tenant: Tenant
) -> None:
    crew = await _seed_crew(db, tenant)
    user = await _seed_user(db, tenant, first_name="Casey", last_name="Lin")
    member = CrewMember(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        crew_id=crew.id,
        user_id=user.id,
        role=CrewMemberRole.lead,
        joined_at=datetime.now(UTC),
    )
    db.add(member)
    await db.flush()

    resp = await client.get(
        f"/api/v1/crews/{crew.id}", headers=_auth(admin_token)
    )
    assert resp.status_code == 200, resp.text

    members = resp.json()["members"]
    assert len(members) == 1
    m = members[0]
    assert m["user_id"] == str(user.id)
    assert m["role"] == "lead"
    assert m["user"] is not None
    assert m["user"]["first_name"] == "Casey"
    assert m["user"]["last_name"] == "Lin"
    assert m["user"]["email"] == user.email


# --------------------------------------------------------------------------- #
# Add member endpoint
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_add_crew_member_returns_user_info(
    client: AsyncClient, db: AsyncSession, admin_token: str, tenant: Tenant
) -> None:
    crew = await _seed_crew(db, tenant)
    user = await _seed_user(db, tenant, first_name="Dana", last_name="Park")

    resp = await client.post(
        f"/api/v1/crews/{crew.id}/members",
        json={"user_id": str(user.id), "role": "member"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text

    body = resp.json()
    assert body["user_id"] == str(user.id)
    assert body["role"] == "member"
    assert body["is_active"] is True
    assert body["user"] is not None
    assert body["user"]["first_name"] == "Dana"
    assert body["user"]["email"] == user.email


@pytest.mark.asyncio
async def test_add_duplicate_active_member_returns_409(
    client: AsyncClient, db: AsyncSession, admin_token: str, tenant: Tenant
) -> None:
    crew = await _seed_crew(db, tenant)
    user = await _seed_user(db, tenant)

    first = await client.post(
        f"/api/v1/crews/{crew.id}/members",
        json={"user_id": str(user.id)},
        headers=_auth(admin_token),
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/v1/crews/{crew.id}/members",
        json={"user_id": str(user.id)},
        headers=_auth(admin_token),
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_add_member_unknown_user_returns_404(
    client: AsyncClient, db: AsyncSession, admin_token: str, tenant: Tenant
) -> None:
    crew = await _seed_crew(db, tenant)
    resp = await client.post(
        f"/api/v1/crews/{crew.id}/members",
        json={"user_id": str(uuid.uuid4())},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Remove member endpoint
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_remove_crew_member_returns_user_info_and_soft_deletes(
    client: AsyncClient, db: AsyncSession, admin_token: str, tenant: Tenant
) -> None:
    crew = await _seed_crew(db, tenant)
    user = await _seed_user(db, tenant, first_name="Sam", last_name="Diaz")
    add = await client.post(
        f"/api/v1/crews/{crew.id}/members",
        json={"user_id": str(user.id)},
        headers=_auth(admin_token),
    )
    assert add.status_code == 201

    remove = await client.delete(
        f"/api/v1/crews/{crew.id}/members/{user.id}",
        headers=_auth(admin_token),
    )
    assert remove.status_code == 200, remove.text

    body = remove.json()
    assert body["user_id"] == str(user.id)
    assert body["is_active"] is False
    assert body["left_at"] is not None
    assert body["user"] is not None
    assert body["user"]["first_name"] == "Sam"

    # Crew detail no longer lists the (now-inactive) member
    detail = await client.get(
        f"/api/v1/crews/{crew.id}", headers=_auth(admin_token)
    )
    assert detail.status_code == 200
    user_ids = [m["user_id"] for m in detail.json()["members"]]
    assert str(user.id) not in user_ids


@pytest.mark.asyncio
async def test_remove_nonexistent_member_returns_404(
    client: AsyncClient, db: AsyncSession, admin_token: str, tenant: Tenant
) -> None:
    crew = await _seed_crew(db, tenant)
    resp = await client.delete(
        f"/api/v1/crews/{crew.id}/members/{uuid.uuid4()}",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404
