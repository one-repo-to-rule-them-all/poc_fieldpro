"""
Tests for Phase 2 of the audit log persistence work (#52).

Covers Section 8.1 of `docs/proposals/audit-log-persistence.md` — the auth-event
regression scenarios. Also includes unit tests for the new AuditService,
AuditContext, and bind_audit_context dependency.
"""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

from httpx import AsyncClient
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditContext, AuditService, get_audit_context
from app.core.audit.context import _AUDIT_CONTEXT
from app.core.security import (
    create_password_reset_token,
    create_refresh_token,
)
from app.models.audit import AuditLog
from app.models.user import RefreshToken, User

# --------------------------------------------------------------------------- #
# Helper — fetch all audit rows visible in the test session
# --------------------------------------------------------------------------- #


async def _fetch_audit_rows(db: AsyncSession) -> list[AuditLog]:
    """Return audit_logs rows for auth-style events only.

    Filters to ``resource_type IN ('auth', 'Tenant', 'User')`` because:
        - 'auth' is what auth-event rows use (login, logout, etc.)
        - 'Tenant' is used by tenant_registered
        - 'User' covers password_reset's resource_type
    Excludes the listener-emitted ``created User`` row that the admin_user
    fixture writes during test setup — that row is not the subject of any
    auth-event test in this module.
    """
    auth_actions = [
        "login",
        "login_failed",
        "logout",
        "tenant_registered",
        "password_reset",
    ]
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.action.in_(auth_actions))
        .order_by(AuditLog.created_at)
    )
    return list(result.scalars().all())


# --------------------------------------------------------------------------- #
# Unit tests — AuditContext
# --------------------------------------------------------------------------- #


def test_audit_context_anonymous_has_all_none() -> None:
    ctx = AuditContext.anonymous()
    assert ctx.user_id is None
    assert ctx.tenant_id is None
    assert ctx.ip_address is None
    assert ctx.user_agent is None
    assert ctx.request_id is None


def test_audit_context_is_frozen() -> None:
    ctx = AuditContext.anonymous()
    # FrozenInstanceError is raised by @dataclass(frozen=True) on attribute set
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        ctx.user_id = uuid.uuid4()  # type: ignore[misc]


def test_get_audit_context_returns_anonymous_by_default() -> None:
    # Reset the contextvar to its default before reading
    token = _AUDIT_CONTEXT.set(AuditContext.anonymous())
    try:
        ctx = get_audit_context()
        assert ctx == AuditContext.anonymous()
    finally:
        _AUDIT_CONTEXT.reset(token)


# --------------------------------------------------------------------------- #
# Unit tests — AuditService
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_audit_service_record_persists_row(
    db: AsyncSession, admin_user: User
) -> None:
    """record() persists with the exact fields passed."""
    service = AuditService(db)

    row = await service.record(
        action="test_event",
        resource_type="TestResource",
        resource_id="abc-123",
        user_id=admin_user.id,
        tenant_id=admin_user.tenant_id,
        ip_address="10.0.0.1",
        user_agent="test-agent/1.0",
    )

    assert row.id is not None
    assert row.action == "test_event"
    assert row.resource_type == "TestResource"
    assert row.resource_id == "abc-123"
    assert row.user_id == admin_user.id
    assert row.tenant_id == admin_user.tenant_id
    assert row.ip_address == "10.0.0.1"
    assert row.user_agent == "test-agent/1.0"


@pytest.mark.asyncio
async def test_audit_service_record_falls_back_to_contextvar(
    db: AsyncSession, admin_user: User
) -> None:
    """When user_id is not passed, AuditService pulls from _AUDIT_CONTEXT."""
    token = _AUDIT_CONTEXT.set(
        AuditContext(
            user_id=admin_user.id,
            tenant_id=admin_user.tenant_id,
            ip_address="1.2.3.4",
            user_agent="ctx-agent",
        )
    )
    try:
        service = AuditService(db)
        row = await service.record(action="contextvar_test", resource_type="X")
        assert row.user_id == admin_user.id
        assert row.tenant_id == admin_user.tenant_id
        assert row.ip_address == "1.2.3.4"
        assert row.user_agent == "ctx-agent"
    finally:
        _AUDIT_CONTEXT.reset(token)


@pytest.mark.asyncio
async def test_audit_service_explicit_overrides_contextvar(
    db: AsyncSession, admin_user: User, employee_user: User
) -> None:
    """Explicit user_id wins over the contextvar value."""
    token = _AUDIT_CONTEXT.set(AuditContext(user_id=admin_user.id))
    try:
        service = AuditService(db)
        row = await service.record(
            action="override_test", resource_type="X", user_id=employee_user.id
        )
        assert row.user_id == employee_user.id
        assert row.user_id != admin_user.id
    finally:
        _AUDIT_CONTEXT.reset(token)


@pytest.mark.asyncio
async def test_audit_service_serializes_dict_values(db: AsyncSession) -> None:
    """old_values / new_values must be persisted as a plain dict."""
    service = AuditService(db)
    row = await service.record(
        action="updated",
        resource_type="WorkOrder",
        old_values={"status": "scheduled"},
        new_values={"status": "completed"},
    )
    assert row.old_values == {"status": "scheduled"}
    assert row.new_values == {"status": "completed"}


