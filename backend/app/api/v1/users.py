"""Users API router — tenant-scoped user management."""

from __future__ import annotations

from datetime import UTC
import math
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.database import get_db
from app.core.dependencies import (
    CurrentTenantId,
    CurrentUser,
    require_permission,
    require_role,
)
from app.core.security import get_password_hash
from app.models.user import User, UserRole

logger = structlog.get_logger(__name__)
router = APIRouter()


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #

def _paginate_meta(total: int, page: int, limit: int) -> dict:
    pages = math.ceil(total / limit) if limit > 0 else 0
    return {"total": total, "page": page, "limit": limit, "pages": pages}


def _user_to_dict(user: User, *, include_sensitive: bool = False) -> dict:
    d = {
        "id": str(user.id),
        "tenant_id": str(user.tenant_id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.full_name,
        "phone": user.phone,
        "role": user.role.value,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "mfa_enabled": user.mfa_enabled,
        "avatar_url": user.avatar_url,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }
    return d


async def _get_user_or_404(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> User:
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.tenant_id == tenant_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _role_rank(role: UserRole) -> int:
    """Higher = more privileged. Used for permission checks."""
    ranks = {
        UserRole.platform_owner: 100,
        UserRole.tenant_admin: 80,
        UserRole.manager: 60,
        UserRole.employee: 40,
        UserRole.client_user: 20,
    }
    return ranks.get(role, 0)


# --------------------------------------------------------------------------- #
# GET /me — current user
# --------------------------------------------------------------------------- #

@router.get("/me")
async def get_me(
    current_user: CurrentUser,
):
    """Return the currently authenticated user's profile."""
    return {"data": _user_to_dict(current_user)}


# --------------------------------------------------------------------------- #
# GET / — list users in tenant
# --------------------------------------------------------------------------- #

@router.get(
    "",
    dependencies=[Depends(require_permission("users", "read"))],
)
async def list_users(
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    role: Annotated[str | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
):
    """
    List all users within the current tenant.
    Accessible by managers and above.
    """
    filters = [
        User.tenant_id == tenant_id,
        User.deleted_at.is_(None),
    ]

    if role:
        try:
            filters.append(User.role == UserRole(role))
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid role value: {role}",
            ) from err
    if is_active is not None:
        filters.append(User.is_active == is_active)
    if search:
        term = f"%{search}%"
        filters.append(
            User.email.ilike(term)
            | User.first_name.ilike(term)
            | User.last_name.ilike(term)
        )

    combined = and_(*filters)

    total = (
        await db.execute(select(func.count()).select_from(User).where(combined))
    ).scalar_one()

    offset = (page - 1) * limit
    rows = (
        await db.execute(
            select(User)
            .where(combined)
            .order_by(User.last_name.asc(), User.first_name.asc())
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()

    return {
        "data": [_user_to_dict(u) for u in rows],
        "meta": _paginate_meta(total, page, limit),
    }


# --------------------------------------------------------------------------- #
# POST / — create / invite user
# --------------------------------------------------------------------------- #

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("tenant_admin", "platform_owner"))],
)
async def create_user(
    payload: dict,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Invite / create a user within the current tenant.
    Only tenant_admin or platform_owner may call this.
    """
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password", "").strip()
    first_name = (payload.get("first_name") or "").strip()
    last_name = (payload.get("last_name") or "").strip()

    if not email:
        raise HTTPException(status_code=422, detail="email is required")
    if not password:
        raise HTTPException(status_code=422, detail="password is required")
    if not first_name:
        raise HTTPException(status_code=422, detail="first_name is required")
    if not last_name:
        raise HTTPException(status_code=422, detail="last_name is required")

    # Email uniqueness within tenant
    dupe = (
        await db.execute(
            select(func.count()).select_from(User).where(
                User.tenant_id == tenant_id,
                User.email == email,
                User.deleted_at.is_(None),
            )
        )
    ).scalar_one()
    if dupe > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with email '{email}' already exists in this tenant",
        )

    # Role validation — admins cannot create higher-privileged users
    role_str = payload.get("role", UserRole.employee.value)
    try:
        new_role = UserRole(role_str)
    except ValueError as err:
        raise HTTPException(
            status_code=422, detail=f"Invalid role: {role_str}"
        ) from err

    if _role_rank(new_role) >= _role_rank(current_user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create a user with a role equal to or higher than your own",
        )

    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email=email,
        hashed_password=get_password_hash(password),
        first_name=first_name,
        last_name=last_name,
        phone=payload.get("phone"),
        role=new_role,
        is_active=payload.get("is_active", True),
        is_verified=False,
        avatar_url=payload.get("avatar_url"),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    logger.info(
        "user_created",
        tenant_id=str(tenant_id),
        user_id=str(user.id),
        email=user.email,
        role=user.role.value,
        created_by=str(current_user.id),
    )

    return {"data": _user_to_dict(user)}


# --------------------------------------------------------------------------- #
# GET /{id} — get user
# --------------------------------------------------------------------------- #

@router.get("/{user_id}")
async def get_user(
    user_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch a user by ID.
    Users may view their own profile; managers+ may view any user in the tenant.
    """
    is_self = current_user.id == user_id
    is_manager_plus = _role_rank(current_user.role) >= _role_rank(UserRole.manager)

    if not is_self and not is_manager_plus:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this user",
        )

    user = await _get_user_or_404(user_id, tenant_id, db)
    return {"data": _user_to_dict(user)}


# --------------------------------------------------------------------------- #
# PATCH /{id} — update user
# --------------------------------------------------------------------------- #

@router.patch("/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    payload: dict,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Update a user.
    - Any user can update their own profile fields (name, phone, avatar, password).
    - tenant_admin+ can additionally update role and is_active.
    """
    is_self = current_user.id == user_id
    is_admin_plus = _role_rank(current_user.role) >= _role_rank(UserRole.tenant_admin)

    if not is_self and not is_admin_plus:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this user",
        )

    user = await _get_user_or_404(user_id, tenant_id, db)

    # Profile fields — any user can update their own
    profile_fields = {"first_name", "last_name", "phone", "avatar_url"}
    for field in profile_fields:
        if field in payload:
            setattr(user, field, payload[field])

    # Password change
    if "password" in payload:
        new_password = (payload["password"] or "").strip()
        if len(new_password) < 8:
            raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
        user.hashed_password = get_password_hash(new_password)

    # Admin-only fields
    if is_admin_plus:
        if "is_active" in payload:
            user.is_active = bool(payload["is_active"])

        if "role" in payload:
            try:
                new_role = UserRole(payload["role"])
            except ValueError as err:
                raise HTTPException(
                    status_code=422, detail=f"Invalid role: {payload['role']}"
                ) from err

            # Prevent privilege escalation
            if _role_rank(new_role) >= _role_rank(current_user.role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot assign a role equal to or higher than your own",
                )
            user.role = new_role

    elif any(k in payload for k in ("is_active", "role")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can modify role or active status",
        )

    await db.flush()
    await db.refresh(user)

    logger.info(
        "user_updated",
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        updated_by=str(current_user.id),
        fields=list(payload.keys()),
    )

    return {"data": _user_to_dict(user)}


# --------------------------------------------------------------------------- #
# DELETE /{id} — deactivate user (soft delete)
# --------------------------------------------------------------------------- #

@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("tenant_admin", "platform_owner"))],
)
async def deactivate_user(
    user_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Soft-delete (deactivate) a user within the tenant.
    tenant_admin only. Cannot deactivate yourself.
    """
    from datetime import datetime

    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account",
        )

    user = await _get_user_or_404(user_id, tenant_id, db)

    if _role_rank(user.role) >= _role_rank(current_user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot deactivate a user with equal or higher privilege",
        )

    user.deleted_at = datetime.now(tz=UTC)
    user.is_active = False
    await db.flush()

    logger.info(
        "user_deactivated",
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        deactivated_by=str(current_user.id),
    )
