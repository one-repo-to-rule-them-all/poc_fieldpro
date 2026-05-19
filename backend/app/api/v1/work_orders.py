"""Work Orders API router — full CRUD + check-in/out + attachments."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
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
    require_role,
)
from app.models.client import Client
from app.models.crew import Crew
from app.models.location import Location
from app.models.work_order import (
    AttachmentType,
    Priority,
    WorkOrder,
    WorkOrderAttachment,
    WorkOrderCheckIn,
    WorkOrderStatus,
    WorkOrderTask,
)
from app.schemas.common import PaginatedResponse
from app.schemas.work_order import (
    AttachmentPresignResponse,
    AttachmentResponse,
    CheckInRequest,
    CheckInResponse,
    CheckOutRequest,
    WorkOrderCreate,
    WorkOrderListItem,
    WorkOrderResponse,
    WorkOrderTaskCreate,
    WorkOrderTaskResponse,
    WorkOrderTaskUpdate,
    WorkOrderUpdate,
)
from app.services.work_order_service import WorkOrderService

logger = structlog.get_logger(__name__)
router = APIRouter()


async def _resolve_related_names(
    db: AsyncSession, wo: WorkOrder
) -> tuple[str | None, str | None, str | None]:
    """Fetch client_name, location_name, and crew_name for a single work order."""
    client_name: str | None = None
    if wo.client_id:
        client_name = (
            await db.execute(select(Client.name).where(Client.id == wo.client_id))
        ).scalar_one_or_none()

    location_name: str | None = None
    if wo.location_id:
        location_name = (
            await db.execute(select(Location.name).where(Location.id == wo.location_id))
        ).scalar_one_or_none()

    crew_name: str | None = None
    if wo.crew_id:
        crew_name = (
            await db.execute(select(Crew.name).where(Crew.id == wo.crew_id))
        ).scalar_one_or_none()

    return client_name, location_name, crew_name


# --------------------------------------------------------------------------- #
# GET / — list with filters
# --------------------------------------------------------------------------- #

@router.get("/", response_model=PaginatedResponse[WorkOrderListItem])
async def list_work_orders(
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    # Filters
    status: Annotated[WorkOrderStatus | None, Query()] = None,
    priority: Annotated[Priority | None, Query()] = None,
    client_id: Annotated[uuid.UUID | None, Query()] = None,
    location_id: Annotated[uuid.UUID | None, Query()] = None,
    crew_id: Annotated[uuid.UUID | None, Query()] = None,
    assigned_to: Annotated[uuid.UUID | None, Query()] = None,
    scheduled_date_from: Annotated[str | None, Query()] = None,
    scheduled_date_to: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    # Pagination
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """Return a paginated, filtered list of work orders for the current tenant."""
    filters = [
        WorkOrder.tenant_id == tenant_id,
        WorkOrder.deleted_at.is_(None),
    ]

    if status:
        filters.append(WorkOrder.status == status)
    if priority:
        filters.append(WorkOrder.priority == priority)
    if client_id:
        filters.append(WorkOrder.client_id == client_id)
    if location_id:
        filters.append(WorkOrder.location_id == location_id)
    if crew_id:
        filters.append(WorkOrder.crew_id == crew_id)
    if assigned_to:
        filters.append(WorkOrder.assigned_to == assigned_to)
    if search:
        filters.append(WorkOrder.title.ilike(f"%{search}%"))

    if scheduled_date_from:
        from datetime import datetime
        filters.append(
            WorkOrder.scheduled_date
            >= datetime.fromisoformat(scheduled_date_from).replace(tzinfo=UTC)
        )
    if scheduled_date_to:
        from datetime import datetime
        filters.append(
            WorkOrder.scheduled_date
            <= datetime.fromisoformat(scheduled_date_to + "T23:59:59").replace(tzinfo=UTC)
        )

    # Total count
    count_result = await db.execute(
        select(func.count()).select_from(WorkOrder).where(and_(*filters))
    )
    total = count_result.scalar_one()

    # Paginated rows
    offset = (page - 1) * page_size
    result = await db.execute(
        select(WorkOrder)
        .where(and_(*filters))
        .order_by(WorkOrder.scheduled_date.desc().nullslast(), WorkOrder.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = result.scalars().all()

    # Batch-fetch client and location names to avoid N+1
    client_ids = {wo.client_id for wo in items if wo.client_id}
    client_names: dict[uuid.UUID, str] = {}
    if client_ids:
        cn_result = await db.execute(
            select(Client.id, Client.name).where(Client.id.in_(client_ids))
        )
        client_names = {row.id: row.name for row in cn_result}

    location_ids = {wo.location_id for wo in items if wo.location_id}
    location_names: dict[uuid.UUID, str] = {}
    if location_ids:
        loc_result = await db.execute(
            select(Location.id, Location.name).where(Location.id.in_(location_ids))
        )
        location_names = {row.id: row.name for row in loc_result}

    crew_ids = {wo.crew_id for wo in items if wo.crew_id}
    crew_names: dict[uuid.UUID, str] = {}
    if crew_ids:
        crew_result = await db.execute(
            select(Crew.id, Crew.name).where(Crew.id.in_(crew_ids))
        )
        crew_names = {row.id: row.name for row in crew_result}

    list_items = []
    for wo in items:
        item = WorkOrderListItem.model_validate(wo)
        item.client_name = client_names.get(wo.client_id)
        item.location_name = location_names.get(wo.location_id)
        if wo.crew_id:
            item.crew_name = crew_names.get(wo.crew_id)
        list_items.append(item)

    return PaginatedResponse.create(
        items=list_items,
        total=total,
        page=page,
        page_size=page_size,
    )


# --------------------------------------------------------------------------- #
# POST / — create
# --------------------------------------------------------------------------- #

@router.post(
    "/",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("work_orders", "write"))],
)
async def create_work_order(
    payload: WorkOrderCreate,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Create a new work order. Managers and above only."""
    service = WorkOrderService(db)
    work_order = await service.create_work_order(
        tenant_id=tenant_id,
        data=payload,
        created_by=current_user,
    )
    # Re-fetch with eager loading so all server-generated columns are current.
    result = await db.execute(
        select(WorkOrder)
        .options(
            selectinload(WorkOrder.tasks),
            selectinload(WorkOrder.attachments),
            selectinload(WorkOrder.check_ins),
        )
        .where(WorkOrder.id == work_order.id)
    )
    wo = result.scalar_one()
    client_name, location_name, crew_name = await _resolve_related_names(db, wo)
    return WorkOrderResponse.from_orm_with_counts(
        wo,
        client_name=client_name,
        location_name=location_name,
        crew_name=crew_name,
    )


