# Import all models here so Alembic autogenerate picks them up.
# Order matters for FK resolution.
from app.models.audit import AuditLog
from app.models.client import Client
from app.models.crew import Crew, CrewMember
from app.models.inventory import Equipment, InventoryItem, InventoryTransaction
from app.models.invoice import Invoice, InvoiceLineItem, Payment
from app.models.location import Location
from app.models.tenant import SubscriptionPlan, Tenant
from app.models.user import EmployeeProfile, RefreshToken, User
from app.models.work_order import (
    WorkOrder,
    WorkOrderAttachment,
    WorkOrderCheckIn,
    WorkOrderTask,
)

__all__ = [
    "Tenant", "SubscriptionPlan",
    "User", "EmployeeProfile", "RefreshToken",
    "Client",
    "Location",
    "Crew", "CrewMember",
    "WorkOrder", "WorkOrderTask", "WorkOrderAttachment", "WorkOrderCheckIn",
    "Equipment", "InventoryItem", "InventoryTransaction",
    "Invoice", "InvoiceLineItem", "Payment",
    "AuditLog",
]
