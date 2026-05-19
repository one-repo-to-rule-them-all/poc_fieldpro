"""Audit log persistence — public API.

See ``docs/proposals/audit-log-persistence.md`` for the design.

This package owns:
    * ``AuditContext``      — actor info carried via contextvars
    * ``AuditService``      — single write surface for audit_logs rows
    * ``bind_audit_context``— FastAPI dep that populates the contextvar per request
    * ``get_audit_service`` — FastAPI dep that constructs AuditService(db)

Phase 3 (listeners + suppression) and Phase 4 (read API) will extend this
package without changing the public surface.
"""

from __future__ import annotations

from app.core.audit.context import (
    AuditContext,
    bind_audit_context,
    get_audit_context,
)
from app.core.audit.listeners import AuditListener
from app.core.audit.service import AuditService, get_audit_service
from app.core.audit.suppression import AuditSuppression

__all__ = [
    "AuditContext",
    "AuditListener",
    "AuditService",
    "AuditSuppression",
    "bind_audit_context",
    "get_audit_context",
    "get_audit_service",
]
