"""
Shared pytest fixtures for FieldPro integration tests.

Architecture (per #62 fix):

    * `engine` is **function-scoped**. A fresh AsyncEngine is created per
      test, the schema is dropped + recreated, and the engine is disposed
      at teardown. This eliminates the cross-loop asyncpg
      "another operation is in progress" failures that occur when a
      session-scoped engine's connection pool is shared across the
      per-test event loops created by pytest-asyncio.

    * `db` yields an AsyncSession bound to the per-test engine. Tests can
      commit freely — the next test recreates the schema anyway.

    * `client` overrides `get_db` to yield the same per-test session, so
      requests made through the AsyncClient see the same DB state the
      test seeded directly.

Trade-off: ~200ms per test for the DROP/CREATE cycle. For a few dozen
tests that's a few seconds total — acceptable. If the suite grows past
a few hundred integration tests we revisit (savepoint-rollback pattern).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
import uuid

from httpx import ASGITransport, AsyncClient
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.audit import AuditListener
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.tenant import SubscriptionPlan, Tenant
from app.models.user import User, UserRole

# --------------------------------------------------------------------------- #
# Audit listeners — ASGITransport doesn't run FastAPI's lifespan, so the
# AuditListener.register() call in app/main.py:lifespan() never fires under
# pytest. Register once at module load. event.listen is idempotent so
# re-running this in another test session is safe.
# --------------------------------------------------------------------------- #

AuditListener.register()

# --------------------------------------------------------------------------- #
# Test DB URL
# --------------------------------------------------------------------------- #

TEST_DB_URL: str = settings.DATABASE_TEST_URL


# --------------------------------------------------------------------------- #
# Engine — function-scoped, schema dropped+recreated per test
# --------------------------------------------------------------------------- #


@pytest_asyncio.fixture
async def engine() -> AsyncIterator:
    """Per-test AsyncEngine. Drops and recreates the schema at setup so
    every test starts on a clean DB."""
    _engine = create_async_engine(TEST_DB_URL, echo=False)
    async with _engine.begin() as conn:
        # Drop the audit-log view first — it depends on audit_logs, which
        # Base.metadata.drop_all would otherwise fail to drop in CI where
        # alembic upgrade head ran first and created the view.
        await conn.execute(text("DROP VIEW IF EXISTS v_audit_events CASCADE"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield _engine
    finally:
        await _engine.dispose()


# --------------------------------------------------------------------------- #
# DB session
# --------------------------------------------------------------------------- #


@pytest_asyncio.fixture
async def db(engine) -> AsyncIterator[AsyncSession]:
    """AsyncSession bound to the per-test engine. Tests are free to
    commit — the engine's schema is recreated for the next test."""
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session


# --------------------------------------------------------------------------- #
# HTTP client with DB override
# --------------------------------------------------------------------------- #


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncIterator[AsyncClient]:
    """httpx AsyncClient wired to the FastAPI app. Overrides `get_db` so
    requests use the same per-test session the test seeded data into.

    The override commits at the end of each request (mirroring production
    ``get_db``) so audit rows written by the listener are visible to the
    test's subsequent queries on the same session.
    """

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        try:
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    app.dependency_overrides[get_db] = _override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# Seed fixtures
# --------------------------------------------------------------------------- #


@pytest_asyncio.fixture
async def subscription_plan(db: AsyncSession) -> SubscriptionPlan:
    """Seed a default subscription plan."""
    plan = SubscriptionPlan(
        id=uuid.uuid4(),
        name="Starter",
        price_monthly=0,
        price_yearly=0,
        max_users=10,
        max_locations=50,
        features={},
        is_active=True,
    )
    db.add(plan)
    await db.flush()
    return plan


@pytest_asyncio.fixture
async def tenant(db: AsyncSession, subscription_plan: SubscriptionPlan) -> Tenant:
    """Seed a test tenant linked to the default subscription plan."""
    t = Tenant(
        id=uuid.uuid4(),
        name="Test Co",
        slug="test-co",
        subscription_plan_id=subscription_plan.id,
        settings={},
        is_active=True,
    )
    db.add(t)
    await db.flush()
    return t


@pytest_asyncio.fixture
async def admin_user(db: AsyncSession, tenant: Tenant) -> User:
    """Seed a tenant_admin user."""
    u = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="admin@test.fieldpro.dev",
        hashed_password=get_password_hash("Admin123!"),
        first_name="Admin",
        last_name="User",
        role=UserRole.tenant_admin,
        is_active=True,
        is_verified=True,
    )
    db.add(u)
    await db.flush()
    return u


@pytest_asyncio.fixture
def admin_token(admin_user: User) -> str:
    """Return a valid JWT access token for the admin user."""
    return create_access_token({"sub": str(admin_user.id)})


@pytest_asyncio.fixture
async def employee_user(db: AsyncSession, tenant: Tenant) -> User:
    """Seed an employee-role user."""
    u = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="worker@test.fieldpro.dev",
        hashed_password=get_password_hash("Worker123!"),
        first_name="Field",
        last_name="Worker",
        role=UserRole.employee,
        is_active=True,
        is_verified=True,
    )
    db.add(u)
    await db.flush()
    return u


@pytest_asyncio.fixture
def employee_token(employee_user: User) -> str:
    """Return a valid JWT access token for the employee user."""
    return create_access_token({"sub": str(employee_user.id)})
