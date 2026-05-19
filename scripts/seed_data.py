"""
FieldPro — Development Seed Data
=================================
Creates a complete, realistic dataset covering every feature and UI state.

Usage:
    python scripts/seed_data.py

Or via Docker:
    docker compose run --rm backend python scripts/seed_data.py
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import get_password_hash
from app.models.tenant import SubscriptionPlan, Tenant, TenantSubscription, SubscriptionStatus
from app.models.user import User, UserRole
from app.models.client import Client, ClientContact, Industry
from app.models.location import Location
from app.models.crew import Crew, CrewMember, CrewMemberRole
from app.models.work_order import (
    WorkOrder, WorkOrderTask, WorkOrderCheckIn,
    WorkOrderStatus, Priority, WorkType, TaskStatus, CheckInMethod,
)
from app.models.invoice import Invoice, InvoiceLineItem, InvoiceStatus, Payment, PaymentMethod

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://fieldpro:fieldpro_dev_password@localhost:5432/fieldpro_dev",
)

NOW = datetime.now(tz=timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def dt(days_offset: int = 0, hours: int = 9, minutes: int = 0) -> datetime:
    return (NOW + timedelta(days=days_offset)).replace(
        hour=hours, minute=minutes, second=0, microsecond=0
    )


async def already_seeded(session: AsyncSession) -> bool:
    result = await session.execute(select(Tenant).where(Tenant.slug == "demo"))
    return result.scalar_one_or_none() is not None


# ─────────────────────────────────────────────────────────────────────────────
# Subscription plan + tenant
# ─────────────────────────────────────────────────────────────────────────────

async def seed_subscription_plans(session: AsyncSession) -> SubscriptionPlan:
    print("  + Creating subscription plans...")
    plan = SubscriptionPlan(
        name="Professional",
        description="Full-featured plan for growing field service teams.",
        price_monthly=Decimal("99.00"),
        price_yearly=Decimal("990.00"),
        max_users=25,
        max_locations=100,
        features={
            "scheduling": True,
            "invoicing": True,
            "crew_management": True,
            "client_portal": True,
            "mobile_app": True,
            "reporting": True,
            "api_access": False,
            "custom_branding": False,
        },
        is_active=True,
    )
    session.add(plan)
    await session.flush()
    print(f"    + Plan: {plan.name} (${plan.price_monthly}/mo)")
    return plan


async def seed_tenant(session: AsyncSession, plan: SubscriptionPlan) -> Tenant:
    print("  + Creating tenant...")
    tenant = Tenant(
        name="Demo Janitorial Co",
        slug="demo",
        subscription_plan_id=plan.id,
        settings={
            "timezone": "America/Chicago",
            "currency": "USD",
            "date_format": "MM/DD/YYYY",
            "work_order_prefix": "WO",
            "invoice_prefix": "INV",
        },
        is_active=True,
    )
    session.add(tenant)
    await session.flush()

    subscription = TenantSubscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        status=SubscriptionStatus.active,
        current_period_start=dt(-30).isoformat(),
        current_period_end=dt(335).isoformat(),
    )
    session.add(subscription)
    await session.flush()
    print(f"    + Tenant: {tenant.name} (slug: {tenant.slug})")
    return tenant


# ─────────────────────────────────────────────────────────────────────────────
# Users
# ─────────────────────────────────────────────────────────────────────────────

async def seed_users(session: AsyncSession, tenant: Tenant) -> dict[str, User]:
    print("  + Creating users...")
    users: dict[str, User] = {}

    user_data = [
        {
            "key": "admin",
            "email": "admin@demo.fieldpro.app",
            "first_name": "Alex",
            "last_name": "Rivera",
            "role": UserRole.tenant_admin,
            "phone": "+13615550001",
            "password": "Admin123!",
        },
        {
            "key": "manager",
            "email": "manager@demo.fieldpro.app",
            "first_name": "Jordan",
            "last_name": "Castillo",
            "role": UserRole.manager,
            "phone": "+13615550002",
            "password": "Manager123!",
        },
        {
            "key": "emp1",
            "email": "carlos@demo.fieldpro.app",
            "first_name": "Carlos",
            "last_name": "Mendez",
            "role": UserRole.employee,
            "phone": "+13615550003",
            "password": "Employee123!",
        },
        {
            "key": "emp2",
            "email": "maria@demo.fieldpro.app",
            "first_name": "Maria",
            "last_name": "Gonzalez",
            "role": UserRole.employee,
            "phone": "+13615550004",
            "password": "Employee123!",
        },
        {
            "key": "emp3",
            "email": "james@demo.fieldpro.app",
            "first_name": "James",
            "last_name": "Thompson",
            "role": UserRole.employee,
            "phone": "+13615550005",
            "password": "Employee123!",
        },
        {
            "key": "emp4",
            "email": "linda@demo.fieldpro.app",
            "first_name": "Linda",
            "last_name": "Nguyen",
            "role": UserRole.employee,
            "phone": "+13615550006",
            "password": "Employee123!",
        },
    ]

    for ud in user_data:
        user = User(
            tenant_id=tenant.id,
            email=ud["email"],
            first_name=ud["first_name"],
            last_name=ud["last_name"],
            role=ud["role"],
            phone=ud.get("phone"),
            hashed_password=get_password_hash(ud["password"]),
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        users[ud["key"]] = user
        print(f"    + User: {user.email} ({user.role.value})")

    await session.flush()
    return users


# ─────────────────────────────────────────────────────────────────────────────
# Clients
# ─────────────────────────────────────────────────────────────────────────────

async def seed_clients(session: AsyncSession, tenant: Tenant) -> dict[str, Client]:
    print("  + Creating clients...")
    clients: dict[str, Client] = {}

    clients_data = [
        {
            "key": "city",
            "name": "City of Corpus Christi",
            "code": "CCTX-001",
            "industry": Industry.janitorial,
            "billing_address": {
                "line1": "1201 Leopard St",
                "city": "Corpus Christi",
                "state": "TX",
                "zip": "78401",
                "country": "US",
            },
            "billing_email": "billing@cctexas.com",
            "billing_phone": "+13615559100",
            "notes": "City parks and recreation department. Net-30 payment terms.",
            "contacts": [
                {
                    "name": "Robert Flores",
                    "email": "r.flores@cctexas.com",
                    "phone": "+13615559101",
                    "title": "Parks & Recreation Director",
                    "is_primary": True,
                    "notes": "Primary contact for all service coordination.",
                },
                {
                    "name": "Sandra Vega",
                    "email": "s.vega@cctexas.com",
                    "phone": "+13615559102",
                    "title": "Facilities Coordinator",
                    "is_primary": False,
                    "notes": "Handles after-hours and emergency requests.",
                },
            ],
        },
        {
            "key": "medcenter",
            "name": "Bay Area Medical Center",
            "code": "BAMC-002",
            "industry": Industry.facility_management,
            "billing_address": {
                "line1": "7101 S Padre Island Dr",
                "city": "Corpus Christi",
                "state": "TX",
                "zip": "78412",
                "country": "US",
            },
            "billing_email": "facilities@bayareamc.com",
            "billing_phone": "+13615558200",
            "notes": "Medical-grade cleaning required. All staff must have HIPAA training. Net-15 payment terms.",
            "contacts": [
                {
                    "name": "Dr. Patricia Walsh",
                    "email": "p.walsh@bayareamc.com",
                    "phone": "+13615558201",
                    "title": "Facilities Director",
                    "is_primary": True,
                    "notes": "Decision maker for contract renewals.",
                },
            ],
        },
        {
            "key": "harbor",
            "name": "Harbor View Shopping Center",
            "code": "HVSC-003",
            "industry": Industry.commercial_cleaning,
            "billing_address": {
                "line1": "5858 S Padre Island Dr",
                "city": "Corpus Christi",
                "state": "TX",
                "zip": "78411",
                "country": "US",
            },
            "billing_email": "mgmt@harborviewsc.com",
            "billing_phone": "+13615557300",
            "notes": "Retail mall — 42 tenant units. Night-time cleaning only (after 10pm). Net-30.",
            "contacts": [
                {
                    "name": "Mike Hartley",
                    "email": "m.hartley@harborviewsc.com",
                    "phone": "+13615557301",
                    "title": "Property Manager",
                    "is_primary": True,
                    "notes": "Strict about cleaning windows and common areas before opening.",
                },
            ],
        },
    ]

    for cd in clients_data:
        client = Client(
            tenant_id=tenant.id,
            name=cd["name"],
            code=cd["code"],
            industry=cd["industry"],
            billing_address=cd["billing_address"],
            billing_email=cd.get("billing_email"),
            billing_phone=cd.get("billing_phone"),
            notes=cd.get("notes"),
            is_active=True,
        )
        session.add(client)
        await session.flush()

        for con in cd.get("contacts", []):
            contact = ClientContact(
                tenant_id=tenant.id,
                client_id=client.id,
                name=con["name"],
                email=con.get("email"),
                phone=con.get("phone"),
                title=con.get("title"),
                is_primary=con.get("is_primary", False),
                notes=con.get("notes"),
            )
            session.add(contact)

        clients[cd["key"]] = client
        print(f"    + Client: {client.name}")

    await session.flush()
    return clients


# ─────────────────────────────────────────────────────────────────────────────
# Locations
# ─────────────────────────────────────────────────────────────────────────────

async def seed_locations(
    session: AsyncSession,
    tenant: Tenant,
    clients: dict[str, Client],
) -> dict[str, Location]:
    print("  + Creating locations...")
    locations: dict[str, Location] = {}

    locations_data = [
        # City of Corpus Christi
        {
            "key": "park_a",
            "client": "city",
            "name": "Greenwood Park",
            "address": {"line1": "4545 Corona Dr", "city": "Corpus Christi", "state": "TX", "zip": "78411", "country": "US"},
            "access_instructions": "Large park with pavilion, restrooms, and playground. Access code: 4521",
        },
        {
            "key": "park_b",
            "client": "city",
            "name": "South Bluff Park",
            "address": {"line1": "700 S Alameda St", "city": "Corpus Christi", "state": "TX", "zip": "78404", "country": "US"},
            "access_instructions": "Smaller park, restroom facility only. Gate key with manager.",
        },
        {
            "key": "community_center",
            "client": "city",
            "name": "Downtown Community Center",
            "address": {"line1": "1581 N Chaparral St", "city": "Corpus Christi", "state": "TX", "zip": "78401", "country": "US"},
            "access_instructions": "Full facility — lobby, 4 meeting rooms, 2 restrooms, kitchen. After-hours contact: 361-555-9200",
        },
        # Bay Area Medical Center
        {
            "key": "med_lobby",
            "client": "medcenter",
            "name": "Main Lobby & Waiting Areas",
            "address": {"line1": "7101 S Padre Island Dr", "city": "Corpus Christi", "state": "TX", "zip": "78412", "country": "US"},
            "access_instructions": "Check in with security desk. Cleaning must use hospital-grade disinfectants only.",
        },
        {
            "key": "med_floors",
            "client": "medcenter",
            "name": "Patient Care Floors 2–4",
            "address": {"line1": "7101 S Padre Island Dr Fl 2-4", "city": "Corpus Christi", "state": "TX", "zip": "78412", "country": "US"},
            "access_instructions": "Badge access required. Do not enter rooms with red isolation signs. Supervisor escort required.",
        },
        # Harbor View Shopping Center
        {
            "key": "harbor_common",
            "client": "harbor",
            "name": "Common Areas & Food Court",
            "address": {"line1": "5858 S Padre Island Dr", "city": "Corpus Christi", "state": "TX", "zip": "78411", "country": "US"},
            "access_instructions": "Service entrance on north side. Key code: 9912. Must complete before 7am.",
        },
        {
            "key": "harbor_restrooms",
            "client": "harbor",
            "name": "Public Restrooms (all levels)",
            "address": {"line1": "5858 S Padre Island Dr", "city": "Corpus Christi", "state": "TX", "zip": "78411", "country": "US"},
            "access_instructions": "3 restroom clusters. Supplies stored in janitorial closet near food court.",
        },
    ]

    for ld in locations_data:
        loc = Location(
            tenant_id=tenant.id,
            client_id=clients[ld["client"]].id,
            name=ld["name"],
            address=ld["address"],
            access_instructions=ld.get("access_instructions"),
            is_active=True,
            geofence_radius_meters=100,
        )
        session.add(loc)
        locations[ld["key"]] = loc
        print(f"    + Location: {loc.name}")

    await session.flush()
    return locations


# ─────────────────────────────────────────────────────────────────────────────
# Crews
# ─────────────────────────────────────────────────────────────────────────────

async def seed_crews(
    session: AsyncSession,
    tenant: Tenant,
    users: dict[str, User],
) -> dict[str, Crew]:
    print("  + Creating crews...")
    crews: dict[str, Crew] = {}

    crew_data = [
        {
            "key": "alpha",
            "name": "Alpha Crew",
            "code": "ALPHA",
            "description": "Primary daytime crew — parks and outdoor facilities",
            "lead_key": "emp1",
            "member_keys": ["emp2"],
        },
        {
            "key": "bravo",
            "name": "Bravo Crew",
            "code": "BRAVO",
            "description": "Evening crew — community center and indoor facilities",
            "lead_key": "emp3",
            "member_keys": ["emp4"],
        },
        {
            "key": "charlie",
            "name": "Charlie Crew",
            "code": "CHARLIE",
            "description": "Medical facilities specialist crew — HIPAA trained",
            "lead_key": "emp4",
            "member_keys": [],
        },
    ]

    for cd in crew_data:
        crew = Crew(
            tenant_id=tenant.id,
            name=cd["name"],
            code=cd["code"],
            description=cd["description"],
            is_active=True,
        )
        session.add(crew)
        await session.flush()

        lead = CrewMember(
            tenant_id=tenant.id,
            crew_id=crew.id,
            user_id=users[cd["lead_key"]].id,
            role=CrewMemberRole.lead,
            joined_at=dt(-60),
        )
        session.add(lead)

        for mk in cd.get("member_keys", []):
            member = CrewMember(
                tenant_id=tenant.id,
                crew_id=crew.id,
                user_id=users[mk].id,
                role=CrewMemberRole.member,
                joined_at=dt(-60),
            )
            session.add(member)

        crews[cd["key"]] = crew
        print(f"    + Crew: {crew.name}")

    await session.flush()
    return crews


# ─────────────────────────────────────────────────────────────────────────────
# Work orders — all statuses, SLA, recurrence
# ─────────────────────────────────────────────────────────────────────────────

async def seed_work_orders(
    session: AsyncSession,
    tenant: Tenant,
    clients: dict[str, Client],
    locations: dict[str, Location],
    users: dict[str, User],
    crews: dict[str, Crew],
) -> dict[str, WorkOrder]:
    print("  + Creating work orders...")
    work_orders: dict[str, WorkOrder] = {}

    wo_data = [
        # ── SCHEDULED ──────────────────────────────────────────────────────
        {
            "key": "wo_sched_1",
            "title": "Weekly Restroom & Pavilion Clean — Greenwood Park",
            "description": "Full restroom sanitization, pavilion sweep and mop, trash collection, exterior pressure wash.",
            "client": "city", "location": "park_a", "crew": "alpha", "assigned_to": "emp1",
            "status": WorkOrderStatus.scheduled,
            "priority": Priority.normal,
            "work_type": WorkType.recurring,
            "scheduled_date": dt(2),
            "scheduled_start_time": dt(2, hours=8),
            "scheduled_end_time": dt(2, hours=12),
            "estimated_hours": Decimal("4.0"),
            "recurrence_rule": "FREQ=WEEKLY;BYDAY=MO,WE,FR",
            "sla_deadline": dt(2, hours=14),
        },
        {
            "key": "wo_sched_2",
            "title": "Bi-Weekly Park Service — Both Parks",
            "description": "Bi-weekly service route: Park A restrooms, pavilion, trash; Park B restrooms, trash. Check for graffiti.",
            "client": "city", "location": "park_a", "crew": "alpha", "assigned_to": "emp1",
            "status": WorkOrderStatus.scheduled,
            "priority": Priority.normal,
            "work_type": WorkType.recurring,
            "scheduled_date": dt(5),
            "scheduled_start_time": dt(5, hours=8),
            "scheduled_end_time": dt(5, hours=13),
            "estimated_hours": Decimal("5.0"),
            "recurrence_rule": "FREQ=WEEKLY;INTERVAL=2;BYDAY=TH",
            "sla_deadline": dt(5, hours=15),
        },
        {
            "key": "wo_sched_3",
            "title": "Nightly Common Area Clean — Harbor View",
            "description": "Sweep and mop all common areas, food court, corridors. Polish entrance floors.",
            "client": "harbor", "location": "harbor_common", "crew": "bravo", "assigned_to": "emp3",
            "status": WorkOrderStatus.scheduled,
            "priority": Priority.high,
            "work_type": WorkType.recurring,
            "scheduled_date": dt(1),
            "scheduled_start_time": dt(1, hours=22),
            "scheduled_end_time": dt(2, hours=2),
            "estimated_hours": Decimal("4.0"),
            "recurrence_rule": "FREQ=DAILY;BYDAY=MO,TU,WE,TH,FR",
            "sla_deadline": dt(2, hours=6),
        },
        {
            "key": "wo_sched_4",
            "title": "Patient Floor Deep Clean — BAMC Floors 2–4",
            "description": "HIPAA-compliant deep clean of patient rooms, corridors, and nursing stations.",
            "client": "medcenter", "location": "med_floors", "crew": "charlie", "assigned_to": "emp4",
            "status": WorkOrderStatus.scheduled,
            "priority": Priority.urgent,
            "work_type": WorkType.recurring,
            "scheduled_date": dt(3),
            "scheduled_start_time": dt(3, hours=6),
            "scheduled_end_time": dt(3, hours=10),
            "estimated_hours": Decimal("4.0"),
            "recurrence_rule": "FREQ=DAILY",
            "sla_deadline": dt(3, hours=11),
        },

        # ── IN PROGRESS ─────────────────────────────────────────────────────
        {
            "key": "wo_inprog_1",
            "title": "Park Restroom Cleaning — South Bluff Park",
            "description": "Restroom deep clean, restock supplies, inspect for vandalism.",
            "client": "city", "location": "park_b", "crew": "alpha", "assigned_to": "emp2",
            "status": WorkOrderStatus.in_progress,
            "priority": Priority.normal,
            "work_type": WorkType.recurring,
            "scheduled_date": dt(0),
            "scheduled_start_time": dt(0, hours=9),
            "scheduled_end_time": dt(0, hours=11),
            "actual_start_time": dt(0, hours=9),
            "estimated_hours": Decimal("2.0"),
            "sla_deadline": dt(0, hours=12),
        },
        {
            "key": "wo_inprog_2",
            "title": "BAMC Lobby & Waiting Room Clean",
            "description": "Sanitize all waiting room seating, reception desk, entrance mats, and lobby restrooms.",
            "client": "medcenter", "location": "med_lobby", "crew": "charlie", "assigned_to": "emp4",
            "status": WorkOrderStatus.in_progress,
            "priority": Priority.high,
            "work_type": WorkType.recurring,
            "scheduled_date": dt(0),
            "scheduled_start_time": dt(0, hours=6),
            "scheduled_end_time": dt(0, hours=8),
            "actual_start_time": dt(0, hours=6),
            "estimated_hours": Decimal("2.0"),
            "sla_deadline": dt(0, hours=9),
        },

        # ── COMPLETED (today — for completed_today KPI) ──────────────────
        {
            "key": "wo_done_today_1",
            "title": "Harbor View Restroom Service — Morning Round",
            "description": "All-level restroom clean, restock paper goods and soap dispensers.",
            "client": "harbor", "location": "harbor_restrooms", "crew": "bravo", "assigned_to": "emp3",
            "status": WorkOrderStatus.completed,
            "priority": Priority.normal,
            "work_type": WorkType.recurring,
            "scheduled_date": dt(0),
            "scheduled_start_time": dt(0, hours=5),
            "scheduled_end_time": dt(0, hours=7),
            "actual_start_time": dt(0, hours=5),
            "actual_end_time": dt(0, hours=6, minutes=45),
            "estimated_hours": Decimal("2.0"),
            "actual_hours": Decimal("1.75"),
            "sla_deadline": dt(0, hours=8),
            "sla_met": True,
            "completion_notes": "All restrooms cleaned and restocked. No issues reported.",
        },
        {
            "key": "wo_done_today_2",
            "title": "Community Center Morning Clean",
            "description": "Pre-opening clean of lobby and restrooms before 8am opening.",
            "client": "city", "location": "community_center", "crew": "bravo", "assigned_to": "emp4",
            "status": WorkOrderStatus.completed,
            "priority": Priority.high,
            "work_type": WorkType.recurring,
            "scheduled_date": dt(0),
            "scheduled_start_time": dt(0, hours=6),
            "scheduled_end_time": dt(0, hours=8),
            "actual_start_time": dt(0, hours=6),
            "actual_end_time": dt(0, hours=7, minutes=50),
            "estimated_hours": Decimal("2.0"),
            "actual_hours": Decimal("1.83"),
            "sla_deadline": dt(0, hours=8),
            "sla_met": True,
            "completion_notes": "Completed on time. Restocked cleaning supplies from storage room.",
        },

        # ── COMPLETED (past — history) ───────────────────────────────────
        {
            "key": "wo_done_1",
            "title": "Community Center Post-Event Clean",
            "description": "Full facility clean after weekend community event — lobby, all meeting rooms, kitchen, restrooms.",
            "client": "city", "location": "community_center", "crew": "bravo", "assigned_to": "emp3",
            "status": WorkOrderStatus.completed,
            "priority": Priority.high,
            "work_type": WorkType.one_time,
            "scheduled_date": dt(-3),
            "scheduled_start_time": dt(-3, hours=18),
            "scheduled_end_time": dt(-3, hours=22),
            "actual_start_time": dt(-3, hours=18),
            "actual_end_time": dt(-3, hours=21),
            "estimated_hours": Decimal("4.0"),
            "actual_hours": Decimal("3.0"),
            "sla_deadline": dt(-3, hours=23),
            "sla_met": True,
            "completion_notes": "Completed ahead of schedule. Removed event signage and stored tables.",
        },
        {
            "key": "wo_done_2",
            "title": "Monthly Deep Clean — Community Center",
            "description": "Strip and wax floors, clean HVAC vents, scrub grout, full kitchen sanitization.",
            "client": "city", "location": "community_center", "crew": "bravo", "assigned_to": "emp3",
            "status": WorkOrderStatus.completed,
            "priority": Priority.normal,
            "work_type": WorkType.recurring,
            "scheduled_date": dt(-14),
            "scheduled_start_time": dt(-14, hours=7),
            "scheduled_end_time": dt(-14, hours=15),
            "actual_start_time": dt(-14, hours=7),
            "actual_end_time": dt(-14, hours=14),
            "estimated_hours": Decimal("8.0"),
            "actual_hours": Decimal("7.0"),
            "sla_deadline": dt(-14, hours=16),
            "sla_met": True,
            "completion_notes": "Floors look great. HVAC vents were heavily clogged — flagged for facilities.",
        },
        {
            "key": "wo_done_3",
            "title": "BAMC Emergency Spill Response — Lobby",
            "description": "Emergency bio-hazard clean per protocol. Full lobby sanitization post-incident.",
            "client": "medcenter", "location": "med_lobby", "crew": "charlie", "assigned_to": "emp4",
            "status": WorkOrderStatus.completed,
            "priority": Priority.urgent,
            "work_type": WorkType.recurring,
            "scheduled_date": dt(-7),
            "scheduled_start_time": dt(-7, hours=14),
            "scheduled_end_time": dt(-7, hours=16),
            "actual_start_time": dt(-7, hours=14, minutes=10),
            "actual_end_time": dt(-7, hours=15, minutes=45),
            "estimated_hours": Decimal("2.0"),
            "actual_hours": Decimal("1.58"),
            "sla_deadline": dt(-7, hours=15),
            "sla_met": False,
            "completion_notes": "Delayed 10 minutes — waiting for security clearance at entrance.",
        },

        # ── ON HOLD ─────────────────────────────────────────────────────────
        {
            "key": "wo_hold_1",
            "title": "Greenwood Park Pavilion Pressure Wash",
            "description": "Full exterior pressure wash of pavilion, walkways, and picnic areas. Waiting on equipment repair.",
            "client": "city", "location": "park_a", "crew": "alpha", "assigned_to": "emp1",
            "status": WorkOrderStatus.on_hold,
            "priority": Priority.low,
            "work_type": WorkType.one_time,
            "scheduled_date": dt(-1),
            "scheduled_start_time": dt(-1, hours=8),
            "scheduled_end_time": dt(-1, hours=12),
            "estimated_hours": Decimal("4.0"),
            "internal_notes": "On hold — pressure washer sent out for repair 2026-05-07. Resume when returned.",
        },

        # ── CANCELLED ───────────────────────────────────────────────────────
        {
            "key": "wo_cancel_1",
            "title": "Harbor View Window Cleaning — Exterior",
            "description": "Annual exterior window cleaning of all storefronts. Cancelled by client — rescheduling for Q3.",
            "client": "harbor", "location": "harbor_common", "crew": "alpha", "assigned_to": "emp1",
            "status": WorkOrderStatus.cancelled,
            "priority": Priority.low,
            "work_type": WorkType.one_time,
            "scheduled_date": dt(-5),
            "scheduled_start_time": dt(-5, hours=7),
            "scheduled_end_time": dt(-5, hours=15),
            "estimated_hours": Decimal("8.0"),
            "internal_notes": "Client cancelled on 2026-05-03 — budget hold. Will reschedule Q3.",
        },

        # ── DRAFT ───────────────────────────────────────────────────────────
        {
            "key": "wo_draft_1",
            "title": "BAMC Floors 2–4 Deep Quarterly Clean",
            "description": "Quarterly deep clean — all patient rooms, floor wax, HVAC vents, biohazard waste room sanitization.",
            "client": "medcenter", "location": "med_floors", "crew": "charlie", "assigned_to": "emp4",
            "status": WorkOrderStatus.draft,
            "priority": Priority.high,
            "work_type": WorkType.one_time,
            "scheduled_date": dt(14),
            "scheduled_start_time": dt(14, hours=6),
            "scheduled_end_time": dt(14, hours=14),
            "estimated_hours": Decimal("8.0"),
        },
        {
            "key": "wo_draft_2",
            "title": "Harbor View Food Court Deep Clean — Monthly",
            "description": "Monthly deep clean of food court — grease traps, floor drains, under equipment.",
            "client": "harbor", "location": "harbor_common", "crew": "bravo", "assigned_to": "emp3",
            "status": WorkOrderStatus.draft,
            "priority": Priority.normal,
            "work_type": WorkType.recurring,
            "scheduled_date": dt(10),
            "scheduled_start_time": dt(10, hours=22),
            "scheduled_end_time": dt(11, hours=2),
            "estimated_hours": Decimal("4.0"),
        },

        # ── OVERDUE (past SLA, still open) ──────────────────────────────────
        {
            "key": "wo_overdue_1",
            "title": "South Bluff Park Graffiti Removal",
            "description": "Remove graffiti from restroom exterior walls. Reported by parks staff.",
            "client": "city", "location": "park_b", "crew": "alpha", "assigned_to": "emp2",
            "status": WorkOrderStatus.scheduled,
            "priority": Priority.urgent,
            "work_type": WorkType.one_time,
            "scheduled_date": dt(-2),
            "scheduled_start_time": dt(-2, hours=9),
            "scheduled_end_time": dt(-2, hours=11),
            "estimated_hours": Decimal("2.0"),
            "sla_deadline": dt(-2, hours=11),
            "internal_notes": "Crew availability issue caused delay. Reschedule ASAP.",
        },
    ]

    for wod in wo_data:
        wo = WorkOrder(
            tenant_id=tenant.id,
            client_id=clients[wod["client"]].id,
            location_id=locations[wod["location"]].id,
            crew_id=crews[wod["crew"]].id,
            assigned_to=users[wod["assigned_to"]].id,
            title=wod["title"],
            description=wod.get("description"),
            status=wod["status"],
            priority=wod["priority"],
            work_type=wod["work_type"],
            scheduled_date=wod.get("scheduled_date"),
            scheduled_start_time=wod.get("scheduled_start_time"),
            scheduled_end_time=wod.get("scheduled_end_time"),
            actual_start_time=wod.get("actual_start_time"),
            actual_end_time=wod.get("actual_end_time"),
            estimated_hours=wod.get("estimated_hours"),
            actual_hours=wod.get("actual_hours"),
            sla_deadline=wod.get("sla_deadline"),
            sla_met=wod.get("sla_met"),
            recurrence_rule=wod.get("recurrence_rule"),
            notes=wod.get("notes"),
            internal_notes=wod.get("internal_notes"),
            completion_notes=wod.get("completion_notes"),
        )
        session.add(wo)
        work_orders[wod["key"]] = wo
        print(f"    + Work Order: {wo.title[:55]} [{wo.status.value}]")

    await session.flush()
    return work_orders


# ─────────────────────────────────────────────────────────────────────────────
# Work order tasks (checklist items)
# ─────────────────────────────────────────────────────────────────────────────

async def seed_tasks(
    session: AsyncSession,
    tenant: Tenant,
    work_orders: dict[str, WorkOrder],
    users: dict[str, User],
) -> None:
    print("  + Creating work order tasks...")

    tasks_data = [
        # Completed WO — all tasks done
        {
            "wo_key": "wo_done_1",
            "tasks": [
                {"title": "Lobby — sweep, mop, wipe surfaces", "status": TaskStatus.completed, "completed_by": "emp3", "sort_order": 1},
                {"title": "Meeting rooms — vacuum carpet, wipe tables and chairs", "status": TaskStatus.completed, "completed_by": "emp3", "sort_order": 2},
                {"title": "Kitchen — sanitize counters, appliances, mop floor", "status": TaskStatus.completed, "completed_by": "emp3", "sort_order": 3},
                {"title": "Restrooms — full sanitize, restock supplies", "status": TaskStatus.completed, "completed_by": "emp3", "sort_order": 4},
                {"title": "Remove event signage and store tables", "status": TaskStatus.completed, "completed_by": "emp3", "sort_order": 5},
            ],
        },
        # In-progress WO — partial completion
        {
            "wo_key": "wo_inprog_1",
            "tasks": [
                {"title": "Restroom A — full clean and restock", "status": TaskStatus.completed, "completed_by": "emp2", "sort_order": 1},
                {"title": "Restroom B — full clean and restock", "status": TaskStatus.pending, "sort_order": 2},
                {"title": "Inspect exterior walls for vandalism", "status": TaskStatus.pending, "sort_order": 3},
                {"title": "Empty and reline trash bins", "status": TaskStatus.pending, "sort_order": 4},
            ],
        },
        # Scheduled WO — all pending
        {
            "wo_key": "wo_sched_1",
            "tasks": [
                {"title": "Restrooms — sanitize all fixtures, mop floors", "status": TaskStatus.pending, "sort_order": 1},
                {"title": "Pavilion — sweep and mop", "status": TaskStatus.pending, "sort_order": 2},
                {"title": "Trash collection — all bins", "status": TaskStatus.pending, "sort_order": 3},
                {"title": "Exterior pressure wash", "status": TaskStatus.pending, "sort_order": 4},
            ],
        },
        # Medical WO — strict checklist
        {
            "wo_key": "wo_done_3",
            "tasks": [
                {"title": "Don PPE — gloves, mask, eye protection", "status": TaskStatus.completed, "completed_by": "emp4", "sort_order": 1},
                {"title": "Contain affected area with barriers", "status": TaskStatus.completed, "completed_by": "emp4", "sort_order": 2},
                {"title": "Apply hospital-grade disinfectant — 10 min contact time", "status": TaskStatus.completed, "completed_by": "emp4", "sort_order": 3},
                {"title": "Wipe all surfaces in 15ft radius", "status": TaskStatus.completed, "completed_by": "emp4", "sort_order": 4},
                {"title": "Bag and label biohazard waste for disposal", "status": TaskStatus.completed, "completed_by": "emp4", "sort_order": 5},
                {"title": "Final inspection and supervisor sign-off", "status": TaskStatus.completed, "completed_by": "emp4", "sort_order": 6},
            ],
        },
    ]

    for td in tasks_data:
        wo = work_orders[td["wo_key"]]
        for t in td["tasks"]:
            completed_by_id = users[t["completed_by"]].id if t.get("completed_by") else None
            completed_at = dt(-3, hours=20) if t["status"] == TaskStatus.completed else None
            task = WorkOrderTask(
                tenant_id=tenant.id,
                work_order_id=wo.id,
                title=t["title"],
                is_required=True,
                status=t["status"],
                completed_by=completed_by_id,
                completed_at=completed_at,
                sort_order=t["sort_order"],
            )
            session.add(task)

    await session.flush()
    print(f"    + Tasks created for {len(tasks_data)} work orders")


# ─────────────────────────────────────────────────────────────────────────────
# Check-ins (crew utilization data)
# ─────────────────────────────────────────────────────────────────────────────

async def seed_check_ins(
    session: AsyncSession,
    tenant: Tenant,
    work_orders: dict[str, WorkOrder],
    users: dict[str, User],
) -> None:
    print("  + Creating check-ins (crew utilization data)...")

    check_ins_data = [
        # Completed check-ins (past) — contribute hours to crew utilization KPI
        {"wo_key": "wo_done_1", "user_key": "emp3",
         "check_in": dt(-3, hours=18), "check_out": dt(-3, hours=21),
         "method": CheckInMethod.gps, "lat_in": Decimal("27.8006"), "lon_in": Decimal("-97.3964")},

        {"wo_key": "wo_done_2", "user_key": "emp3",
         "check_in": dt(-14, hours=7), "check_out": dt(-14, hours=14),
         "method": CheckInMethod.gps, "lat_in": Decimal("27.8006"), "lon_in": Decimal("-97.3964")},

        {"wo_key": "wo_done_3", "user_key": "emp4",
         "check_in": dt(-7, hours=14, minutes=10), "check_out": dt(-7, hours=15, minutes=45),
         "method": CheckInMethod.manual, "lat_in": Decimal("27.7213"), "lon_in": Decimal("-97.3866")},

        # Today's completed WOs
        {"wo_key": "wo_done_today_1", "user_key": "emp3",
         "check_in": dt(0, hours=5), "check_out": dt(0, hours=6, minutes=45),
         "method": CheckInMethod.gps, "lat_in": Decimal("27.7501"), "lon_in": Decimal("-97.4071")},
        {"wo_key": "wo_done_today_2", "user_key": "emp4",
         "check_in": dt(0, hours=6), "check_out": dt(0, hours=7, minutes=50),
         "method": CheckInMethod.qr_code, "lat_in": Decimal("27.8006"), "lon_in": Decimal("-97.3964")},

        # Active check-ins (currently on-site — no check_out) → active_check_ins KPI
        {"wo_key": "wo_inprog_1", "user_key": "emp2",
         "check_in": dt(0, hours=9), "check_out": None,
         "method": CheckInMethod.gps, "lat_in": Decimal("27.7413"), "lon_in": Decimal("-97.4049")},
        {"wo_key": "wo_inprog_2", "user_key": "emp4",
         "check_in": dt(0, hours=6), "check_out": None,
         "method": CheckInMethod.gps, "lat_in": Decimal("27.7213"), "lon_in": Decimal("-97.3866")},
    ]

    for ci in check_ins_data:
        check_in = WorkOrderCheckIn(
            tenant_id=tenant.id,
            work_order_id=work_orders[ci["wo_key"]].id,
            user_id=users[ci["user_key"]].id,
            check_in_time=ci["check_in"],
            check_out_time=ci.get("check_out"),
            check_in_latitude=ci.get("lat_in"),
            check_in_longitude=ci.get("lon_in"),
            check_in_method=ci["method"],
            distance_from_location_meters=15,
            is_valid=True,
        )
        session.add(check_in)

    await session.flush()
    print(f"    + {len(check_ins_data)} check-in records created (2 active, {len(check_ins_data)-2} completed)")


# ─────────────────────────────────────────────────────────────────────────────
# Invoices — all statuses
# ─────────────────────────────────────────────────────────────────────────────

async def seed_invoices(
    session: AsyncSession,
    tenant: Tenant,
    clients: dict[str, Client],
    work_orders: dict[str, WorkOrder],
    users: dict[str, User],
) -> None:
    print("  + Creating invoices...")

    # ── PAID ────────────────────────────────────────────────────────────────
    inv_paid = Invoice(
        tenant_id=tenant.id,
        client_id=clients["city"].id,
        invoice_number="INV-2026-0038",
        status=InvoiceStatus.paid,
        issue_date=dt(-45),
        due_date=dt(-15),
        subtotal=Decimal("1050.00"),
        tax_rate=Decimal("0.0825"),
        tax_amount=Decimal("86.63"),
        discount_amount=Decimal("0.00"),
        total=Decimal("1136.63"),
        notes="Monthly deep clean + bi-weekly park services.",
        terms="Net 30",
        sent_at=dt(-45),
        paid_at=dt(-18),
    )
    session.add(inv_paid)
    await session.flush()

    for li in [
        InvoiceLineItem(tenant_id=tenant.id, invoice_id=inv_paid.id,
                        work_order_id=work_orders["wo_done_2"].id,
                        description="Community Center Monthly Deep Clean (7 hrs @ $125/hr)",
                        quantity=Decimal("7"), unit_price=Decimal("125.00"), line_total=Decimal("875.00"), sort_order=1),
        InvoiceLineItem(tenant_id=tenant.id, invoice_id=inv_paid.id,
                        work_order_id=None,
                        description="Park Service Route x2 visits (2 x $87.50)",
                        quantity=Decimal("2"), unit_price=Decimal("87.50"), line_total=Decimal("175.00"), sort_order=2),
    ]:
        session.add(li)

    session.add(Payment(
        tenant_id=tenant.id, invoice_id=inv_paid.id, amount=Decimal("1136.63"),
        payment_method=PaymentMethod.check, reference_number="CHK-30291",
        payment_date=dt(-18), notes="Check received on time.", recorded_by=users["admin"].id,
    ))

    # ── SENT (awaiting payment) ─────────────────────────────────────────────
    inv_sent = Invoice(
        tenant_id=tenant.id,
        client_id=clients["city"].id,
        invoice_number="INV-2026-0041",
        status=InvoiceStatus.sent,
        issue_date=dt(-10),
        due_date=dt(20),
        subtotal=Decimal("875.00"),
        tax_rate=Decimal("0.0825"),
        tax_amount=Decimal("72.19"),
        discount_amount=Decimal("0.00"),
        total=Decimal("947.19"),
        notes="Services rendered per recurring service agreement. Net-30.",
        terms="Net 30",
        sent_at=dt(-10),
    )
    session.add(inv_sent)
    await session.flush()

    for li in [
        InvoiceLineItem(tenant_id=tenant.id, invoice_id=inv_sent.id,
                        work_order_id=work_orders["wo_done_1"].id,
                        description="Community Center Post-Event Clean (3 hrs @ $125/hr)",
                        quantity=Decimal("3"), unit_price=Decimal("125.00"), line_total=Decimal("375.00"), sort_order=1),
        InvoiceLineItem(tenant_id=tenant.id, invoice_id=inv_sent.id,
                        work_order_id=None,
                        description="Park A Weekly Service — Greenwood Park (4 hrs @ $75/hr)",
                        quantity=Decimal("4"), unit_price=Decimal("75.00"), line_total=Decimal("300.00"), sort_order=2),
        InvoiceLineItem(tenant_id=tenant.id, invoice_id=inv_sent.id,
                        work_order_id=None,
                        description="Park B Service — South Bluff Park (2.67 hrs @ $75/hr)",
                        quantity=Decimal("2.67"), unit_price=Decimal("75.00"), line_total=Decimal("200.25"), sort_order=3),
    ]:
        session.add(li)

    # ── OVERDUE ─────────────────────────────────────────────────────────────
    inv_overdue = Invoice(
        tenant_id=tenant.id,
        client_id=clients["harbor"].id,
        invoice_number="INV-2026-0039",
        status=InvoiceStatus.overdue,
        issue_date=dt(-60),
        due_date=dt(-30),
        subtotal=Decimal("2200.00"),
        tax_rate=Decimal("0.0825"),
        tax_amount=Decimal("181.50"),
        discount_amount=Decimal("0.00"),
        total=Decimal("2381.50"),
        notes="March nightly service — 22 nights. Payment overdue — please remit immediately.",
        terms="Net 30",
        sent_at=dt(-60),
    )
    session.add(inv_overdue)
    await session.flush()

    for li in [
        InvoiceLineItem(tenant_id=tenant.id, invoice_id=inv_overdue.id,
                        work_order_id=None,
                        description="Nightly Common Area Clean x22 nights (22 x $75.00)",
                        quantity=Decimal("22"), unit_price=Decimal("75.00"), line_total=Decimal("1650.00"), sort_order=1),
        InvoiceLineItem(tenant_id=tenant.id, invoice_id=inv_overdue.id,
                        work_order_id=None,
                        description="Nightly Restroom Service x22 nights (22 x $25.00)",
                        quantity=Decimal("22"), unit_price=Decimal("25.00"), line_total=Decimal("550.00"), sort_order=2),
    ]:
        session.add(li)

    # ── PARTIAL (partially paid) ─────────────────────────────────────────────
    inv_partial = Invoice(
        tenant_id=tenant.id,
        client_id=clients["medcenter"].id,
        invoice_number="INV-2026-0040",
        status=InvoiceStatus.partial,
        issue_date=dt(-25),
        due_date=dt(5),
        subtotal=Decimal("1800.00"),
        tax_rate=Decimal("0.0825"),
        tax_amount=Decimal("148.50"),
        discount_amount=Decimal("0.00"),
        total=Decimal("1948.50"),
        notes="Medical facility cleaning — daily lobby and patient floor service.",
        terms="Net 30",
        sent_at=dt(-25),
    )
    session.add(inv_partial)
    await session.flush()

    for li in [
        InvoiceLineItem(tenant_id=tenant.id, invoice_id=inv_partial.id,
                        work_order_id=work_orders["wo_done_3"].id,
                        description="Emergency Spill Response (1.58 hrs @ $200/hr)",
                        quantity=Decimal("1.58"), unit_price=Decimal("200.00"), line_total=Decimal("316.00"), sort_order=1),
        InvoiceLineItem(tenant_id=tenant.id, invoice_id=inv_partial.id,
                        work_order_id=None,
                        description="Daily Lobby Clean x14 days (14 x $75.00)",
                        quantity=Decimal("14"), unit_price=Decimal("75.00"), line_total=Decimal("1050.00"), sort_order=2),
        InvoiceLineItem(tenant_id=tenant.id, invoice_id=inv_partial.id,
                        work_order_id=None,
                        description="Patient Floor Clean x7 days (7 x $62.00)",
                        quantity=Decimal("7"), unit_price=Decimal("62.00"), line_total=Decimal("434.00"), sort_order=3),
    ]:
        session.add(li)

    session.add(Payment(
        tenant_id=tenant.id, invoice_id=inv_partial.id, amount=Decimal("974.25"),
        payment_method=PaymentMethod.ach, reference_number="ACH-88192",
        payment_date=dt(-10), notes="Partial payment received — 50%. Balance outstanding.",
        recorded_by=users["admin"].id,
    ))

    # ── DRAFT ───────────────────────────────────────────────────────────────
    inv_draft = Invoice(
        tenant_id=tenant.id,
        client_id=clients["harbor"].id,
        invoice_number="INV-2026-0042",
        status=InvoiceStatus.draft,
        issue_date=dt(0),
        due_date=dt(30),
        subtotal=Decimal("975.00"),
        tax_rate=Decimal("0.0825"),
        tax_amount=Decimal("80.44"),
        discount_amount=Decimal("0.00"),
        total=Decimal("1055.44"),
        notes="April nightly service — draft pending manager review.",
        terms="Net 30",
    )
    session.add(inv_draft)
    await session.flush()

    for li in [
        InvoiceLineItem(tenant_id=tenant.id, invoice_id=inv_draft.id,
                        work_order_id=None,
                        description="Nightly Common Area Clean x13 nights (13 x $75.00)",
                        quantity=Decimal("13"), unit_price=Decimal("75.00"), line_total=Decimal("975.00"), sort_order=1),
    ]:
        session.add(li)

    await session.flush()

    print(f"    + Invoice: {inv_paid.invoice_number} [PAID]    — ${inv_paid.total}")
    print(f"    + Invoice: {inv_sent.invoice_number} [SENT]    — ${inv_sent.total}")
    print(f"    + Invoice: {inv_overdue.invoice_number} [OVERDUE] — ${inv_overdue.total}")
    print(f"    + Invoice: {inv_partial.invoice_number} [PARTIAL] — ${inv_partial.total}")
    print(f"    + Invoice: {inv_draft.invoice_number} [DRAFT]   — ${inv_draft.total}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def main() -> None:
    print("")
    print("FieldPro — Seed Data")
    print("=" * 50)

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        async with session.begin():
            if await already_seeded(session):
                print("  Seed data already present (tenant 'demo' exists). Skipping.")
                print("  To reseed: docker compose down --volumes, then re-run migrations and this script.")
                return

            plan = await seed_subscription_plans(session)
            tenant = await seed_tenant(session, plan)
            users = await seed_users(session, tenant)
            clients = await seed_clients(session, tenant)
            locations = await seed_locations(session, tenant, clients)
            crews = await seed_crews(session, tenant, users)
            work_orders = await seed_work_orders(session, tenant, clients, locations, users, crews)
            await seed_tasks(session, tenant, work_orders, users)
            await seed_check_ins(session, tenant, work_orders, users)
            await seed_invoices(session, tenant, clients, work_orders, users)

    await engine.dispose()

    print("")
    print("  Seed complete!")
    print("")
    print("  Data summary:")
    print("    3 clients  (City of CC, Bay Area Medical, Harbor View)")
    print("    7 locations across 3 clients")
    print("    3 crews    (Alpha, Bravo, Charlie)")
    print("    6 users    (admin, manager, 4 employees)")
    print("    14 work orders (draft, scheduled, in_progress, completed, on_hold, cancelled, overdue)")
    print("    7 check-ins   (2 active → active_check_ins KPI, 5 completed → utilization)")
    print("    5 invoices    (paid, sent, overdue, partial, draft)")
    print("")
    print("  Login credentials:")
    print("    Admin:    admin@demo.fieldpro.app   / Admin123!")
    print("    Manager:  manager@demo.fieldpro.app / Manager123!")
    print("    Employee: carlos@demo.fieldpro.app  / Employee123!")
    print("")
    print("  Access the app:")
    print("    Frontend:  http://localhost:3000")
    print("    API docs:  http://localhost:8000/docs")
    print("")


if __name__ == "__main__":
    asyncio.run(main())
