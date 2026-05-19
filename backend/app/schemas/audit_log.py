"""Audit log read API schemas.

Two response shapes:
    * AuditLogListResponse — light row for the paginated list endpoint.
      JOINs in actor_email/actor_name from the users table so clients
      don't have to do their own lookup.
    * AuditLogDetailResponse — full row including old_values / new_values.

Field names match the keys produced by `_audit_log_to_dict()` in
``app/api/v1/audit_logs.py`` exactly (per the response_model contract
documented in CLAUDE.md).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogListResponse(BaseModel):
    """Light row for the paginated list endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    tenant_id: UUID | None
    user_id: UUID | None
    actor_email: str | None
    actor_name: str | None
    action: str
    resource_type: str
    resource_id: str | None
    request_id: str | None
    ip_address: str | None


class AuditLogDetailResponse(AuditLogListResponse):
    """Full detail row — same as list + user_agent + old/new values."""

    user_agent: str | None
    old_values: dict[str, Any] | None
    new_values: dict[str, Any] | None
