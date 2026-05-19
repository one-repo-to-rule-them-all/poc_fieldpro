"""WorkOrder, WorkOrderTask, WorkOrderAttachment, and WorkOrderCheckIn models."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import enum
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TenantAwareModel

# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #

class WorkOrderStatus(str, enum.Enum):
    draft = "draft"
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"
    on_hold = "on_hold"


class Priority(str, enum.Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class WorkType(str, enum.Enum):
    recurring = "recurring"
    one_time = "one_time"
    emergency = "emergency"


class TaskStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    skipped = "skipped"
    blocked = "blocked"


class AttachmentType(str, enum.Enum):
    photo = "photo"
    document = "document"
    signature = "signature"


class CheckInMethod(str, enum.Enum):
    gps = "gps"
    qr_code = "qr_code"
    manual = "manual"


# --------------------------------------------------------------------------- #
# WorkOrder
# --------------------------------------------------------------------------- #

class WorkOrder(Base, TenantAwareModel):
    __tablename__ = "work_orders"

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    crew_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crews.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status: Mapped[WorkOrderStatus] = mapped_column(
        Enum(WorkOrderStatus, name="work_order_status"),
        nullable=False,
        default=WorkOrderStatus.draft,
        index=True,
    )
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, name="priority"),
        nullable=False,
        default=Priority.normal,
    )
    work_type: Mapped[WorkType] = mapped_column(
        Enum(WorkType, name="work_type"),
        nullable=False,
        default=WorkType.one_time,
    )

    # Scheduling
    scheduled_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    scheduled_start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scheduled_end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    estimated_hours: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2), nullable=True
    )
    actual_hours: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2), nullable=True
    )

    # SLA
    sla_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sla_met: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Recurrence
    recurrence_rule: Mapped[str | None] = mapped_column(
        String(500), nullable=True  # iCal RRULE string e.g. "FREQ=WEEKLY;BYDAY=MO,WE,FR"
    )
    parent_work_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completion_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    client: Mapped[Client] = relationship("Client")  # type: ignore[name-defined]
    location: Mapped[Location] = relationship("Location")  # type: ignore[name-defined]
    crew: Mapped[Crew | None] = relationship("Crew")  # type: ignore[name-defined]
    assignee: Mapped[User | None] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[assigned_to]
    )
    tasks: Mapped[list[WorkOrderTask]] = relationship(
        "WorkOrderTask",
        back_populates="work_order",
        cascade="all, delete-orphan",
        order_by="WorkOrderTask.sort_order",
    )
    attachments: Mapped[list[WorkOrderAttachment]] = relationship(
        "WorkOrderAttachment",
        back_populates="work_order",
        cascade="all, delete-orphan",
    )
    check_ins: Mapped[list[WorkOrderCheckIn]] = relationship(
        "WorkOrderCheckIn",
        back_populates="work_order",
        cascade="all, delete-orphan",
    )
    child_work_orders: Mapped[list[WorkOrder]] = relationship(
        "WorkOrder",
        foreign_keys=[parent_work_order_id],
        back_populates="parent_work_order",
    )
    parent_work_order: Mapped[WorkOrder | None] = relationship(
        "WorkOrder",
        foreign_keys=[parent_work_order_id],
        back_populates="child_work_orders",
        remote_side="WorkOrder.id",
    )

    @property
    def is_overdue(self) -> bool:
        if self.sla_deadline and self.status not in (
            WorkOrderStatus.completed, WorkOrderStatus.cancelled
        ):
            deadline = self.sla_deadline
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=UTC)
            return datetime.now(tz=UTC) > deadline
        return False

    def __repr__(self) -> str:
        return f"<WorkOrder {self.title[:30]} status={self.status}>"


# --------------------------------------------------------------------------- #
# WorkOrderTask
# --------------------------------------------------------------------------- #

class WorkOrderTask(Base, TenantAwareModel):
    __tablename__ = "work_order_tasks"

    work_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status"),
        nullable=False,
        default=TaskStatus.pending,
    )
    completed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    work_order: Mapped[WorkOrder] = relationship("WorkOrder", back_populates="tasks")
    completed_by_user: Mapped[User | None] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[completed_by]
    )

    def __repr__(self) -> str:
        return f"<WorkOrderTask {self.title[:40]} status={self.status}>"


# --------------------------------------------------------------------------- #
# WorkOrderAttachment
# --------------------------------------------------------------------------- #

class WorkOrderAttachment(Base, TenantAwareModel):
    __tablename__ = "work_order_attachments"

    work_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_order_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)

    attachment_type: Mapped[AttachmentType] = mapped_column(
        Enum(AttachmentType, name="attachment_type"),
        nullable=False,
        default=AttachmentType.photo,
    )
    caption: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_issue: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    work_order: Mapped[WorkOrder] = relationship(
        "WorkOrder", back_populates="attachments"
    )
    uploader: Mapped[User] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[uploaded_by]
    )

    def __repr__(self) -> str:
        return f"<WorkOrderAttachment {self.file_name} type={self.attachment_type}>"


# --------------------------------------------------------------------------- #
# WorkOrderCheckIn
# --------------------------------------------------------------------------- #

class WorkOrderCheckIn(Base, TenantAwareModel):
    __tablename__ = "work_order_check_ins"

    work_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    check_in_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    check_out_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    check_in_latitude: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 8), nullable=True
    )
    check_in_longitude: Mapped[Decimal | None] = mapped_column(
        Numeric(11, 8), nullable=True
    )
    check_out_latitude: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 8), nullable=True
    )
    check_out_longitude: Mapped[Decimal | None] = mapped_column(
        Numeric(11, 8), nullable=True
    )

    check_in_method: Mapped[CheckInMethod] = mapped_column(
        Enum(CheckInMethod, name="check_in_method"),
        nullable=False,
        default=CheckInMethod.gps,
    )
    distance_from_location_meters: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    work_order: Mapped[WorkOrder] = relationship(
        "WorkOrder", back_populates="check_ins"
    )
    user: Mapped[User] = relationship("User")  # type: ignore[name-defined]

    @property
    def duration_minutes(self) -> int | None:
        """Return minutes between check-in and check-out, or None if not checked out."""
        if self.check_out_time and self.check_in_time:
            delta = self.check_out_time - self.check_in_time
            return int(delta.total_seconds() / 60)
        return None

    def __repr__(self) -> str:
        return (
            f"<WorkOrderCheckIn wo={self.work_order_id} "
            f"user={self.user_id} valid={self.is_valid}>"
        )
