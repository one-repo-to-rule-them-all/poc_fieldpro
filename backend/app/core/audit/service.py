"""AuditService — single write surface for the audit_logs table.

Phase 2: explicit calls from service-layer code (auth flows, state
machines, domain events).

Phase 3 will add an ``AuditListener`` that drives SQLAlchemy event-based
auto-capture for CRUD; that listener will call this same service.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.audit.context import get_audit_context
from app.core.database import get_db
from app.models.audit import AuditLog

logger = structlog.get_logger(__name__)


class AuditService:
    """Persist audit log entries.

    Defaults for ``user_id`` / ``tenant_id`` / ``ip_address`` / ``user_agent``
    come from the current ``AuditContext`` (populated by ``bind_audit_context``).
    Callers may pass any of those four explicitly to override — useful for
    auth flows where the user is identified inside the route handler rather
    than via JWT.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record(
        self,
        *,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        old_values: Mapping[str, Any] | None = None,
        new_values: Mapping[str, Any] | None = None,
        user_id: UUID | None = None,
        tenant_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        autonomous: bool = False,
    ) -> AuditLog:
        """Persist a single audit row.

        By default the row is inserted inside the caller's transaction and
        commits/rolls back atomically with it. This is the right semantics
        for CRUD events (Phase 3 listener path) — a failed WO update should
        not leave behind an audit row claiming the update happened.

        Pass ``autonomous=True`` for failure-path audit events that must
        survive a subsequent rollback or HTTPException. The canonical
        case is ``login_failed``: the route raises 401 after recording the
        event, which triggers ``get_db``'s rollback path and would otherwise
        destroy the audit row. ``autonomous=True`` issues a ``commit()``
        before returning so the row is durable.
        """
        ctx = get_audit_context()

        row = AuditLog(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_values=dict(old_values) if old_values else None,
            new_values=dict(new_values) if new_values else None,
            user_id=user_id or ctx.user_id,
            tenant_id=tenant_id or ctx.tenant_id,
            ip_address=ip_address or ctx.ip_address,
            user_agent=user_agent or ctx.user_agent,
            request_id=ctx.request_id,
        )
        self.db.add(row)
        await self.db.flush()

        if autonomous:
            # Commit the row to its own transaction so it survives any
            # subsequent rollback (e.g. the route raising HTTPException).
            # A new transaction auto-begins for any later DB work in this
            # session, and the request's eventual rollback becomes a no-op.
            await self.db.commit()

        return row

    async def record_model_change(
        self,
        *,
        target: Any,
        action: str,
        old_values: Mapping[str, Any] | None = None,
        new_values: Mapping[str, Any] | None = None,
    ) -> AuditLog:
        """Convenience entry point for the Phase 3 SQLAlchemy listener.

        Derives ``resource_type`` from the model class name and ``resource_id``
        from ``target.id``. Phase 2 ships this method but does not yet call it
        — Phase 3 wires the listener.
        """
        return await self.record(
            action=action,
            resource_type=type(target).__name__,
            resource_id=str(target.id) if getattr(target, "id", None) is not None else None,
            old_values=old_values,
            new_values=new_values,
        )


# --------------------------------------------------------------------------- #
# FastAPI dependency
# --------------------------------------------------------------------------- #


def get_audit_service(db: AsyncSession = Depends(get_db)) -> AuditService:
    """Inject an AuditService bound to the request's DB session."""
    return AuditService(db)
