"""Crews API router — crew management and membership."""

from __future__ import annotations

from datetime import UTC, datetime
import math
from typing import Annotated, Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.core.database import get_db
from app.core.dependencies import (
    CurrentTenantId,
    CurrentUser,
    require_permission,
)
from app.models.crew import Crew, CrewMember, CrewMemberRole
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.crew import CrewDetailResponse, CrewListResponse, CrewMemberDetail

logger = structlog.get_logger(__name__)
router = APIRouter()


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #

def _paginate_meta(total: int, page: int, limit: int) -> dict:
    pages = math.ceil(total / limit) if limit > 0 else 0
    return {"total": total, "page": page, "limit": limit, "pages": pages}


def _member_to_dict(member: CrewMember) -> dict:
    user_dict: dict | None = None
    user_obj = getattr(member, "user", None)
    if user_obj is not None:
        user_dict = {
            "id": str(user_obj.id),
            "first_name": user_obj.first_name,
            "last_name": user_obj.last_name,
            "email": user_obj.email,
        }
    return {
        "id": str(member.id),
        "crew_id": str(member.crew_id),
        "user_id": str(member.user_id),
        "user": user_dict,
        "role": member.role.value,
        "joined_at": member.joined_at.isoformat(),
        "left_at": member.left_at.isoformat() if member.left_at else None,
        "is_active": member.is_active,
    }


def _crew_to_dict(crew: Crew, include_members: bool = False) -> dict:
    d: dict[str, Any] = {
        "id": str(crew.id),
        "tenant_id": str(crew.tenant_id),
        "name": crew.name,
        "code": crew.code,
        "description": crew.description,
        "is_active": crew.is_active,
        "created_at": crew.created_at.isoformat(),
        "updated_at": crew.updated_at.isoformat() if crew.updated_at else None,
    }
    if include_members:
        d["members"] = [_member_to_dict(m) for m in crew.members]
    return d


async def _get_crew_or_404(
    crew_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
    load_members: bool = False,
) -> Crew:
    q = select(Crew).where(
        Crew.id == crew_id,
        Crew.tenant_id == tenant_id,
        Crew.deleted_at.is_(None),
    )
    if load_members:
        q = q.options(selectinload(Crew.members).selectinload(CrewMember.user))

    result = await db.execute(q)
    crew = result.scalar_one_or_none()
    if crew is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crew not found")
    return crew


# --------------------------------------------------------------------------- #
# GET / — list crews
# --------------------------------------------------------------------------- #

