"""WorkOrder Pydantic v2 schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import uuid

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.work_order import (
    AttachmentType,
    CheckInMethod,
    Priority,
    TaskStatus,
    WorkOrderStatus,
    WorkType,
)

# --------------------------------------------------------------------------- #
# WorkOrderTask schemas
# --------------------------------------------------------------------------- #

class WorkOrderTaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: str | None = None
    is_required: bool = True
    sort_order: int = 0


class WorkOrderTaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    is_required: bool | None = None
    status: TaskStatus | None = None
    sort_order: int | None = None


class WorkOrderTaskResponse(BaseModel):
    id: uuid.UUID
    work_order_id: uuid.UUID
    title: str
    description: str | None = None
    is_required: bool
    status: TaskStatus
    completed_by: uuid.UUID | None = None
    completed_at: datetime | None = None
    sort_order: int

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# WorkOrder schemas
# --------------------------------------------------------------------------- #

class WorkOrderCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: str | None = None
    client_id: uuid.UUID
    location_id: uuid.UUID
    crew_id: uuid.UUID | None = None
    assigned_to: uuid.UUID | None = None
    priority: Priority = Priority.normal
    work_type: WorkType = WorkType.one_time
    scheduled_date: datetime | None = None
    scheduled_start_time: datetime | None = None
    scheduled_end_time: datetime | None = None
    estimated_hours: Decimal | None = Field(default=None, ge=0, le=999)
    sla_deadline: datetime | None = None
    recurrence_rule: str | None = Field(default=None, max_length=500)
    notes: str | None = None
    internal_notes: str | None = None
    tasks: list[WorkOrderTaskCreate] = Field(default_factory=list)

    @field_validator("recurrence_rule")
    @classmethod
    def validate_rrule(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith("FREQ="):
            raise ValueError("recurrence_rule must be a valid iCal RRULE starting with FREQ=")
        return v

    @model_validator(mode="after")
    def validate_time_window(self) -> WorkOrderCreate:
        if (
            self.scheduled_start_time
            and self.scheduled_end_time
            and self.scheduled_start_time >= self.scheduled_end_time
        ):
            raise ValueError("scheduled_start_time must be before scheduled_end_time")
        return self


class WorkOrderUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    crew_id: uuid.UUID | None = None
    assigned_to: uuid.UUID | None = None
    status: WorkOrderStatus | None = None
    priority: Priority | None = None
    scheduled_date: datetime | None = None
    scheduled_start_time: datetime | None = None
    scheduled_end_time: datetime | None = None
    estimated_hours: Decimal | None = Field(default=None, ge=0, le=999)
    sla_deadline: datetime | None = None
    recurrence_rule: str | None = None
    notes: str | None = None
    internal_notes: str | None = None
    completion_notes: str | None = None


class WorkOrderListItem(BaseModel):
    """Lightweight schema for list views — omits large fields."""

    id: uuid.UUID
    title: str
    status: WorkOrderStatus
    priority: Priority
    work_type: WorkType
    client_id: uuid.UUID
    client_name: str | None = None
    location_id: uuid.UUID
    location_name: str | None = None
    crew_id: uuid.UUID | None = None
    crew_name: str | None = None
    assigned_to: uuid.UUID | None = None
    scheduled_date: datetime | None = None
    sla_deadline: datetime | None = None
    sla_met: bool | None = None
    is_overdue: bool = False
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class WorkOrderResponse(BaseModel):
    """Full work order response including tasks, check-ins counts, etc."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    title: str
    description: str | None = None
    client_id: uuid.UUID
    client_name: str | None = None
    location_id: uuid.UUID
    location_name: str | None = None
    crew_id: uuid.UUID | None = None
    crew_name: str | None = None
    assigned_to: uuid.UUID | None = None
    status: WorkOrderStatus
    priority: Priority
    work_type: WorkType
    scheduled_date: datetime | None = None
    scheduled_start_time: datetime | None = None
    scheduled_end_time: datetime | None = None
    actual_start_time: datetime | None = None
    actual_end_time: datetime | None = None
    estimated_hours: Decimal | None = None
    actual_hours: Decimal | None = None
    sla_deadline: datetime | None = None
    sla_met: bool | None = None
    recurrence_rule: str | None = None
    parent_work_order_id: uuid.UUID | None = None
    notes: str | None = None
    internal_notes: str | None = None
    completion_notes: str | None = None
    is_overdue: bool = False
    tasks: list[WorkOrderTaskResponse] = Field(default_factory=list)
    check_ins: list[CheckInListItem] = Field(default_factory=list)
    task_count: int = 0
    completed_task_count: int = 0
    attachment_count: int = 0
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_counts(
        cls,
        wo,
        client_name: str | None = None,
        location_name: str | None = None,
        crew_name: str | None = None,
    ) -> WorkOrderResponse:
        """Build response, computing task counts from loaded relationships."""
        task_count = len(wo.tasks) if wo.tasks else 0
        completed_task_count = sum(
            1 for t in (wo.tasks or []) if t.status == TaskStatus.completed
        )
        attachment_count = len(wo.attachments) if wo.attachments else 0
        data = cls.model_validate(wo)
        data.task_count = task_count
        data.completed_task_count = completed_task_count
        data.attachment_count = attachment_count
        data.client_name = client_name
        data.location_name = location_name
        data.crew_name = crew_name
        return data


# --------------------------------------------------------------------------- #
# Check-in list item (for embedding in work order detail responses)
# --------------------------------------------------------------------------- #

class CheckInListItem(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    check_in_time: datetime
    check_out_time: datetime | None = None
    is_valid: bool
    distance_from_location_meters: int | None = None

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# Check-in / check-out schemas
# --------------------------------------------------------------------------- #

class CheckInRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    method: CheckInMethod = CheckInMethod.gps
    qr_token: str | None = None

    @model_validator(mode="after")
    def qr_token_required_for_qr_method(self) -> CheckInRequest:
        if self.method == CheckInMethod.qr_code and not self.qr_token:
            raise ValueError("qr_token is required when method is qr_code")
        return self


class CheckOutRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    notes: str | None = None


class CheckInResponse(BaseModel):
    check_in_id: uuid.UUID
    work_order_id: uuid.UUID
    is_valid: bool
    distance_meters: int | None = None
    message: str
    check_in_time: datetime


# --------------------------------------------------------------------------- #
# Attachment upload
# --------------------------------------------------------------------------- #

class AttachmentPresignResponse(BaseModel):
    upload_url: str
    attachment_id: uuid.UUID
    s3_key: str
    expires_in_seconds: int = 900


class AttachmentResponse(BaseModel):
    id: uuid.UUID
    work_order_id: uuid.UUID
    task_id: uuid.UUID | None = None
    file_name: str
    file_size: int
    mime_type: str
    attachment_type: AttachmentType
    caption: str | None = None
    is_issue: bool
    thumbnail_url: str | None = None
    download_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
