"""FastAPI dependency injection functions."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.database import get_db
from app.core.security import verify_access_token
from app.models.user import User

logger = structlog.get_logger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


# --------------------------------------------------------------------------- #
# Current user extraction
# --------------------------------------------------------------------------- #

async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    db: AsyncSession = Depends(get_db),
):
    """
    Decode the Bearer JWT, load the user from DB.

    Raises 401 if token is missing, invalid, or user not found.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_access_token(credentials.credentials)
    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_active_user(
    current_user=Depends(get_current_user),
):
    """Raise 403 if the authenticated user is inactive."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


# --------------------------------------------------------------------------- #
# Role-based access control
# --------------------------------------------------------------------------- #

def require_role(*roles: str):
    """
    Dependency factory: raise 403 if current user's role is not in *roles*.

    Usage::

        @router.get("/admin-only")
        async def admin_route(user = Depends(require_role("platform_owner", "tenant_admin"))):
            ...
    """
    async def _check_role(current_user=Depends(get_current_active_user)):
        if current_user.role.value not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires one of the following roles: {', '.join(roles)}",
            )
        return current_user

    return _check_role


# --------------------------------------------------------------------------- #
# Permission-based access control
# --------------------------------------------------------------------------- #

# A simple permission map keyed by (role, resource, action).
# In a full implementation this would be stored in DB / Redis.
_PERMISSION_MAP: dict[tuple[str, str, str], bool] = {
    # platform_owner has all permissions
    **{("platform_owner", res, act): True for res in ["*"] for act in ["*"]},
    # tenant_admin
    ("tenant_admin", "work_orders", "read"): True,
    ("tenant_admin", "work_orders", "write"): True,
    ("tenant_admin", "work_orders", "delete"): True,
    ("tenant_admin", "users", "read"): True,
    ("tenant_admin", "users", "write"): True,
    ("tenant_admin", "clients", "read"): True,
    ("tenant_admin", "clients", "write"): True,
    ("tenant_admin", "clients", "delete"): True,
    ("tenant_admin", "locations", "read"): True,
    ("tenant_admin", "locations", "write"): True,
    ("tenant_admin", "locations", "delete"): True,
    ("tenant_admin", "crews", "read"): True,
    ("tenant_admin", "crews", "write"): True,
    ("tenant_admin", "crews", "delete"): True,
    ("tenant_admin", "invoices", "read"): True,
    ("tenant_admin", "invoices", "write"): True,
    ("tenant_admin", "analytics", "read"): True,
    # manager
    ("manager", "work_orders", "read"): True,
    ("manager", "work_orders", "write"): True,
    ("manager", "work_orders", "delete"): True,
    ("manager", "users", "read"): True,
    ("manager", "clients", "read"): True,
    ("manager", "clients", "write"): True,
    ("manager", "clients", "delete"): True,
    ("manager", "locations", "read"): True,
    ("manager", "locations", "write"): True,
    ("manager", "locations", "delete"): True,
    ("manager", "crews", "read"): True,
    ("manager", "crews", "write"): True,
    ("manager", "crews", "delete"): True,
    ("manager", "invoices", "read"): True,
    ("manager", "invoices", "write"): True,
    ("manager", "analytics", "read"): True,
    # employee
    ("employee", "work_orders", "read"): True,
    ("employee", "work_orders", "checkin"): True,
    ("employee", "clients", "read"): True,
    ("employee", "locations", "read"): True,
    ("employee", "crews", "read"): True,
    # client_user
    ("client_user", "work_orders", "read"): True,
    ("client_user", "invoices", "read"): True,
}


def require_permission(resource: str, action: str):
    """
    Dependency factory: raise 403 if the user lacks the given resource/action permission.

    Usage::

        @router.delete("/{id}")
        async def delete(user = Depends(require_permission("work_orders", "delete"))):
            ...
    """
    async def _check_permission(current_user=Depends(get_current_active_user)):
        role = current_user.role.value
        # platform_owner always passes
        if role == "platform_owner":
            return current_user
        # Check wildcard and specific key
        allowed = (
            _PERMISSION_MAP.get(("*", "*", "*"), False)
            or _PERMISSION_MAP.get((role, "*", "*"), False)
            or _PERMISSION_MAP.get((role, resource, "*"), False)
            or _PERMISSION_MAP.get((role, resource, action), False)
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You do not have permission to {action} {resource}",
            )
        return current_user

    return _check_permission


# --------------------------------------------------------------------------- #
# Tenant isolation helper
# --------------------------------------------------------------------------- #

async def get_tenant_id(
    current_user=Depends(get_current_active_user),
) -> UUID:
    """Extract the tenant_id from the currently authenticated user."""
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no associated tenant",
        )
    return current_user.tenant_id


# --------------------------------------------------------------------------- #
# Annotated type aliases (use these in route signatures for brevity)
# --------------------------------------------------------------------------- #

DBSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_active_user)]
CurrentTenantId = Annotated[UUID, Depends(get_tenant_id)]