@router.get("", response_model=PaginatedResponse[CrewListResponse])
async def list_crews(
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    is_active: Annotated[bool | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    """Return a paginated list of crews for the current tenant."""
    filters = [
        Crew.tenant_id == tenant_id,
        Crew.deleted_at.is_(None),
    ]
    if is_active is not None:
        filters.append(Crew.is_active == is_active)
    if search:
        filters.append(
            Crew.name.ilike(f"%{search}%") | Crew.code.ilike(f"%{search}%")
        )

    combined = and_(*filters)

    total = (
        await db.execute(select(func.count()).select_from(Crew).where(combined))
    ).scalar_one()

    offset = (page - 1) * page_size
    rows = (
        await db.execute(
            select(Crew)
            .where(combined)
            .order_by(Crew.name.asc())
            .offset(offset)
            .limit(page_size)
        )
    ).scalars().all()

    crew_ids = [c.id for c in rows]
    member_counts: dict[uuid.UUID, int] = {}
    lead_names: dict[uuid.UUID, str] = {}
    if crew_ids:
        count_rows = await db.execute(
            select(CrewMember.crew_id, func.count(CrewMember.id))
            .where(
                CrewMember.crew_id.in_(crew_ids),
                CrewMember.tenant_id == tenant_id,
                CrewMember.left_at.is_(None),
            )
            .group_by(CrewMember.crew_id)
        )
        member_counts = {row[0]: row[1] for row in count_rows}

        lead_rows = await db.execute(
            select(CrewMember.crew_id, User.first_name, User.last_name)
            .join(User, User.id == CrewMember.user_id)
            .where(
                CrewMember.crew_id.in_(crew_ids),
                CrewMember.tenant_id == tenant_id,
                CrewMember.left_at.is_(None),
                CrewMember.role == CrewMemberRole.lead,
            )
        )
        lead_names = {
            row[0]: f"{row[1]} {row[2]}" for row in lead_rows
        }

    items = []
    for c in rows:
        d = _crew_to_dict(c)
        d["member_count"] = member_counts.get(c.id, 0)
        d["lead_name"] = lead_names.get(c.id)
        items.append(d)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if page_size > 0 else 0,
    }


# --------------------------------------------------------------------------- #
# POST / — create crew
# --------------------------------------------------------------------------- #

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=CrewDetailResponse,
    dependencies=[Depends(require_permission("crews", "write"))],
)
async def create_crew(
    payload: dict,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Create a new crew. Requires crews:write permission."""
    name = (payload.get("name") or "").strip()
    code = (payload.get("code") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    if not code:
        raise HTTPException(status_code=422, detail="code is required")

    dupe = (
        await db.execute(
            select(func.count()).select_from(Crew).where(
                Crew.tenant_id == tenant_id,
                Crew.code == code,
                Crew.deleted_at.is_(None),
            )
        )
    ).scalar_one()
    if dupe > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A crew with code '{code}' already exists in this tenant",
        )

    crew = Crew(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=name,
        code=code,
        description=payload.get("description"),
        is_active=payload.get("is_active", True),
    )
    db.add(crew)
    await db.flush()
    await db.refresh(crew)

    logger.info(
        "crew_created",
        tenant_id=str(tenant_id),
        crew_id=str(crew.id),
        code=crew.code,
        created_by=str(current_user.id),
    )

    return _crew_to_dict(crew, include_members=False)


# --------------------------------------------------------------------------- #
# GET /{id} — crew detail with active members
# --------------------------------------------------------------------------- #

@router.get("/{crew_id}", response_model=CrewDetailResponse)
async def get_crew(
    crew_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Fetch a crew with its current active members."""
    crew = await _get_crew_or_404(crew_id, tenant_id, db, load_members=True)
    return _crew_to_dict(crew, include_members=True)


# --------------------------------------------------------------------------- #
# PATCH /{id} — update crew
# --------------------------------------------------------------------------- #

@router.patch(
    "/{crew_id}",
    response_model=CrewDetailResponse,
    dependencies=[Depends(require_permission("crews", "write"))],
)
async def update_crew(
    crew_id: uuid.UUID,
    payload: dict,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Partially update a crew. Requires crews:write permission."""
    crew = await _get_crew_or_404(crew_id, tenant_id, db)

    for field in ("name", "description", "is_active"):
        if field in payload:
            setattr(crew, field, payload[field])

    if "code" in payload:
        new_code = (payload["code"] or "").strip()
        if new_code != crew.code:
            dupe = (
                await db.execute(
                    select(func.count()).select_from(Crew).where(
                        Crew.tenant_id == tenant_id,
                        Crew.code == new_code,
                        Crew.deleted_at.is_(None),
                    )
                )
            ).scalar_one()
            if dupe > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A crew with code '{new_code}' already exists",
                )
            crew.code = new_code

    await db.flush()
    await db.refresh(crew)

    logger.info(
        "crew_updated",
        tenant_id=str(tenant_id),
        crew_id=str(crew_id),
        updated_by=str(current_user.id),
        fields=list(payload.keys()),
    )

    return _crew_to_dict(crew)


# --------------------------------------------------------------------------- #
# DELETE /{id} — soft delete crew
# --------------------------------------------------------------------------- #

@router.delete(
    "/{crew_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("crews", "delete"))],
)
async def delete_crew(
    crew_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a crew. Requires crews:delete permission."""
    crew = await _get_crew_or_404(crew_id, tenant_id, db)
    crew.deleted_at = datetime.now(tz=UTC)
    crew.is_active = False
    await db.flush()

    logger.info(
        "crew_deleted",
        tenant_id=str(tenant_id),
        crew_id=str(crew_id),
        deleted_by=str(current_user.id),
    )


# --------------------------------------------------------------------------- #
# POST /{id}/members — add member to crew
# --------------------------------------------------------------------------- #

@router.post(
    "/{crew_id}/members",
    status_code=status.HTTP_201_CREATED,
    response_model=CrewMemberDetail,
    dependencies=[Depends(require_permission("crews", "write"))],
)
async def add_crew_member(
    crew_id: uuid.UUID,
    payload: dict,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Add a user to a crew.
    Validates that the user exists within the same tenant.
    """
    # _get_crew_or_404 raises HTTPException(404) if the crew doesn't exist
    # in this tenant; the return value isn't used here, just the side effect.
    await _get_crew_or_404(crew_id, tenant_id, db)

    user_id_val = payload.get("user_id")
    if not user_id_val:
        raise HTTPException(status_code=422, detail="user_id is required")
    user_id = uuid.UUID(str(user_id_val))

    # Verify user belongs to same tenant
    user_result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.tenant_id == tenant_id,
            User.deleted_at.is_(None),
            User.is_active.is_(True),
        )
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or is not active in this tenant",
        )

    # Check for existing active membership
    existing = (
        await db.execute(
            select(CrewMember).where(
                CrewMember.crew_id == crew_id,
                CrewMember.user_id == user_id,
                CrewMember.tenant_id == tenant_id,
                CrewMember.left_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already an active member of this crew",
        )

    role_str = payload.get("role", CrewMemberRole.member.value)
    try:
        member_role = CrewMemberRole(role_str)
    except ValueError as err:
        raise HTTPException(
            status_code=422, detail=f"Invalid crew member role: {role_str}"
        ) from err

    member = CrewMember(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        crew_id=crew_id,
        user_id=user_id,
        role=member_role,
        joined_at=datetime.now(tz=UTC),
    )
    db.add(member)
    await db.flush()
    await db.refresh(member)
    member.user = user  # avoid lazy-load in async context

    logger.info(
        "crew_member_added",
        tenant_id=str(tenant_id),
        crew_id=str(crew_id),
        user_id=str(user_id),
        added_by=str(current_user.id),
    )

    return _member_to_dict(member)


# --------------------------------------------------------------------------- #
# DELETE /{id}/members/{user_id} — remove member
# --------------------------------------------------------------------------- #

@router.delete(
    "/{crew_id}/members/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=CrewMemberDetail,
    dependencies=[Depends(require_permission("crews", "write"))],
)
async def remove_crew_member(
    crew_id: uuid.UUID,
    user_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Remove a user from a crew by setting left_at = now().
    The record is preserved for audit purposes.
    """
    await _get_crew_or_404(crew_id, tenant_id, db)

    result = await db.execute(
        select(CrewMember)
        .options(selectinload(CrewMember.user))
        .where(
            CrewMember.crew_id == crew_id,
            CrewMember.user_id == user_id,
            CrewMember.tenant_id == tenant_id,
            CrewMember.left_at.is_(None),
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active crew membership not found",
        )

    member.left_at = datetime.now(tz=UTC)
    await db.flush()

    logger.info(
        "crew_member_removed",
        tenant_id=str(tenant_id),
        crew_id=str(crew_id),
        user_id=str(user_id),
        removed_by=str(current_user.id),
    )

    return _member_to_dict(member)
