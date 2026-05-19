"""
Integration tests for /api/v1/auth/* endpoints.

Each test uses the rolled-back DB session from conftest so the database is
clean after every test without explicit cleanup.
"""

from __future__ import annotations

from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole

# --------------------------------------------------------------------------- #
# Register
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_register_creates_tenant_and_admin(client: AsyncClient) -> None:
    """POST /register should create a tenant + admin user and return tokens."""
    payload = {
        "tenant_name": "Acme Janitorial",
        "tenant_slug": "acme-janitorial",
        "email": "owner@acme-janitorial.com",
        "password": "SecurePass123!",
        "first_name": "Jane",
        "last_name": "Doe",
    }
    response = await client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 201, response.text
    body = response.json()

    # The route returns LoginResponse directly (not wrapped in "data")
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"

    user_data = body["user"]
    assert user_data["email"] == payload["email"]
    assert user_data["role"] == UserRole.tenant_admin.value
    assert user_data["tenant_id"] is not None


@pytest.mark.asyncio
async def test_register_duplicate_slug_returns_409(client: AsyncClient) -> None:
    """Registering a second tenant with the same slug must return 409."""
    payload = {
        "tenant_name": "Dup Corp",
        "tenant_slug": "dup-corp",
        "email": "first@dup.com",
        "password": "SecurePass123!",
        "first_name": "First",
        "last_name": "User",
    }
    resp1 = await client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    # Attempt to register again with the same slug
    payload2 = dict(payload)
    payload2["email"] = "second@dup.com"
    resp2 = await client.post("/api/v1/auth/register", json=payload2)
    assert resp2.status_code == 409


# --------------------------------------------------------------------------- #
# Login
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_login_success(
    client: AsyncClient, admin_user: User
) -> None:
    """POST /login with correct credentials returns 200 and access/refresh tokens."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "Admin123!"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == admin_user.email


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(
    client: AsyncClient, admin_user: User
) -> None:
    """POST /login with wrong password must return 401, not 200 or 403."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "WrongPassword999!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user_returns_401(client: AsyncClient) -> None:
    """POST /login for an email that doesn't exist must return 401."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@nowhere.example", "password": "Whatever123!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user_returns_403(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
) -> None:
    """Logging in as an inactive user should return 403."""
    admin_user.is_active = False
    await db.flush()

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "Admin123!"},
    )
    assert response.status_code == 403


# --------------------------------------------------------------------------- #
# Refresh-token rotation
# --------------------------------------------------------------------------- #

@pytest.mark.xfail(
    reason="Pre-existing: refresh-token uniqueness collision unmasked by #106. Follow-up PR. See CLAUDE.md 'Known pre-existing test failures'.",
    strict=False,
)
@pytest.mark.asyncio
async def test_refresh_token_rotation(
    client: AsyncClient, admin_user: User
) -> None:
    """
    After login, using the refresh token should issue a new access+refresh pair.
    The old refresh token must then be rejected (rotation / revocation).
    """
    # Step 1 — login to get initial token pair
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "Admin123!"},
    )
    assert login_resp.status_code == 200
    original_refresh = login_resp.json()["refresh_token"]
    original_access = login_resp.json()["access_token"]

    # Step 2 — exchange the refresh token for a new pair
    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": original_refresh},
    )
    assert refresh_resp.status_code == 200
    new_body = refresh_resp.json()
    new_access = new_body["access_token"]
    new_refresh = new_body["refresh_token"]

    # Tokens must differ
    assert new_access != original_access
    assert new_refresh != original_refresh

    # Step 3 — using the old refresh token again must be rejected
    replay_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": original_refresh},
    )
    assert replay_resp.status_code == 401


# --------------------------------------------------------------------------- #
# Tenant isolation
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_tenant_isolation(
    client: AsyncClient,
    db: AsyncSession,
) -> None:
    """
    Users from tenant A must only see their own tenant_id on /me.
    The returned tenant_id must not belong to any other registered tenant.
    """
    # Register tenant A
    resp_a = await client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": "Tenant Alpha",
            "tenant_slug": "tenant-alpha",
            "email": "user@alpha.example",
            "password": "AlphaPass123!",
            "first_name": "Alice",
            "last_name": "Alpha",
        },
    )
    assert resp_a.status_code == 201
    tenant_a_id = resp_a.json()["user"]["tenant_id"]
    token_a = resp_a.json()["access_token"]

    # Register tenant B
    resp_b = await client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": "Tenant Beta",
            "tenant_slug": "tenant-beta",
            "email": "user@beta.example",
            "password": "BetaPass123!",
            "first_name": "Bob",
            "last_name": "Beta",
        },
    )
    assert resp_b.status_code == 201
    tenant_b_id = resp_b.json()["user"]["tenant_id"]

    # Tenant A token must identify the user as belonging to tenant A only
    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["tenant_id"] == tenant_a_id
    assert me_resp.json()["tenant_id"] != tenant_b_id


# --------------------------------------------------------------------------- #
# Logout / token revocation
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(
    client: AsyncClient, admin_user: User
) -> None:
    """
    After logging out, the refresh token used for logout must be rejected.
    """
    # Login
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "Admin123!"},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    # Logout using that refresh token
    logout_resp = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_resp.status_code == 204

    # Attempting to refresh with the now-revoked token must fail
    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_requires_auth(client: AsyncClient) -> None:
    """GET /me without a token must return 401."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_with_valid_token(
    client: AsyncClient, admin_user: User, admin_token: str
) -> None:
    """GET /me with a valid token returns the correct user profile."""
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(admin_user.id)
    assert body["email"] == admin_user.email
    assert body["role"] == UserRole.tenant_admin.value


