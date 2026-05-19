"""Locations API router — full CRUD for service locations."""

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
)
from app.models.client import Client
from app.models.location import Location
from app.schemas.common import PaginatedResponse
from app.schemas.location import LocationDetailResponse, LocationListResponse

logger = structlog.get_logger(__name__)
router = APIRouter()


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #

def _paginate_meta(total: int, page: int, limit: int) -> dict:
    pages = math.ceil(total / limit) if limit > 0 else 0
    return {"total": total, "page": page, "limit": limit, "pages": pages}


def _location_to_dict(loc: Location) -> dict:
    return {
        "id": str(loc.id),
        "tenant_id": str(loc.tenant_id),
        "client_id": str(loc.client_id),
        "name": loc.name,
        "address": loc.address,
        "latitude": str(loc.latitude) if loc.latitude is not None else None,
        "longitude": str(loc.longitude) if loc.longitude is not None else None,
        "geofence_radius_meters": loc.geofence_radius_meters,
        "access_instructions": loc.access_instructions,
        "special_requirements": loc.special_requirements,
        "is_active": loc.is_active,
        "qr_code_token": loc.qr_code_token,
        "created_at": loc.created_at.isoformat(),
        "updated_at": loc.updated_at.isoformat() if loc.updated_at else None,
    }


