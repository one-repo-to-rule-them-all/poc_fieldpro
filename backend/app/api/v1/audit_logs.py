"""Audit log read API — Phase 4 of #52.

Two endpoints, both admin-only and tenant-scoped:

    GET /api/v1/audit-logs            — paginated list, filterable
    GET /api/v1/audit-logs/{id}       — single row detail

Tenant scoping:
    * platform_owner — sees rows across all tenants
    * tenant_admin   — sees own tenant only

The list endpoint JOINs to users for actor_email / actor_name so clients
read the row in human-readable form. The same JOIN is exposed in the
``v_audit_events`` Postgres view for psql / ad-hoc queries; this API is
the same data via FastAPI.
"""

from __future__ import annotations

from datetime import datetime
import math
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.database import get_db
from app.core.dependencies import CurrentTenantId, CurrentUser, require_role
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.audit_log import AuditLogDetailResponse, AuditLogListResponse
from app.schemas.common import PaginatedResponse

logger = structlog.get_logger(__name__)
router = APIRouter()


# --------------------------------------------------------------------------- #
# Serializers
# --------------------------------------------------------------------------- #


def _audit_row_to_list_dict(row: AuditLog, actor: User | None) -> dict:
    """Light list-shape dict matching AuditLogListResponse fields."""
    return {
        "id": row.id,
        "created_at": row.created_at,
        "tenant_id": row.tenant_id,
        "user_id": row.user_id,
        "actor_email": actor.email if actor else None,
        "actor_name": (
            f"{actor.first_name} {actor.last_name}".strip() if actor else None
        ),
        "action": row.action,
        "resource_type": row.resource_type,
        "resource_id": row.resource_id,
        "request_id": row.request_id,
        "ip_address": row.ip_address,
    }


def _audit_row_to_detail_dict(row: AuditLog, actor: User | None) -> dict:
    """Full detail dict matching AuditLogDetailResponse fields."""
    return {
        **_audit_row_to_list_dict(row, actor),
        "user_agent": row.user_agent,
        "old_values": row.old_values,
        "new_values": row.new_values,
    }


# --------------------------------------------------------------------------- #
# GET / — paginated list
# --------------------------------------------------------------------------- #


@router.get(
    "/",
    response_model=PaginatedResponse[AuditLogListResponse],
    summary="List audit log events",
    description=(
        "Paginated list of audit events. Tenant-scoped: admins see their own "
        "tenant only; platform_owner sees across all tenants. Filterable by "
        "resource_type, user_id, action, request_id, and a created_at "
        "date range (from/to). Ordered newest first."
    ),
)
async def list_audit_logs(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role("platform_owner", "tenant_admin"))],
    resource_type: Annotated[
        str | None,
        Query(max_length=100, description="Filter by resource_type (e.g. 'WorkOrder')"),
    ] = None,
    user_id: Annotated[
        uuid.UUID | None,
        Query(description="Filter by actor (user_id)"),
    ] = None,
    action: Annotated[
        str | None,
        Query(max_length=100, description="Filter by action verb (e.g. 'created')"),
    ] = None,
    request_id: Annotated[
        str | None,
        Query(
            max_length=64,
            description="Filter by HTTP request id — every row from the same request",
        ),
    ] = None,
    from_: Annotated[
        datetime | None,
        Query(alias="from", description="Lower bound on created_at (inclusive)"),
    ] = None,
    to: Annotated[
        datetime | None,
        Query(description="Upper bound on created_at (inclusive)"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict:
    """Paginated audit log listing — tenant-scoped, role-gated."""
    filters: list = []

    # Tenant scoping — platform_owner crosses tenants
    if str(current_user.role.value) != "platform_owner":
        filters.append(AuditLog.tenant_id == tenant_id)

    if resource_type:
        filters.append(AuditLog.resource_type == resource_type)
    if user_id:
        filters.append(AuditLog.user_id == user_id)
    if action:
        filters.append(AuditLog.action == action)
    if request_id:
        filters.append(AuditLog.request_id == request_id)
    if from_:
        filters.append(AuditLog.created_at >= from_)
    if to:
        filters.append(AuditLog.created_at <= to)

    where = and_(*filters) if filters else None

    # Count
    count_q = select(func.count()).select_from(AuditLog)
    if where is not None:
        count_q = count_q.where(where)
    total = (await db.execute(count_q)).scalar_one()

    # Page query — JOIN to User for actor_email / actor_name. LEFT OUTER
    # so anonymous or hard-deleted users still surface their rows.
    offset = (page - 1) * page_size
    page_q = (
        select(AuditLog, User)
        .outerjoin(User, User.id == AuditLog.user_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    if where is not None:
        page_q = page_q.where(where)

    rows = (await db.execute(page_q)).all()
    items = [_audit_row_to_list_dict(row, actor) for row, actor in rows]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if page_size > 0 else 0,
    }


# --------------------------------------------------------------------------- #
# GET /{audit_log_id} — single row detail
# --------------------------------------------------------------------------- #


@router.get(
    "/{audit_log_id}",
    response_model=AuditLogDetailResponse,
    summary="Audit log event detail",
    description=(
        "Single row with full old_values / new_values. Same tenant scoping "
        "and role gating as the list endpoint."
    ),
)
async def get_audit_log(
    audit_log_id: uuid.UUID,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role("platform_owner", "tenant_admin"))],
) -> dict:
    """Detail for one audit event — 404 if missing or out of tenant scope."""
    q = (
        select(AuditLog, User)
        .outerjoin(User, User.id == AuditLog.user_id)
        .where(AuditLog.id == audit_log_id)
    )

    if str(current_user.role.value) != "platform_owner":
        q = q.where(AuditLog.tenant_id == tenant_id)

    result = (await db.execute(q)).first()
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log entry not found",
        )

    row, actor = result
    return _audit_row_to_detail_dict(row, actor)
