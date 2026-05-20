"""Clients API router — full CRUD + nested locations and work orders."""

from __future__ import annotations

from datetime import UTC
import math
from typing import Annotated, Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.database import get_db
from app.core.dependencies import (
    CurrentTenantId,
    CurrentUser,
    require_permission,
)
from app.models.client import Client
from app.models.location import Location
from app.models.work_order import WorkOrder
from app.schemas.client import ClientDetailResponse, ClientListResponse
from app.schemas.common import PaginatedResponse

logger = structlog.get_logger(__name__)
router = APIRouter()


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #

def _paginate_meta(total: int, page: int, limit: int) -> dict:
    pages = math.ceil(total / limit) if limit > 0 else 0
    return {"total": total, "page": page, "limit": limit, "pages": pages}


async def _get_client_or_404(
    client_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> Client:
    result = await db.execute(
        select(Client).where(
            Client.id == client_id,
            Client.tenant_id == tenant_id,
            Client.deleted_at.is_(None),
        )
    )
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return client


def _client_to_dict(client: Client, location_count: int | None = None) -> dict:
    d: dict[str, Any] = {
        "id": str(client.id),
        "tenant_id": str(client.tenant_id),
        "name": client.name,
        "code": client.code,
        "industry": client.industry.value if client.industry else None,
        "billing_address": client.billing_address,
        "billing_email": client.billing_email,
        "billing_phone": client.billing_phone,
        "contract_start_date": (
            client.contract_start_date.isoformat() if client.contract_start_date else None
        ),
        "contract_end_date": (
            client.contract_end_date.isoformat() if client.contract_end_date else None
        ),
        "notes": client.notes,
        "is_active": client.is_active,
        "created_at": client.created_at.isoformat(),
        "updated_at": client.updated_at.isoformat() if client.updated_at else None,
    }
    if location_count is not None:
        d["location_count"] = location_count
    return d


# --------------------------------------------------------------------------- #
# GET / — list clients
# --------------------------------------------------------------------------- #

@router.get("", response_model=PaginatedResponse[ClientListResponse])
async def list_clients(
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    search: Annotated[str | None, Query(max_length=200)] = None,
    is_active: Annotated[bool | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    """Return a paginated, filtered list of clients for the current tenant."""
    filters = [
        Client.tenant_id == tenant_id,
        Client.deleted_at.is_(None),
    ]
    if search:
        filters.append(
            Client.name.ilike(f"%{search}%") | Client.code.ilike(f"%{search}%")
        )
    if is_active is not None:
        filters.append(Client.is_active == is_active)

    combined = and_(*filters)

    count_result = await db.execute(
        select(func.count()).select_from(Client).where(combined)
    )
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        select(Client)
        .where(combined)
        .order_by(Client.name.asc())
        .offset(offset)
        .limit(page_size)
    )
    clients = result.scalars().all()

    pages = math.ceil(total / page_size) if page_size > 0 else 0
    return {
        "items": [_client_to_dict(c) for c in clients],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


# --------------------------------------------------------------------------- #
# POST / — create client
# --------------------------------------------------------------------------- #

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ClientDetailResponse,
    dependencies=[Depends(require_permission("clients", "write"))],
)
async def create_client(
    payload: dict,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Create a new client. Requires clients:write permission."""
    from app.models.client import Industry

    # Validate required fields
    name = payload.get("name", "").strip()
    code = payload.get("code", "").strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="name is required"
        )
    if not code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="code is required"
        )

    # Check uniqueness of code within tenant
    exists_result = await db.execute(
        select(func.count()).select_from(Client).where(
            Client.tenant_id == tenant_id,
            Client.code == code,
            Client.deleted_at.is_(None),
        )
    )
    if exists_result.scalar_one() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A client with code '{code}' already exists in this tenant",
        )

    industry_val = payload.get("industry")
    try:
        industry = Industry(industry_val) if industry_val else None
    except ValueError as err:
        valid = ", ".join(repr(i.value) for i in Industry)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid industry '{industry_val}'. Must be one of: {valid}",
        ) from err

    client = Client(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=name,
        code=code,
        industry=industry,
        billing_address=payload.get("billing_address") or {},
        billing_email=payload.get("billing_email"),
        billing_phone=payload.get("billing_phone"),
        contract_start_date=payload.get("contract_start_date"),
        contract_end_date=payload.get("contract_end_date"),
        notes=payload.get("notes"),
        is_active=payload.get("is_active", True),
    )
    db.add(client)
    try:
        await db.flush()
    except IntegrityError as err:
        # Race: another request created a client with the same code between
        # our pre-check (line ~169) and this flush. Translate the constraint
        # violation to a clean 409 instead of letting it bubble as a 500.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A client with code '{code}' already exists in this tenant",
        ) from err
    await db.refresh(client)

    logger.info(
        "client_created",
        tenant_id=str(tenant_id),
        client_id=str(client.id),
        code=client.code,
        created_by=str(current_user.id),
    )

    return _client_to_dict(client, location_count=0)


# --------------------------------------------------------------------------- #
# GET /{id} — get single client with location count
# --------------------------------------------------------------------------- #

@router.get("/{client_id}", response_model=ClientDetailResponse)
async def get_client(
    client_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Fetch a single client including its active location count."""
    client = await _get_client_or_404(client_id, tenant_id, db)

    count_result = await db.execute(
        select(func.count()).select_from(Location).where(
            Location.client_id == client_id,
            Location.tenant_id == tenant_id,
            Location.deleted_at.is_(None),
        )
    )
    location_count = count_result.scalar_one()

    return _client_to_dict(client, location_count=location_count)


# --------------------------------------------------------------------------- #
# PATCH /{id} — update client
# --------------------------------------------------------------------------- #

@router.patch(
    "/{client_id}",
    response_model=ClientDetailResponse,
    dependencies=[Depends(require_permission("clients", "write"))],
)
async def update_client(
    client_id: uuid.UUID,
    payload: dict,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Partially update a client. Requires clients:write permission."""
    from app.models.client import Industry

    client = await _get_client_or_404(client_id, tenant_id, db)

    updatable_fields = {
        "name", "billing_address", "billing_email", "billing_phone",
        "contract_start_date", "contract_end_date", "notes", "is_active",
    }

    for field in updatable_fields:
        if field in payload:
            setattr(client, field, payload[field])

    if "industry" in payload:
        client.industry = Industry(payload["industry"]) if payload["industry"] else None

    if "code" in payload:
        new_code = payload["code"].strip()
        if new_code != client.code:
            dupe = await db.execute(
                select(func.count()).select_from(Client).where(
                    Client.tenant_id == tenant_id,
                    Client.code == new_code,
                    Client.deleted_at.is_(None),
                )
            )
            if dupe.scalar_one() > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A client with code '{new_code}' already exists",
                )
            client.code = new_code

    await db.flush()
    await db.refresh(client)

    logger.info(
        "client_updated",
        tenant_id=str(tenant_id),
        client_id=str(client_id),
        updated_by=str(current_user.id),
        fields=list(payload.keys()),
    )

    return _client_to_dict(client)


# --------------------------------------------------------------------------- #
# DELETE /{id} — soft delete
# --------------------------------------------------------------------------- #

@router.delete(
    "/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("clients", "delete"))],
)
async def delete_client(
    client_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a client. Requires clients:delete permission."""
    from datetime import datetime

    client = await _get_client_or_404(client_id, tenant_id, db)

    # Guard: check for open work orders
    open_wo_count_result = await db.execute(
        select(func.count()).select_from(WorkOrder).where(
            WorkOrder.client_id == client_id,
            WorkOrder.tenant_id == tenant_id,
            WorkOrder.deleted_at.is_(None),
            WorkOrder.status.in_(["draft", "scheduled", "in_progress", "on_hold"]),
        )
    )
    if open_wo_count_result.scalar_one() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a client with open work orders",
        )

    client.deleted_at = datetime.now(tz=UTC)
    client.is_active = False
    await db.flush()

    logger.info(
        "client_deleted",
        tenant_id=str(tenant_id),
        client_id=str(client_id),
        deleted_by=str(current_user.id),
    )


# --------------------------------------------------------------------------- #
# GET /{id}/locations — paginated locations for a client
# --------------------------------------------------------------------------- #

@router.get("/{client_id}/locations")
async def list_client_locations(
    client_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    is_active: Annotated[bool | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    """List all service locations belonging to this client (paginated)."""
    await _get_client_or_404(client_id, tenant_id, db)

    filters = [
        Location.client_id == client_id,
        Location.tenant_id == tenant_id,
        Location.deleted_at.is_(None),
    ]
    if is_active is not None:
        filters.append(Location.is_active == is_active)

    combined = and_(*filters)

    total = (
        await db.execute(select(func.count()).select_from(Location).where(combined))
    ).scalar_one()

    offset = (page - 1) * page_size
    rows = (
        await db.execute(
            select(Location)
            .where(combined)
            .order_by(Location.name.asc())
            .offset(offset)
            .limit(page_size)
        )
    ).scalars().all()

    items = [
        {
            "id": str(loc.id),
            "client_id": str(loc.client_id),
            "name": loc.name,
            "address": loc.address,
            "latitude": float(loc.latitude) if loc.latitude is not None else None,
            "longitude": float(loc.longitude) if loc.longitude is not None else None,
            "geofence_radius_meters": loc.geofence_radius_meters,
            "access_instructions": loc.access_instructions,
            "special_requirements": loc.special_requirements,
            "is_active": loc.is_active,
            "qr_code_token": loc.qr_code_token,
            "created_at": loc.created_at.isoformat(),
        }
        for loc in rows
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if page_size > 0 else 0,
    }


# --------------------------------------------------------------------------- #
# GET /{id}/work-orders — paginated work orders for a client
# --------------------------------------------------------------------------- #

@router.get("/{client_id}/work-orders")
async def list_client_work_orders(
    client_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    wo_status: Annotated[str | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    """List all work orders for this client (paginated)."""
    await _get_client_or_404(client_id, tenant_id, db)

    filters = [
        WorkOrder.client_id == client_id,
        WorkOrder.tenant_id == tenant_id,
        WorkOrder.deleted_at.is_(None),
    ]
    if wo_status:
        from app.models.work_order import WorkOrderStatus
        filters.append(WorkOrder.status == WorkOrderStatus(wo_status))

    combined = and_(*filters)

    total = (
        await db.execute(select(func.count()).select_from(WorkOrder).where(combined))
    ).scalar_one()

    offset = (page - 1) * page_size
    rows = (
        await db.execute(
            select(WorkOrder)
            .where(combined)
            .order_by(WorkOrder.scheduled_date.desc().nullslast(), WorkOrder.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
    ).scalars().all()

    items: list[dict[str, Any]] = [
        {
            "id": str(wo.id),
            "title": wo.title,
            "client_id": str(wo.client_id),
            "status": wo.status.value,
            "priority": wo.priority.value,
            "location_id": str(wo.location_id),
            "crew_id": str(wo.crew_id) if wo.crew_id else None,
            "scheduled_date": wo.scheduled_date.isoformat() if wo.scheduled_date else None,
            "estimated_hours": (
                float(wo.estimated_hours) if wo.estimated_hours is not None else None
            ),
            "actual_hours": float(wo.actual_hours) if wo.actual_hours is not None else None,
            "created_at": wo.created_at.isoformat(),
            "tasks": [],
            "check_ins": [],
        }
        for wo in rows
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if page_size > 0 else 0,
    }
