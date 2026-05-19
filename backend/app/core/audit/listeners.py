"""SQLAlchemy event listeners for CRUD audit capture.

Phase 3 of the audit log work (#52). One listener class registers
``after_insert`` / ``after_update`` / ``after_delete`` handlers on a
fixed allowlist of models. Each handler:

    1. Bails early if ``AuditSuppression.is_active()`` — seed scripts
       and service-layer escape-hatch paths use this.
    2. Reads the actor info from ``AuditContext`` (set by the request
       dependency in ``app.core.audit.context``).
    3. Captures the changed fields via SQLAlchemy attribute history,
       stripping sensitive fields per ``DEFAULT_DENY_FIELDS`` plus the
       per-model ``__audit_deny_fields__`` class attribute.
    4. Inserts an ``audit_logs`` row directly via the active connection
       (NOT the ORM session) so the listener doesn't recurse into
       itself or fight the flush.

Soft-delete handling: an UPDATE that flips ``deleted_at`` from null to
non-null is recorded as ``action="deleted"`` rather than ``"updated"``.
This is the only case where the listener overrides the generic CRUD verb.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, ClassVar
from uuid import UUID, uuid4

from sqlalchemy import event, insert, inspect
import structlog

from app.core.audit.context import get_audit_context
from app.core.audit.suppression import AuditSuppression
from app.models.audit import AuditLog
from app.models.client import Client
from app.models.crew import Crew
from app.models.inventory import Equipment, InventoryItem, InventoryTransaction
from app.models.invoice import Invoice, InvoiceLineItem, Payment
from app.models.location import Location
from app.models.user import User
from app.models.work_order import WorkOrder

logger = structlog.get_logger(__name__)


# Sensitive fields that should never be serialized into old/new_values —
# applied to every audited model on top of per-model __audit_deny_fields__.
DEFAULT_DENY_FIELDS: frozenset[str] = frozenset(
    {
        "password_hash",
        "hashed_password",
        "mfa_secret",
        "mfa_backup_codes",
        "token_hash",
        "secret",
    }
)


def _serialize(value: Any) -> Any:
    """Convert a Python value into a JSON-serializable form for JSONB storage."""
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list | tuple):
        return [_serialize(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _serialize(v) for k, v in value.items()}
    return repr(value)


class AuditListener:
    """Central registration point for SQLAlchemy audit hooks.

    Add a model to ``AUDITED_MODELS`` to enable CRUD audit capture for
    it. Set ``__audit_deny_fields__: ClassVar[set[str]] = {...}`` on the
    model to strip additional sensitive fields beyond the defaults.
    """

    # Full 11-model allowlist locked in the scoping doc (#52 Section 4).
    # Order is illustrative — registration is independent.
    AUDITED_MODELS: ClassVar[list[type]] = [
        Client,
        Location,
        Crew,
        WorkOrder,
        Invoice,
        InvoiceLineItem,
        Payment,
        User,
        Equipment,
        InventoryItem,
        InventoryTransaction,
    ]

    @classmethod
    def register(cls) -> None:
        """Attach event handlers for every model in ``AUDITED_MODELS``."""
        for model in cls.AUDITED_MODELS:
            event.listen(model, "after_insert", cls._on_insert)
            event.listen(model, "after_update", cls._on_update)
            event.listen(model, "after_delete", cls._on_delete)
        logger.info(
            "audit_listeners_registered",
            models=[m.__name__ for m in cls.AUDITED_MODELS],
        )

    # ---------------------------------------------------------------- #
    # Event handlers
    # ---------------------------------------------------------------- #

    @classmethod
    def _on_insert(cls, mapper: Any, connection: Any, target: Any) -> None:
        if AuditSuppression.is_active():
            return
        new_values = cls._snapshot(target)
        cls._write(connection, target, action="created", old_values=None, new_values=new_values)

    @classmethod
    def _on_update(cls, mapper: Any, connection: Any, target: Any) -> None:
        if AuditSuppression.is_active():
            return
        old_values, new_values = cls._diff(target)
        if not old_values and not new_values:
            # No-op update (e.g. PATCH that didn't change anything)
            return

        action = "updated"
        # Soft-delete detection: deleted_at flipped from null to a value
        if (
            "deleted_at" in new_values
            and new_values["deleted_at"] is not None
            and old_values.get("deleted_at") is None
        ):
            action = "deleted"

        cls._write(
            connection,
            target,
            action=action,
            old_values=old_values,
            new_values=new_values,
        )

    @classmethod
    def _on_delete(cls, mapper: Any, connection: Any, target: Any) -> None:
        if AuditSuppression.is_active():
            return
        old_values = cls._snapshot(target)
        cls._write(connection, target, action="deleted", old_values=old_values, new_values=None)

    # ---------------------------------------------------------------- #
    # Internal helpers
    # ---------------------------------------------------------------- #

    @classmethod
    def _deny_fields(cls, target: Any) -> frozenset[str]:
        per_model: frozenset[str] | set[str] = getattr(
            type(target), "__audit_deny_fields__", frozenset()
        )
        return DEFAULT_DENY_FIELDS | frozenset(per_model)

    @classmethod
    def _snapshot(cls, target: Any) -> dict[str, Any]:
        """Capture every column on the instance, minus deny-listed fields."""
        insp = inspect(target)
        deny = cls._deny_fields(target)
        return {
            attr.key: _serialize(getattr(target, attr.key))
            for attr in insp.mapper.column_attrs
            if attr.key not in deny
        }

    @classmethod
    def _diff(cls, target: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        """Return (old, new) for every changed column, minus deny-listed."""
        insp = inspect(target)
        deny = cls._deny_fields(target)
        old_values: dict[str, Any] = {}
        new_values: dict[str, Any] = {}
        for attr in insp.mapper.column_attrs:
            if attr.key in deny:
                continue
            hist = insp.attrs[attr.key].history
            if not hist.has_changes():
                continue
            old_values[attr.key] = _serialize(hist.deleted[0]) if hist.deleted else None
            new_values[attr.key] = _serialize(hist.added[0]) if hist.added else None
        return old_values, new_values

    @classmethod
    def _write(
        cls,
        connection: Any,
        target: Any,
        *,
        action: str,
        old_values: dict[str, Any] | None,
        new_values: dict[str, Any] | None,
    ) -> None:
        """Persist the audit row via raw connection (NOT the ORM session).

        Using ``connection.execute(insert(AuditLog).values(...))`` keeps
        the write out of the current flush cycle — no recursion into our
        own listeners and no fighting with autoflush.
        """
        ctx = get_audit_context()
        resource_id = (
            str(target.id) if getattr(target, "id", None) is not None else None
        )
        # Tenant_id resolution: prefer the target's own tenant (the affected
        # resource) and fall back to the actor's context tenant. They almost
        # always match; the model wins when they don't.
        tenant_id = getattr(target, "tenant_id", None) or ctx.tenant_id

        connection.execute(
            insert(AuditLog).values(
                id=uuid4(),
                action=action,
                resource_type=type(target).__name__,
                resource_id=resource_id,
                user_id=ctx.user_id,
                tenant_id=tenant_id,
                ip_address=ctx.ip_address,
                user_agent=ctx.user_agent,
                request_id=ctx.request_id,
                old_values=old_values,
                new_values=new_values,
            )
        )