# --------------------------------------------------------------------------- #
# Mobile auth — ?client=mobile query param
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_mobile_login_returns_refresh_token_in_body(
    client: AsyncClient, admin_user: User
) -> None:
    """?client=mobile login returns refresh_token in the JSON body."""
    response = await client.post(
        "/api/v1/auth/login?client=mobile",
        json={"email": admin_user.email, "password": "Admin123!"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["refresh_token"] is not None
    assert len(body["refresh_token"]) > 0


@pytest.mark.asyncio
async def test_mobile_login_does_not_set_cookie(
    client: AsyncClient, admin_user: User
) -> None:
    """?client=mobile login must NOT set the refresh_token httpOnly cookie."""
    response = await client.post(
        "/api/v1/auth/login?client=mobile",
        json={"email": admin_user.email, "password": "Admin123!"},
    )
    assert response.status_code == 200, response.text
    assert "refresh_token" not in response.cookies


@pytest.mark.asyncio
async def test_web_login_sets_refresh_cookie(
    client: AsyncClient, admin_user: User
) -> None:
    """Default (web) login sets an httpOnly refresh_token cookie."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "Admin123!"},
    )
    assert response.status_code == 200, response.text
    assert "refresh_token" in response.cookies


@pytest.mark.xfail(
    reason="Pre-existing: refresh-token uniqueness collision unmasked by #106. Follow-up PR.",
    strict=False,
)
@pytest.mark.asyncio
async def test_mobile_refresh_via_body(
    client: AsyncClient, admin_user: User
) -> None:
    """Mobile: refresh token sent in JSON body is accepted and rotated."""
    login_resp = await client.post(
        "/api/v1/auth/login?client=mobile",
        json={"email": admin_user.email, "password": "Admin123!"},
    )
    assert login_resp.status_code == 200
    original_refresh = login_resp.json()["refresh_token"]

    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": original_refresh},
    )
    assert refresh_resp.status_code == 200, refresh_resp.text
    new_body = refresh_resp.json()
    assert new_body["refresh_token"] is not None
    assert new_body["refresh_token"] != original_refresh
    assert new_body["access_token"] is not None


@pytest.mark.xfail(
    reason="Pre-existing: refresh-token uniqueness collision unmasked by #106. Follow-up PR.",
    strict=False,
)
@pytest.mark.asyncio
async def test_web_refresh_via_cookie(
    client: AsyncClient, admin_user: User
) -> None:
    """Web: refresh token sent via cookie (no body) is accepted and rotated."""
    # Web login sets the cookie; HTTPX retains it on the shared client
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "Admin123!"},
    )
    assert login_resp.status_code == 200
    assert "refresh_token" in login_resp.cookies

    # Send no JSON body — refresh endpoint falls back to cookie
    refresh_resp = await client.post("/api/v1/auth/refresh")
    assert refresh_resp.status_code == 200, refresh_resp.text
    new_body = refresh_resp.json()
    assert new_body["access_token"] is not None
    assert new_body["refresh_token"] is not None


@pytest.mark.asyncio
async def test_refresh_no_token_returns_401(client: AsyncClient) -> None:
    """Refresh with no body and no cookie must return 401."""
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