async def _get_location_or_404(
    location_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> Location:
    result = await db.execute(
        select(Location).where(
            Location.id == location_id,
            Location.tenant_id == tenant_id,
            Location.deleted_at.is_(None),
        )
    )
    loc = result.scalar_one_or_none()
    if loc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return loc


async def _assert_client_exists(
    client_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    result = await db.execute(
        select(func.count()).select_from(Client).where(
            Client.id == client_id,
            Client.tenant_id == tenant_id,
            Client.deleted_at.is_(None),
        )
    )
    if result.scalar_one() == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client {client_id} not found",
        )


# --------------------------------------------------------------------------- #
# GET / — list locations
# --------------------------------------------------------------------------- #

@router.get("/", response_model=PaginatedResponse[LocationListResponse])
async def list_locations(
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    client_id: Annotated[uuid.UUID | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    """Return a paginated, filtered list of service locations for the tenant."""
    filters = [
        Location.tenant_id == tenant_id,
        Location.deleted_at.is_(None),
    ]
    if client_id:
        filters.append(Location.client_id == client_id)
    if is_active is not None:
        filters.append(Location.is_active == is_active)
    if search:
        filters.append(Location.name.ilike(f"%{search}%"))

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

    return {
        "items": [_location_to_dict(loc) for loc in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if page_size > 0 else 0,
    }


# --------------------------------------------------------------------------- #
# POST / — create location
# --------------------------------------------------------------------------- #

@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=LocationDetailResponse,
    dependencies=[Depends(require_permission("locations", "write"))],
)
async def create_location(
    payload: dict,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Create a new service location. Requires locations:write permission."""
    from decimal import Decimal

    client_id_val = payload.get("client_id")
    if not client_id_val:
        raise HTTPException(status_code=422, detail="client_id is required")
    client_id = uuid.UUID(str(client_id_val))

    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")

    await _assert_client_exists(client_id, tenant_id, db)

    # Optional QR token — must be unique if supplied
    qr_token = payload.get("qr_code_token")
    if qr_token:
        existing = (
            await db.execute(
                select(func.count()).select_from(Location).where(
                    Location.qr_code_token == qr_token
                )
            )
        ).scalar_one()
        if existing > 0:
            raise HTTPException(status_code=409, detail="qr_code_token already in use")

    lat = payload.get("latitude")
    lon = payload.get("longitude")

    location = Location(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        client_id=client_id,
        name=name,
        address=payload.get("address") or {},
        latitude=Decimal(str(lat)) if lat is not None else None,
        longitude=Decimal(str(lon)) if lon is not None else None,
        geofence_radius_meters=int(payload.get("geofence_radius_meters") or 200),
        access_instructions=payload.get("access_instructions"),
        special_requirements=payload.get("special_requirements"),
        is_active=payload.get("is_active", True),
        qr_code_token=qr_token,
    )
    db.add(location)
    await db.flush()
    await db.refresh(location)

    logger.info(
        "location_created",
        tenant_id=str(tenant_id),
        location_id=str(location.id),
        client_id=str(client_id),
        created_by=str(current_user.id),
    )

    return _location_to_dict(location)


# --------------------------------------------------------------------------- #
# GET /{id} — get single location
# --------------------------------------------------------------------------- #

@router.get("/{location_id}", response_model=LocationDetailResponse)
async def get_location(
    location_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Fetch a single service location."""
    loc = await _get_location_or_404(location_id, tenant_id, db)
    return _location_to_dict(loc)


# --------------------------------------------------------------------------- #
# PATCH /{id} — update location
# --------------------------------------------------------------------------- #

@router.patch(
    "/{location_id}",
    response_model=LocationDetailResponse,
    dependencies=[Depends(require_permission("locations", "write"))],
)
async def update_location(
    location_id: uuid.UUID,
    payload: dict,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Partially update a service location. Requires locations:write permission."""
    from decimal import Decimal

    loc = await _get_location_or_404(location_id, tenant_id, db)

    plain_fields = {
        "name", "address", "geofence_radius_meters",
        "access_instructions", "special_requirements", "is_active",
    }
    for field in plain_fields:
        if field in payload:
            setattr(loc, field, payload[field])

    if "latitude" in payload:
        v = payload["latitude"]
        loc.latitude = Decimal(str(v)) if v is not None else None
    if "longitude" in payload:
        v = payload["longitude"]
        loc.longitude = Decimal(str(v)) if v is not None else None

    if "qr_code_token" in payload:
        new_token = payload["qr_code_token"]
        if new_token and new_token != loc.qr_code_token:
            existing = (
                await db.execute(
                    select(func.count()).select_from(Location).where(
                        Location.qr_code_token == new_token,
                        Location.id != location_id,
                    )
                )
            ).scalar_one()
            if existing > 0:
                raise HTTPException(status_code=409, detail="qr_code_token already in use")
        loc.qr_code_token = new_token

    if "client_id" in payload:
        new_client_id = uuid.UUID(str(payload["client_id"]))
        await _assert_client_exists(new_client_id, tenant_id, db)
        loc.client_id = new_client_id

    await db.flush()
    await db.refresh(loc)

    logger.info(
        "location_updated",
        tenant_id=str(tenant_id),
        location_id=str(location_id),
        updated_by=str(current_user.id),
        fields=list(payload.keys()),
    )

    return _location_to_dict(loc)


# --------------------------------------------------------------------------- #
# DELETE /{id} — soft delete
# --------------------------------------------------------------------------- #

@router.delete(
    "/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("locations", "delete"))],
)
async def delete_location(
    location_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a service location. Requires locations:delete permission."""
    from datetime import datetime

    from app.models.work_order import WorkOrder

    loc = await _get_location_or_404(location_id, tenant_id, db)

    # Guard: open work orders reference this location
    open_count = (
        await db.execute(
            select(func.count()).select_from(WorkOrder).where(
                WorkOrder.location_id == location_id,
                WorkOrder.tenant_id == tenant_id,
                WorkOrder.deleted_at.is_(None),
                WorkOrder.status.in_(["draft", "scheduled", "in_progress", "on_hold"]),
            )
        )
    ).scalar_one()
    if open_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a location with open work orders",
        )

    loc.deleted_at = datetime.now(tz=UTC)
    loc.is_active = False
    await db.flush()

    logger.info(
        "location_deleted",
        tenant_id=str(tenant_id),
        location_id=str(location_id),
        deleted_by=str(current_user.id),
    )
