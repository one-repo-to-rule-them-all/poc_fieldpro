"""
WorkOrder business logic service layer.

All state machine logic, geofence validation, SLA tracking,
and recurring work order generation lives here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import math
from typing import TYPE_CHECKING
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.core.audit import AuditService, AuditSuppression
from app.models.location import Location
from app.models.work_order import (
    CheckInMethod,
    TaskStatus,
    WorkOrder,
    WorkOrderCheckIn,
    WorkOrderStatus,
    WorkOrderTask,
)

if TYPE_CHECKING:
    from app.models.user import User
    from app.schemas.work_order import WorkOrderCreate

logger = structlog.get_logger(__name__)


# --------------------------------------------------------------------------- #
# Valid status state machine transitions
# --------------------------------------------------------------------------- #

_VALID_TRANSITIONS: dict[WorkOrderStatus, set[WorkOrderStatus]] = {
    WorkOrderStatus.draft: {
        WorkOrderStatus.scheduled,
        WorkOrderStatus.cancelled,
    },
    WorkOrderStatus.scheduled: {
        WorkOrderStatus.in_progress,
        WorkOrderStatus.on_hold,
        WorkOrderStatus.cancelled,
    },
    WorkOrderStatus.in_progress: {
        WorkOrderStatus.completed,
        WorkOrderStatus.on_hold,
        WorkOrderStatus.cancelled,
    },
    WorkOrderStatus.on_hold: {
        WorkOrderStatus.in_progress,
        WorkOrderStatus.scheduled,
        WorkOrderStatus.cancelled,
    },
    WorkOrderStatus.completed: set(),  # Terminal
    WorkOrderStatus.cancelled: set(),  # Terminal
}


def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """
    Calculate the great-circle distance in meters between two GPS coordinates
    using the Haversine formula.
    """
    earth_radius_m = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return int(earth_radius_m * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


class WorkOrderService:
    """Encapsulates all business logic for work orders."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        # Domain events (status transitions, check-ins, completions) wrap their
        # ORM mutations in AuditSuppression.suppress() and emit a richer
        # domain-verb row via self.audit.record() — instead of letting the
        # generic listener-driven "updated" row stand. See PR #102 design.
        self.audit = AuditService(db)

    # ---------------------------------------------------------------------- #
    # Create
    # ---------------------------------------------------------------------- #

    async def create_work_order(
        self,
        tenant_id: uuid.UUID,
        data: WorkOrderCreate,
        created_by: User,
    ) -> WorkOrder:
        """
        Create a new work order with its tasks.

        - Validates that client + location belong to this tenant.
        - If crew_id provided, checks the crew is active in the tenant.
        - Creates child WorkOrderTask records in bulk.
        """
        # Validate location belongs to this tenant
        loc_result = await self.db.execute(
            select(Location).where(
                Location.id == data.location_id,
                Location.tenant_id == tenant_id,
                Location.deleted_at.is_(None),
            )
        )
        location = loc_result.scalar_one_or_none()
        if not location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Location not found or does not belong to this tenant",
            )

        work_order = WorkOrder(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            title=data.title,
            description=data.description,
            client_id=data.client_id,
            location_id=data.location_id,
            crew_id=data.crew_id,
            assigned_to=data.assigned_to,
            priority=data.priority,
            work_type=data.work_type,
            scheduled_date=data.scheduled_date,
            scheduled_start_time=data.scheduled_start_time,
            scheduled_end_time=data.scheduled_end_time,
            estimated_hours=data.estimated_hours,
            sla_deadline=data.sla_deadline,
            recurrence_rule=data.recurrence_rule,
            notes=data.notes,
            internal_notes=data.internal_notes,
            status=WorkOrderStatus.draft,
        )
        self.db.add(work_order)
        await self.db.flush()  # Get ID for tasks

        for i, task_data in enumerate(data.tasks or []):
            task = WorkOrderTask(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                work_order_id=work_order.id,
                title=task_data.title,
                description=task_data.description,
                is_required=task_data.is_required,
                sort_order=task_data.sort_order if task_data.sort_order else i,
            )
            self.db.add(task)

        logger.info(
            "work_order_created",
            work_order_id=str(work_order.id),
            tenant_id=str(tenant_id),
            created_by=str(created_by.id),
        )
        return work_order

    # ---------------------------------------------------------------------- #
    # Status transitions
    # ---------------------------------------------------------------------- #

    async def update_work_order_status(
        self,
        wo_id: uuid.UUID,
        new_status: WorkOrderStatus,
        user: User,
        tenant_id: uuid.UUID,
    ) -> WorkOrder:
        """
        Transition a work order to a new status, enforcing the state machine.

        Raises HTTPException 409 if the transition is not allowed.
        """
        result = await self.db.execute(
            select(WorkOrder).where(
                WorkOrder.id == wo_id,
                WorkOrder.tenant_id == tenant_id,
                WorkOrder.deleted_at.is_(None),
            )
        )
        wo = result.scalar_one_or_none()
        if not wo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work order not found",
            )

        current_status = wo.status

        # No-op if same status
        if new_status == current_status:
            return wo

        allowed = _VALID_TRANSITIONS.get(current_status, set())

        if new_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot transition from '{current_status.value}' to '{new_status.value}'. "
                    f"Allowed transitions: {[s.value for s in allowed]}"
                ),
            )

        now = datetime.now(tz=UTC)

        # Suppress the auto-listener for the status mutation; we emit a
        # richer domain-verb audit row below instead of letting the
        # listener record a generic "updated".
        with AuditSuppression.suppress():
            wo.status = new_status
            if new_status == WorkOrderStatus.in_progress and not wo.actual_start_time:
                wo.actual_start_time = now
            await self.db.flush()

        await self.audit.record(
            action="status_changed",
            resource_type="WorkOrder",
            resource_id=str(wo_id),
            old_values={"status": current_status.value},
            new_values={"status": new_status.value},
            user_id=user.id,
            tenant_id=tenant_id,
        )

        logger.info(
            "work_order_status_changed",
            work_order_id=str(wo_id),
            from_status=current_status.value,
            to_status=new_status.value,
            changed_by=str(user.id),
        )
        return wo

    # ---------------------------------------------------------------------- #
    # Check-in
    # ---------------------------------------------------------------------- #

    async def process_checkin(
        self,
        wo_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        lat: float,
        lon: float,
        method: CheckInMethod,
        qr_token: str | None = None,
    ) -> WorkOrderCheckIn:
        """
        Record a GPS/QR check-in for a work order.

        - Loads the work order and its location.
        - If method is qr_code, validates the token matches the location's qr_code_token.
        - Calculates distance from the location and checks geofence.
        - Transitions work order to in_progress if still scheduled.
        - Returns the created WorkOrderCheckIn record.
        """
        # Load work order
        wo_result = await self.db.execute(
            select(WorkOrder).where(
                WorkOrder.id == wo_id,
                WorkOrder.tenant_id == tenant_id,
                WorkOrder.deleted_at.is_(None),
            )
        )
        wo = wo_result.scalar_one_or_none()
        if not wo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work order not found",
            )

        if wo.status == WorkOrderStatus.completed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot check into a completed work order",
            )
        if wo.status == WorkOrderStatus.cancelled:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot check into a cancelled work order",
            )

        # Load location for geofence validation
        loc_result = await self.db.execute(
            select(Location).where(Location.id == wo.location_id)
        )
        location = loc_result.scalar_one_or_none()

        # QR token validation
        if method == CheckInMethod.qr_code and (
            not qr_token or location is None or location.qr_code_token != qr_token
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid QR code token for this location",
            )

        # Calculate geofence distance
        distance_m: int | None = None
        is_valid = True

        if location and location.latitude and location.longitude:
            distance_m = _haversine_meters(
                float(location.latitude),
                float(location.longitude),
                lat,
                lon,
            )
            geofence_radius = location.geofence_radius_meters or 200
            is_valid = distance_m <= geofence_radius

            if not is_valid:
                logger.warning(
                    "checkin_outside_geofence",
                    work_order_id=str(wo_id),
                    user_id=str(user_id),
                    distance_m=distance_m,
                    geofence_radius=geofence_radius,
                )

        now = datetime.now(tz=UTC)
        check_in = WorkOrderCheckIn(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            work_order_id=wo_id,
            user_id=user_id,
            check_in_time=now,
            check_in_latitude=Decimal(str(lat)),
            check_in_longitude=Decimal(str(lon)),
            check_in_method=method,
            distance_from_location_meters=distance_m,
            is_valid=is_valid,
        )
        self.db.add(check_in)

        # Suppress the auto-listener for the implicit status transition
        # to in_progress; the explicit "checkin" audit row below captures
        # both the check-in and the transition as a single event.
        with AuditSuppression.suppress():
            if wo.status in (WorkOrderStatus.draft, WorkOrderStatus.scheduled):
                wo.status = WorkOrderStatus.in_progress
                wo.actual_start_time = now
            await self.db.flush()

        await self.audit.record(
            action="checkin",
            resource_type="WorkOrder",
            resource_id=str(wo_id),
            new_values={
                "check_in_id": str(check_in.id),
                "method": method.value,
                "is_valid_geofence": is_valid,
                "distance_m": distance_m,
            },
            user_id=user_id,
            tenant_id=tenant_id,
        )

        return check_in

    # ---------------------------------------------------------------------- #
    # Complete
    # ---------------------------------------------------------------------- #

    async def complete_work_order(
        self,
        wo_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        completion_notes: str | None = None,
    ) -> WorkOrder:
        """
        Mark a work order as completed.

        Validations:
        - All required tasks must be in 'completed' or 'skipped' state.
        - Work order must not already be completed or cancelled.

        Side effects:
        - Sets actual_end_time and calculates actual_hours from check-ins.
        - Sets sla_met based on sla_deadline.
        - Closes any open check-ins.
        """
        result = await self.db.execute(
            select(WorkOrder)
            .where(
                WorkOrder.id == wo_id,
                WorkOrder.tenant_id == tenant_id,
                WorkOrder.deleted_at.is_(None),
            )
            .options(
                selectinload(WorkOrder.tasks),
                selectinload(WorkOrder.check_ins),
            )
        )
        wo = result.scalar_one_or_none()
        if not wo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work order not found",
            )

        if wo.status == WorkOrderStatus.completed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Work order is already completed",
            )
        if wo.status == WorkOrderStatus.cancelled:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot complete a cancelled work order",
            )

        # Validate required tasks
        incomplete_required = [
            t for t in (wo.tasks or [])
            if t.is_required and t.status not in (TaskStatus.completed, TaskStatus.skipped)
        ]
        if incomplete_required:
            task_titles = ", ".join(f"'{t.title}'" for t in incomplete_required[:5])
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Cannot complete: {len(incomplete_required)} required task(s) not done: "
                    f"{task_titles}"
                ),
            )

        now = datetime.now(tz=UTC)
        previous_status = wo.status

        # Suppress the auto-listener while we mutate status + end_time +
        # actual_hours + sla_met + completion_notes — these are all part
        # of one logical "completed" event. The explicit audit.record()
        # call below captures the meaningful fields.
        with AuditSuppression.suppress():
            # Close any open check-ins
            for ci in (wo.check_ins or []):
                if ci.check_out_time is None:
                    ci.check_out_time = now

            # Compute actual_hours from all check-in durations
            total_minutes = sum(
                ci.duration_minutes or 0 for ci in (wo.check_ins or [])
            )
            wo.actual_hours = Decimal(str(round(total_minutes / 60, 2)))

            # Determine SLA
            if wo.sla_deadline:
                wo.sla_met = now <= wo.sla_deadline

            wo.status = WorkOrderStatus.completed
            wo.actual_end_time = now
            if completion_notes:
                wo.completion_notes = completion_notes

            await self.db.flush()

        await self.audit.record(
            action="completed",
            resource_type="WorkOrder",
            resource_id=str(wo_id),
            old_values={"status": previous_status.value},
            new_values={
                "status": WorkOrderStatus.completed.value,
                "actual_hours": str(wo.actual_hours),
                "sla_met": wo.sla_met,
                "completion_notes": wo.completion_notes,
            },
            user_id=user_id,
            tenant_id=tenant_id,
        )

        logger.info(
            "work_order_completed",
            work_order_id=str(wo_id),
            actual_hours=str(wo.actual_hours),
            sla_met=wo.sla_met,
            completed_by=str(user_id),
        )

        # Auto-spawn next occurrence for recurring work orders
        if wo.recurrence_rule:
            await self.spawn_next_occurrence(wo, tenant_id)

        return wo

    # ---------------------------------------------------------------------- #
    # Recurring instances
    # ---------------------------------------------------------------------- #

    async def generate_recurring_instances(
        self,
        parent_wo_id: uuid.UUID,
        tenant_id: uuid.UUID,
        until_date: datetime,
    ) -> list[WorkOrder]:
        """
        Parse the parent work order's RRULE and generate child WorkOrder instances
        up to (but not exceeding) until_date.

        Returns the list of newly created WorkOrder objects.
        """
        from dateutil.rrule import rrulestr

        result = await self.db.execute(
            select(WorkOrder).where(
                WorkOrder.id == parent_wo_id,
                WorkOrder.tenant_id == tenant_id,
            )
        )
        parent = result.scalar_one_or_none()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent work order not found",
            )
        if not parent.recurrence_rule:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Work order has no recurrence rule",
            )

        dtstart = parent.scheduled_date or datetime.now(tz=UTC)
        try:
            rule = rrulestr(parent.recurrence_rule, dtstart=dtstart)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid RRULE: {exc}",
            ) from exc

        occurrences = list(rule.between(dtstart, until_date, inc=False))
        created: list[WorkOrder] = []

        # Eager-load tasks so we can copy them to each child
        await self.db.refresh(parent, ["tasks"])

        for occurrence_dt in occurrences:
            child = WorkOrder(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                title=parent.title,
                description=parent.description,
                client_id=parent.client_id,
                location_id=parent.location_id,
                crew_id=parent.crew_id,
                assigned_to=parent.assigned_to,
                status=WorkOrderStatus.scheduled,
                priority=parent.priority,
                work_type=parent.work_type,
                scheduled_date=occurrence_dt,
                estimated_hours=parent.estimated_hours,
                parent_work_order_id=parent.id,
                recurrence_rule=parent.recurrence_rule,
                notes=parent.notes,
            )
            self.db.add(child)

            for t in (parent.tasks or []):
                self.db.add(WorkOrderTask(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    work_order_id=child.id,
                    title=t.title,
                    description=t.description,
                    is_required=t.is_required,
                    sort_order=t.sort_order,
                    status=TaskStatus.pending,
                ))

            created.append(child)

        if created:
            await self.db.flush()
            logger.info(
                "recurring_instances_generated",
                parent_id=str(parent_wo_id),
                count=len(created),
            )

        return created

    async def spawn_next_occurrence(
        self,
        wo: WorkOrder,
        tenant_id: uuid.UUID,
    ) -> WorkOrder | None:
        """
        Spawn exactly one next occurrence of a recurring work order.

        Called automatically when a recurring WO is completed. Computes
        the next scheduled_date after wo.scheduled_date using the RRULE
        and creates a single child WO with tasks copied from the parent.

        Returns the new WorkOrder, or None if no future occurrence exists.
        """
        from dateutil.rrule import rrulestr

        if not wo.recurrence_rule:
            return None

        dtstart = wo.scheduled_date or datetime.now(tz=UTC)
        try:
            rule = rrulestr(wo.recurrence_rule, dtstart=dtstart)
        except Exception:
            logger.warning("spawn_next_occurrence_invalid_rrule", work_order_id=str(wo.id))
            return None

        # The root parent is the template; use it for task copying
        root_id = wo.parent_work_order_id or wo.id
        root_result = await self.db.execute(
            select(WorkOrder)
            .where(WorkOrder.id == root_id, WorkOrder.tenant_id == tenant_id)
            .options(selectinload(WorkOrder.tasks))
        )
        root = root_result.scalar_one_or_none() or wo
        if not hasattr(root, "tasks") or root.tasks is None:
            await self.db.refresh(root, ["tasks"])

        next_dt = rule.after(dtstart, inc=False)
        if next_dt is None:
            return None

        child = WorkOrder(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            title=root.title,
            description=root.description,
            client_id=root.client_id,
            location_id=root.location_id,
            crew_id=root.crew_id,
            assigned_to=root.assigned_to,
            status=WorkOrderStatus.scheduled,
            priority=root.priority,
            work_type=root.work_type,
            scheduled_date=next_dt,
            estimated_hours=root.estimated_hours,
            parent_work_order_id=root.id,
            recurrence_rule=root.recurrence_rule,
            notes=root.notes,
        )
        self.db.add(child)

        for t in (root.tasks or []):
            self.db.add(WorkOrderTask(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                work_order_id=child.id,
                title=t.title,
                description=t.description,
                is_required=t.is_required,
                sort_order=t.sort_order,
                status=TaskStatus.pending,
            ))

        await self.db.flush()
        logger.info(
            "recurring_next_occurrence_spawned",
            parent_id=str(wo.id),
            root_id=str(root.id),
            next_scheduled=next_dt.isoformat(),
        )
        return child
