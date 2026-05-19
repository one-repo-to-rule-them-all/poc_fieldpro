"""Actor context for audit log writes.

The contextvar pattern lets code far from the HTTP request (notably the
SQLAlchemy event listeners added in Phase 3) read who's acting without
passing ``request`` and ``current_user`` through every call site.

Flow per request:
    1. ``bind_audit_context`` runs as a FastAPI dependency on the v1
       router (see ``app/api/v1/router.py``).
    2. It resolves the authenticated user via ``_get_optional_current_user``
       — None for anonymous routes like /auth/login.
    3. It builds an ``AuditContext`` and sets the contextvar.
    4. ``AuditService.record(...)`` reads the contextvar to fill
       ``user_id`` / ``tenant_id`` / ``ip_address`` / ``user_agent``
       defaults; the caller can override any of them.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.database import get_db
from app.core.security import verify_access_token

logger = structlog.get_logger(__name__)


# --------------------------------------------------------------------------- #
# AuditContext dataclass
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class AuditContext:
    """Immutable snapshot of actor info for a single request."""

    user_id: UUID | None = None
    tenant_id: UUID | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None

    @classmethod
    def anonymous(cls) -> AuditContext:
        """An empty context — used as the contextvar default."""
        return cls()


# --------------------------------------------------------------------------- #
# ContextVar (module-private; read via get_audit_context)
# --------------------------------------------------------------------------- #

_AUDIT_CONTEXT: ContextVar[AuditContext] = ContextVar(
    "audit_context", default=AuditContext.anonymous()
)


def get_audit_context() -> AuditContext:
    """Read the audit context for the current request.

    Returns an empty (anonymous) context if no request is in flight or
    ``bind_audit_context`` has not run yet.
    """
    return _AUDIT_CONTEXT.get()


# --------------------------------------------------------------------------- #
# Optional current user — never raises 401 (anonymous routes are valid)
# --------------------------------------------------------------------------- #

_audit_bearer = HTTPBearer(auto_error=False)


async def _get_optional_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_audit_bearer)
    ],
    db: AsyncSession = Depends(get_db),
):
    """Resolve the authenticated user, or None if no/invalid bearer token.

    Unlike ``app.core.dependencies.get_current_user``, this never raises —
    anonymous routes like /auth/login are legitimate and should produce an
    audit row with ``user_id = None`` for the bind step.
    """
    from app.models.user import User  # deferred to avoid circular imports

    if credentials is None or credentials.scheme.lower() != "bearer":
        return None

    try:
        payload = verify_access_token(credentials.credentials)
    except Exception:
        return None

    user_id_str = payload.get("sub")
    if user_id_str is None:
        return None

    try:
        user_uuid = UUID(user_id_str)
    except (ValueError, TypeError):
        return None

    result = await db.execute(select(User).where(User.id == user_uuid))
    return result.scalar_one_or_none()


# --------------------------------------------------------------------------- #
# Public dependency — wired on the v1 router
# --------------------------------------------------------------------------- #


async def bind_audit_context(
    request: Request,
    current_user=Depends(_get_optional_current_user),
) -> None:
    """Populate the audit contextvar for the duration of this request.

    Anonymous routes (login, register, password reset) leave
    ``user_id`` / ``tenant_id`` as None; the route handler can still
    override either explicitly when calling ``AuditService.record()``.
    """
    request_id = structlog.contextvars.get_contextvars().get("request_id")

    ctx = AuditContext(
        user_id=current_user.id if current_user else None,
        tenant_id=current_user.tenant_id if current_user else None,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        request_id=request_id,
    )
    _AUDIT_CONTEXT.set(ctx)