# --------------------------------------------------------------------------- #
# GET /{id} — get single with all related data
# --------------------------------------------------------------------------- #

@router.get("/{work_order_id}", response_model=WorkOrderResponse)
async def get_work_order(
    work_order_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Fetch a work order with tasks, check-ins, and attachments."""
    result = await db.execute(
        select(WorkOrder)
        .where(
            WorkOrder.id == work_order_id,
            WorkOrder.tenant_id == tenant_id,
            WorkOrder.deleted_at.is_(None),
        )
        .options(
            selectinload(WorkOrder.tasks),
            selectinload(WorkOrder.attachments),
            selectinload(WorkOrder.check_ins),
        )
    )
    wo = result.scalar_one_or_none()
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")

    client_name, location_name, crew_name = await _resolve_related_names(db, wo)
    return WorkOrderResponse.from_orm_with_counts(
        wo,
        client_name=client_name,
        location_name=location_name,
        crew_name=crew_name,
    )


# --------------------------------------------------------------------------- #
# PATCH /{id} — partial update
# --------------------------------------------------------------------------- #

@router.patch(
    "/{work_order_id}",
    response_model=WorkOrderResponse,
    dependencies=[Depends(require_permission("work_orders", "write"))],
)
async def update_work_order(
    work_order_id: uuid.UUID,
    payload: WorkOrderUpdate,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Partially update a work order."""
    result = await db.execute(
        select(WorkOrder).where(
            WorkOrder.id == work_order_id,
            WorkOrder.tenant_id == tenant_id,
            WorkOrder.deleted_at.is_(None),
        )
    )
    wo = result.scalar_one_or_none()
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")

    update_data = payload.model_dump(exclude_unset=True)

    # Status transitions go through the service
    if "status" in update_data:
        service = WorkOrderService(db)
        await service.update_work_order_status(
            wo_id=work_order_id,
            new_status=update_data.pop("status"),
            user=current_user,
            tenant_id=tenant_id,
        )

    for field, value in update_data.items():
        setattr(wo, field, value)

    await db.flush()

    # Re-fetch with eager loading so Pydantic can access all attributes
    # synchronously (db.refresh only reloads listed attrs, leaving other
    # server-generated columns like updated_at expired → MissingGreenlet).
    result2 = await db.execute(
        select(WorkOrder)
        .options(
            selectinload(WorkOrder.tasks),
            selectinload(WorkOrder.attachments),
            selectinload(WorkOrder.check_ins),
        )
        .where(WorkOrder.id == work_order_id)
    )
    wo = result2.scalar_one()
    client_name, location_name, crew_name = await _resolve_related_names(db, wo)
    return WorkOrderResponse.from_orm_with_counts(
        wo,
        client_name=client_name,
        location_name=location_name,
        crew_name=crew_name,
    )


# --------------------------------------------------------------------------- #
# DELETE /{id} — soft delete
# --------------------------------------------------------------------------- #

@router.delete(
    "/{work_order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("work_orders", "delete"))],
)
async def delete_work_order(
    work_order_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a work order (manager+ only)."""
    from datetime import datetime

    result = await db.execute(
        select(WorkOrder).where(
            WorkOrder.id == work_order_id,
            WorkOrder.tenant_id == tenant_id,
            WorkOrder.deleted_at.is_(None),
        )
    )
    wo = result.scalar_one_or_none()
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")

    if wo.status == WorkOrderStatus.in_progress:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a work order that is currently in progress",
        )

    wo.deleted_at = datetime.now(tz=UTC)
    logger.info(
        "work_order_deleted",
        work_order_id=str(work_order_id),
        deleted_by=str(current_user.id),
    )


# --------------------------------------------------------------------------- #
# POST /{id}/tasks — add task
# --------------------------------------------------------------------------- #

@router.post(
    "/{work_order_id}/tasks",
    response_model=WorkOrderTaskResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("work_orders", "write"))],
)
async def add_task(
    work_order_id: uuid.UUID,
    payload: WorkOrderTaskCreate,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Append a task to a work order."""
    result = await db.execute(
        select(WorkOrder).where(
            WorkOrder.id == work_order_id,
            WorkOrder.tenant_id == tenant_id,
            WorkOrder.deleted_at.is_(None),
        )
    )
    wo = result.scalar_one_or_none()
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")

    task = WorkOrderTask(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        work_order_id=work_order_id,
        title=payload.title,
        description=payload.description,
        is_required=payload.is_required,
        sort_order=payload.sort_order,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return WorkOrderTaskResponse.model_validate(task)


# --------------------------------------------------------------------------- #
# PATCH /{id}/tasks/{task_id} — update task status
# --------------------------------------------------------------------------- #

@router.patch(
    "/{work_order_id}/tasks/{task_id}",
    response_model=WorkOrderTaskResponse,
)
async def update_task(
    work_order_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: WorkOrderTaskUpdate,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Update a task (status, title, etc.). Employees can update their own tasks."""
    from datetime import datetime

    from app.models.work_order import TaskStatus

    result = await db.execute(
        select(WorkOrderTask).where(
            WorkOrderTask.id == task_id,
            WorkOrderTask.work_order_id == work_order_id,
            WorkOrderTask.tenant_id == tenant_id,
            WorkOrderTask.deleted_at.is_(None),
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    update_data = payload.model_dump(exclude_unset=True)
    new_status = update_data.pop("status", None)

    for field, value in update_data.items():
        setattr(task, field, value)

    if new_status is not None:
        task.status = new_status
        if new_status == TaskStatus.completed:
            task.completed_by = current_user.id
            task.completed_at = datetime.now(tz=UTC)
        elif new_status != TaskStatus.completed:
            task.completed_by = None
            task.completed_at = None

    await db.flush()
    await db.refresh(task)
    return WorkOrderTaskResponse.model_validate(task)


# --------------------------------------------------------------------------- #
# POST /{id}/checkin
# --------------------------------------------------------------------------- #

@router.post("/{work_order_id}/checkin", response_model=CheckInResponse)
async def checkin(
    work_order_id: uuid.UUID,
    payload: CheckInRequest,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """GPS or QR code check-in for a work order."""
    service = WorkOrderService(db)
    check_in_record = await service.process_checkin(
        wo_id=work_order_id,
        tenant_id=tenant_id,
        user_id=current_user.id,
        lat=payload.latitude,
        lon=payload.longitude,
        method=payload.method,
        qr_token=payload.qr_token,
    )

    message = (
        "Checked in successfully"
        if check_in_record.is_valid
        else f"Checked in outside geofence ({check_in_record.distance_from_location_meters}m away)"
    )

    return CheckInResponse(
        check_in_id=check_in_record.id,
        work_order_id=work_order_id,
        is_valid=check_in_record.is_valid,
        distance_meters=check_in_record.distance_from_location_meters,
        message=message,
        check_in_time=check_in_record.check_in_time,
    )


# --------------------------------------------------------------------------- #
# POST /{id}/checkout
# --------------------------------------------------------------------------- #

@router.post("/{work_order_id}/checkout", response_model=CheckInResponse)
async def checkout(
    work_order_id: uuid.UUID,
    payload: CheckOutRequest,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Check out from a work order, recording final GPS coordinates."""
    from datetime import datetime

    # Find the active check-in for this user / work order
    result = await db.execute(
        select(WorkOrderCheckIn).where(
            WorkOrderCheckIn.work_order_id == work_order_id,
            WorkOrderCheckIn.user_id == current_user.id,
            WorkOrderCheckIn.tenant_id == tenant_id,
            WorkOrderCheckIn.check_out_time.is_(None),
        ).order_by(WorkOrderCheckIn.check_in_time.desc())
    )
    check_in = result.scalars().first()

    if not check_in:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active check-in found for this work order",
        )

    now = datetime.now(tz=UTC)
    check_in.check_out_time = now
    check_in.check_out_latitude = Decimal(str(payload.latitude))
    check_in.check_out_longitude = Decimal(str(payload.longitude))

    await db.flush()

    return CheckInResponse(
        check_in_id=check_in.id,
        work_order_id=work_order_id,
        is_valid=check_in.is_valid,
        distance_meters=check_in.distance_from_location_meters,
        message="Checked out successfully",
        check_in_time=check_in.check_in_time,
    )


# --------------------------------------------------------------------------- #
# POST /{id}/attachments — presigned upload URL
# --------------------------------------------------------------------------- #

@router.post(
    "/{work_order_id}/attachments",
    response_model=AttachmentPresignResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_attachment_upload_url(
    work_order_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    file_name: str = Query(..., max_length=255),
    mime_type: str = Query(..., max_length=100),
    file_size: int = Query(..., ge=1, le=52428800),
    attachment_type: AttachmentType = Query(default=AttachmentType.photo),
):
    """
    Create a pending attachment record and return a presigned S3 upload URL.

    The client should PUT the file directly to the returned URL,
    then call PATCH /attachments/{id}/confirm to finalize.
    """
    import boto3

    from app.core.config import settings

    # Verify work order exists and belongs to tenant
    result = await db.execute(
        select(WorkOrder).where(
            WorkOrder.id == work_order_id,
            WorkOrder.tenant_id == tenant_id,
            WorkOrder.deleted_at.is_(None),
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")

    attachment_id = uuid.uuid4()
    s3_key = (
        f"tenants/{tenant_id}/work-orders/{work_order_id}/"
        f"attachments/{attachment_id}/{file_name}"
    )

    # Create the attachment record (pre-upload state)
    attachment = WorkOrderAttachment(
        id=attachment_id,
        tenant_id=tenant_id,
        work_order_id=work_order_id,
        uploaded_by=current_user.id,
        file_name=file_name,
        file_size=file_size,
        mime_type=mime_type,
        s3_key=s3_key,
        attachment_type=attachment_type,
    )
    db.add(attachment)
    await db.flush()

    # Generate presigned URL
    s3_client = boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.effective_aws_access_key,
        aws_secret_access_key=settings.effective_aws_secret_key,
        endpoint_url=settings.s3_endpoint_url or None,
    )

    expires_in = settings.S3_PRESIGNED_URL_EXPIRE_SECONDS
    upload_url = s3_client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.effective_s3_bucket,
            "Key": s3_key,
            "ContentType": mime_type,
        },
        ExpiresIn=expires_in,
    )

    return AttachmentPresignResponse(
        upload_url=upload_url,
        attachment_id=attachment_id,
        s3_key=s3_key,
        expires_in_seconds=expires_in,
    )


# --------------------------------------------------------------------------- #
# GET /{id}/attachments — list attachments
# --------------------------------------------------------------------------- #

@router.get("/{work_order_id}/attachments", response_model=list[AttachmentResponse])
async def list_attachments(
    work_order_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """List all attachments for a work order."""
    result = await db.execute(
        select(WorkOrderAttachment).where(
            WorkOrderAttachment.work_order_id == work_order_id,
            WorkOrderAttachment.tenant_id == tenant_id,
            WorkOrderAttachment.deleted_at.is_(None),
        ).order_by(WorkOrderAttachment.created_at.desc())
    )
    attachments = result.scalars().all()
    return [AttachmentResponse.model_validate(a) for a in attachments]


# --------------------------------------------------------------------------- #
# POST /{id}/complete
# --------------------------------------------------------------------------- #

@router.post(
    "/{work_order_id}/complete",
    response_model=WorkOrderResponse,
    dependencies=[Depends(require_permission("work_orders", "write"))],
)
async def complete_work_order(
    work_order_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    completion_notes: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a work order as completed.

    Validates that all required tasks are done before allowing completion.
    """
    service = WorkOrderService(db)
    wo = await service.complete_work_order(
        wo_id=work_order_id,
        tenant_id=tenant_id,
        user_id=current_user.id,
        completion_notes=completion_notes,
    )
    result = await db.execute(
        select(WorkOrder)
        .options(
            selectinload(WorkOrder.tasks),
            selectinload(WorkOrder.attachments),
            selectinload(WorkOrder.check_ins),
        )
        .where(WorkOrder.id == work_order_id)
    )
    wo = result.scalar_one()
    client_name, location_name, crew_name = await _resolve_related_names(db, wo)
    return WorkOrderResponse.from_orm_with_counts(
        wo,
        client_name=client_name,
        location_name=location_name,
        crew_name=crew_name,
    )


# --------------------------------------------------------------------------- #
# POST /{id}/generate-instances — manually generate recurring instances
# --------------------------------------------------------------------------- #

@router.post(
    "/{work_order_id}/generate-instances",
    response_model=list[WorkOrderListItem],
    dependencies=[Depends(require_role("manager"))],
)
async def generate_recurring_instances(
    work_order_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    until_date: datetime,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually generate all recurring instances for a work order up to until_date.

    Useful for seeding the schedule ahead of time. Requires manager role.
    Auto-generation on completion is handled automatically by complete_work_order.
    """
    service = WorkOrderService(db)
    created = await service.generate_recurring_instances(
        parent_wo_id=work_order_id,
        tenant_id=tenant_id,
        until_date=until_date,
    )
    await db.commit()
    return [WorkOrderListItem.model_validate(wo, from_attributes=True) for wo in created]
