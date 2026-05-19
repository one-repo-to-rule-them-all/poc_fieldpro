"""
Integration tests for /api/v1/analytics/* endpoints.

Focused on the dashboard KPI shape contract and the crew_utilization metric
(redefined in #37 as actual hours from check-ins / scheduled estimated hours).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import uuid

from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.crew import Crew
from app.models.location import Location
from app.models.tenant import Tenant
from app.models.user import User
from app.models.work_order import (
    CheckInMethod,
    Priority,
    WorkOrder,
    WorkOrderCheckIn,
    WorkOrderStatus,
    WorkType,
)

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

async def _seed_client(db: AsyncSession, tenant: Tenant) -> Client:
    c = Client(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Acme Co",
        code=f"AC-{uuid.uuid4().hex[:6].upper()}",
        billing_address={},
        is_active=True,
    )
    db.add(c)
    await db.flush()
    return c


async def _seed_location(
    db: AsyncSession, tenant: Tenant, client_row: Client
) -> Location:
    loc = Location(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        client_id=client_row.id,
        name="Main Site",
        address={"street": "1 Main St", "city": "Testville", "state": "TX", "zip": "00000"},
        geofence_radius_meters=200,
        is_active=True,
    )
    db.add(loc)
    await db.flush()
    return loc


async def _seed_crew(db: AsyncSession, tenant: Tenant, name: str = "Alpha") -> Crew:
    crew = Crew(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name=name,
        code=f"{name[:2].upper()}-{uuid.uuid4().hex[:6].upper()}",
        is_active=True,
    )
    db.add(crew)
    await db.flush()
    return crew


async def _seed_work_order(
    db: AsyncSession,
    tenant: Tenant,
    client_row: Client,
    location: Location,
    *,
    crew: Crew | None,
    estimated_hours: Decimal | None,
    scheduled_date: datetime,
    status: WorkOrderStatus = WorkOrderStatus.scheduled,
) -> WorkOrder:
    wo = WorkOrder(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        client_id=client_row.id,
        location_id=location.id,
        crew_id=crew.id if crew else None,
        title="Test WO",
        status=status,
        priority=Priority.normal,
        work_type=WorkType.one_time,
        scheduled_date=scheduled_date,
        estimated_hours=estimated_hours,
    )
    db.add(wo)
    await db.flush()
    return wo


async def _seed_check_in(
    db: AsyncSession,
    tenant: Tenant,
    work_order: WorkOrder,
    user: User,
    *,
    check_in_time: datetime,
    check_out_time: datetime | None,
) -> WorkOrderCheckIn:
    ci = WorkOrderCheckIn(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        work_order_id=work_order.id,
        user_id=user.id,
        check_in_time=check_in_time,
        check_out_time=check_out_time,
        check_in_method=CheckInMethod.gps,
        distance_from_location_meters=10,
        is_valid=True,
    )
    db.add(ci)
    await db.flush()
    return ci


# --------------------------------------------------------------------------- #
# /kpis — shape contract
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_get_kpis_returns_expected_shape(
    client: AsyncClient,
    admin_token: str,
    tenant: Tenant,
) -> None:
    """GET /analytics/kpis returns the 8 fields consumed by the dashboard."""
    response = await client.get(
        "/api/v1/analytics/kpis",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    expected_fields = {
        "active_work_orders": int,
        "completed_today": int,
        "completion_rate": float,
        "sla_compliance": float,
        "outstanding_invoices": float,
        "total_revenue_mtd": float,
        "crew_utilization": float,
        "avg_time_on_site_minutes": int,
    }
    for field, expected_type in expected_fields.items():
        assert field in body, f"missing field {field!r} in /kpis response"
        # JSON numbers come back as int or float depending on value; accept both
        assert isinstance(body[field], (int, float)), (
            f"{field}={body[field]!r} not numeric"
        )
        # Hard type assertion only for ints to catch obvious regressions
        if expected_type is int:
            assert isinstance(body[field], int), f"{field} expected int"


# --------------------------------------------------------------------------- #
# crew_utilization — behavioral tests
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_crew_utilization_with_completed_checkin(
    client: AsyncClient,
    admin_token: str,
    db: AsyncSession,
    tenant: Tenant,
    employee_user: User,
) -> None:
    """
    One crew-assigned WO with estimated_hours=4, one 2-hour check-in
    -> crew_utilization == 0.5 (50%).
    """
    cust = await _seed_client(db, tenant)
    loc = await _seed_location(db, tenant, cust)
    crew = await _seed_crew(db, tenant)

    now = datetime.now(UTC)
    scheduled = now - timedelta(days=2)
    wo = await _seed_work_order(
        db, tenant, cust, loc,
        crew=crew,
        estimated_hours=Decimal("4.0"),
        scheduled_date=scheduled,
        status=WorkOrderStatus.completed,
    )
    await _seed_check_in(
        db, tenant, wo, employee_user,
        check_in_time=scheduled.replace(hour=9, minute=0),
        check_out_time=scheduled.replace(hour=11, minute=0),  # 2 hours
    )

    response = await client.get(
        "/api/v1/analytics/kpis",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["crew_utilization"] == 0.5


@pytest.mark.asyncio
async def test_crew_utilization_zero_when_no_scheduled_hours(
    client: AsyncClient,
    admin_token: str,
    tenant: Tenant,
) -> None:
    """No WOs scheduled in range -> denominator is 0 -> returns 0.0 (no DivByZero)."""
    response = await client.get(
        "/api/v1/analytics/kpis",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["crew_utilization"] == 0.0


@pytest.mark.asyncio
async def test_crew_utilization_excludes_unassigned_wo(
    client: AsyncClient,
    admin_token: str,
    db: AsyncSession,
    tenant: Tenant,
    employee_user: User,
) -> None:
    """
    A WO with no crew_id must not enter the denominator.
    Setup: two WOs, one with crew (4h) + 2h check-in, one without crew (10h)
    -> crew_utilization == 0.5 (the unassigned 10h is excluded).
    """
    cust = await _seed_client(db, tenant)
    loc = await _seed_location(db, tenant, cust)
    crew = await _seed_crew(db, tenant)

    now = datetime.now(UTC)
    scheduled = now - timedelta(days=1)

    wo_with_crew = await _seed_work_order(
        db, tenant, cust, loc,
        crew=crew,
        estimated_hours=Decimal("4.0"),
        scheduled_date=scheduled,
    )
    await _seed_check_in(
        db, tenant, wo_with_crew, employee_user,
        check_in_time=scheduled.replace(hour=9, minute=0),
        check_out_time=scheduled.replace(hour=11, minute=0),  # 2 hours
    )
    # Unassigned WO (no crew) — should not contribute to denominator
    await _seed_work_order(
        db, tenant, cust, loc,
        crew=None,
        estimated_hours=Decimal("10.0"),
        scheduled_date=scheduled,
    )

    response = await client.get(
        "/api/v1/analytics/kpis",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["crew_utilization"] == 0.5
