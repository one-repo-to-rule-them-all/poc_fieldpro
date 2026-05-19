"""Context manager for disabling the SQLAlchemy audit listener.

Two callers:
    1. Seed scripts / bulk fixtures — keeping the audit log free of
       demo-data noise.
    2. Service-layer overrides — when the route wants to emit a richer
       domain-verb audit row (e.g. action="completed" instead of the
       generic "updated"), it wraps the underlying ORM mutation in
       ``suppress()`` so the listener doesn't double-write.

Usage:

    from app.core.audit import AuditSuppression

    with AuditSuppression.suppress():
        db.add(work_order)
        await db.flush()
    # listener stayed silent for the above; emit your own row now
    await audit.record(action="completed", resource_type="WorkOrder", ...)
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_SUPPRESS_AUDIT: ContextVar[bool] = ContextVar("suppress_audit", default=False)


class AuditSuppression:
    """Static surface for the suppression context manager + status check."""

    @staticmethod
    @contextmanager
    def suppress() -> Iterator[None]:
        """Disable the audit listener for the duration of the block."""
        token = _SUPPRESS_AUDIT.set(True)
        try:
            yield
        finally:
            _SUPPRESS_AUDIT.reset(token)

    @staticmethod
    def is_active() -> bool:
        """Return True if a `suppress()` block is currently open."""
        return _SUPPRESS_AUDIT.get()