@pytest.mark.asyncio
async def test_audit_service_record_model_change_derives_fields(
    db: AsyncSession, admin_user: User
) -> None:
    """record_model_change derives resource_type and resource_id from the target."""
    service = AuditService(db)
    row = await service.record_model_change(
        target=admin_user,
        action="created",
        new_values={"email": admin_user.email},
    )
    assert row.resource_type == "User"
    assert row.resource_id == str(admin_user.id)
    assert row.action == "created"


# --------------------------------------------------------------------------- #
# Integration tests — auth event regressions (Section 8.1 of scoping doc)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_audit_login_failed_writes_row(
    client: AsyncClient, admin_user: User, db: AsyncSession
) -> None:
    """Wrong password → 401 + audit row with action='login_failed'.

    The row is written with autonomous=True so it survives the request
    rollback that happens when the route raises HTTPException(401).
    Without that, get_db() would roll back the audit row along with the
    failed attempt and the table would have zero login_failed rows ever.
    """
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "wrong"},
    )
    assert response.status_code == 401

    rows = await _fetch_audit_rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "login_failed"
    assert row.resource_type == "auth"
    # user_id is the matched user (email existed, password didn't match)
    assert row.user_id == admin_user.id
    # ip + user_agent populated by bind_audit_context
    assert row.ip_address is not None
    assert row.user_agent is not None


@pytest.mark.asyncio
async def test_audit_login_failed_unknown_email_writes_null_user_id(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Wrong-email failed login writes row with user_id=None (no match)."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nosuch@nowhere.com", "password": "wrong"},
    )
    assert response.status_code == 401

    rows = await _fetch_audit_rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "login_failed"
    assert row.user_id is None


@pytest.mark.asyncio
async def test_audit_login_success_writes_row(
    client: AsyncClient, admin_user: User, db: AsyncSession
) -> None:
    """Correct credentials → 200 + audit row with action='login' and the user/tenant."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "Admin123!"},
    )
    assert response.status_code == 200

    rows = await _fetch_audit_rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "login"
    assert row.resource_type == "auth"
    assert row.resource_id == str(admin_user.id)
    assert row.user_id == admin_user.id
    assert row.tenant_id == admin_user.tenant_id
    assert row.ip_address is not None
    assert row.user_agent is not None


@pytest.mark.asyncio
async def test_audit_logout_writes_row(
    client: AsyncClient, admin_user: User, db: AsyncSession
) -> None:
    """Logout with a valid refresh token writes action='logout'."""
    # Mint a refresh token + persist its record (mirrors what /login would do)
    import hashlib

    raw_token = create_refresh_token({"sub": str(admin_user.id)})
    token_record = RefreshToken(
        id=uuid.uuid4(),
        user_id=admin_user.id,
        tenant_id=admin_user.tenant_id,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=datetime.now(tz=UTC).replace(year=2030),
    )
    db.add(token_record)
    await db.flush()

    response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": raw_token}
    )
    assert response.status_code == 204

    rows = await _fetch_audit_rows(db)
    logout_rows = [r for r in rows if r.action == "logout"]
    assert len(logout_rows) == 1
    row = logout_rows[0]
    assert row.resource_type == "auth"
    assert row.user_id == admin_user.id


@pytest.mark.asyncio
async def test_audit_register_writes_row(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Register flow writes action='tenant_registered' with resource_type='Tenant'."""
    payload = {
        "tenant_name": "Audit Test Co",
        "tenant_slug": "audit-test-co",
        "email": "founder@audit-test-co.com",
        "password": "SecurePass123!",
        "first_name": "Audit",
        "last_name": "Tester",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    rows = await _fetch_audit_rows(db)
    register_rows = [r for r in rows if r.action == "tenant_registered"]
    assert len(register_rows) == 1
    row = register_rows[0]
    assert row.resource_type == "Tenant"
    assert row.tenant_id is not None
    assert row.user_id is not None
    assert row.resource_id == str(row.tenant_id)


@pytest.mark.asyncio
async def test_audit_password_reset_writes_row(
    client: AsyncClient, admin_user: User, db: AsyncSession
) -> None:
    """Password reset completion writes action='password_reset' for the user."""
    reset_token = create_password_reset_token(str(admin_user.id))

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "NewSecurePass123!"},
    )
    assert response.status_code == 200

    rows = await _fetch_audit_rows(db)
    reset_rows = [r for r in rows if r.action == "password_reset"]
    assert len(reset_rows) == 1
    row = reset_rows[0]
    assert row.resource_type == "User"
    assert row.user_id == admin_user.id
    assert row.tenant_id == admin_user.tenant_id
    assert row.resource_id == str(admin_user.id)
    # new password / hash must NOT leak into either values column
    assert row.old_values is None
    assert row.new_values is None


# --------------------------------------------------------------------------- #
# Integration test — bind_audit_context fills ip + user_agent
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_bind_audit_context_populates_ip_and_user_agent_on_anonymous_request(
    client: AsyncClient, admin_user: User, db: AsyncSession
) -> None:
    """Anonymous request (login_failed) still carries ip_address and user_agent."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "wrong"},
        headers={"User-Agent": "phase-2-test/1.0"},
    )
    assert response.status_code == 401

    rows = await _fetch_audit_rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert row.user_agent == "phase-2-test/1.0"
    assert row.ip_address  # ASGI transport sets some value, never empty
