"""Phase 3 listener integration tests for #52.

Covers Section 8.2 - 8.10 of the verification matrix in the scoping doc
(``docs/proposals/audit-log-persistence.md``). The listener pattern is
exercised end-to-end through the API where routes exist, and via direct
ORM where routes don't (Equipment / Inventory).
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditSuppression
from app.models.audit import AuditLog
from app.models.client import Client
from app.models.tenant import Tenant
from app.models.user import User

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


async def _audit_rows_for(
    db: AsyncSession,
    *,
    resource_type: str,
    resource_id: str | None = None,
) -> list[AuditLog]:
    """Pull audit rows matching the resource, ordered by created_at."""
    q = select(AuditLog).where(AuditLog.resource_type == resource_type)
    if resource_id:
        q = q.where(AuditLog.resource_id == resource_id)
    q = q.order_by(AuditLog.created_at)
    result = await db.execute(q)
    return list(result.scalars().all())


# --------------------------------------------------------------------------- #
# Client CRUD listener (Section 8.3)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_client_create_writes_audit_row(
    client: AsyncClient, admin_token: str, db: AsyncSession
) -> None:
    """POST /clients → action='created' with full new_values snapshot."""
    resp = await client.post(
        "/api/v1/clients/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Test Client", "code": "TC-1"},
    )
    assert resp.status_code == 201, resp.text
    client_id = resp.json()["id"]

    rows = await _audit_rows_for(db, resource_type="Client", resource_id=client_id)
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "created"
    assert row.old_values is None
    assert row.new_values is not None
    assert row.new_values["name"] == "Test Client"
    assert row.new_values["code"] == "TC-1"


@pytest.mark.asyncio
async def test_client_update_single_field_diff(
    client: AsyncClient, admin_token: str, db: AsyncSession
) -> None:
    """PATCH /clients/:id → action='updated' with only the changed field in old/new_values."""
    create = await client.post(
        "/api/v1/clients/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Original Name", "code": "TC-2"},
    )
    client_id = create.json()["id"]

    patch = await client.patch(
        f"/api/v1/clients/{client_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Updated Name"},
    )
    assert patch.status_code == 200, patch.text

    rows = await _audit_rows_for(db, resource_type="Client", resource_id=client_id)
    assert len(rows) == 2
    update_row = rows[1]
    assert update_row.action == "updated"
    # Only `name` (and possibly updated_at) appear in the diff
    assert "name" in update_row.new_values
    assert update_row.new_values["name"] == "Updated Name"
    assert update_row.old_values["name"] == "Original Name"
    # code wasn't changed → not in the diff
    assert "code" not in update_row.old_values
    assert "code" not in update_row.new_values


@pytest.mark.asyncio
async def test_client_soft_delete_emits_deleted_action(
    client: AsyncClient, admin_token: str, db: AsyncSession
) -> None:
    """DELETE /clients/:id (soft-delete) emits action='deleted', not 'updated'."""
    create = await client.post(
        "/api/v1/clients/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Soft Delete Test", "code": "SD-1"},
    )
    client_id = create.json()["id"]

    delete = await client.delete(
        f"/api/v1/clients/{client_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert delete.status_code == 204, delete.text

    rows = await _audit_rows_for(db, resource_type="Client", resource_id=client_id)
    actions = [r.action for r in rows]
    assert "created" in actions
    assert "deleted" in actions
    assert "updated" not in actions  # soft-delete is detected as `deleted`, not generic `updated`


# --------------------------------------------------------------------------- #
# Direct-ORM listener firing (Section 8.10 — suppress + transaction behavior)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_suppress_audit_skips_listener(
    db: AsyncSession, tenant: Tenant
) -> None:
    """Mutations inside AuditSuppression.suppress() produce no audit row."""
    with AuditSuppression.suppress():
        c = Client(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            name="Silent Client",
            code="SILENT-1",
            billing_address={},
        )
        db.add(c)
        await db.flush()

    rows = await _audit_rows_for(db, resource_type="Client", resource_id=str(c.id))
    assert rows == []


@pytest.mark.asyncio
async def test_user_password_hash_stripped_from_audit(
    db: AsyncSession, admin_user: User
) -> None:
    """Updating User.hashed_password alongside a non-sensitive field leaves
    hashed_password OUT of old_values/new_values while the non-sensitive
    field still appears in the diff.

    (Important: if ONLY hashed_password changes, the listener emits NO row
    at all — there's nothing safe to log. We change first_name too so an
    audit row is guaranteed.)
    """
    admin_user.hashed_password = "new_hash_value_for_test"
    admin_user.first_name = "Updated First Name"
    await db.flush()

    rows = await _audit_rows_for(db, resource_type="User", resource_id=str(admin_user.id))
    update_rows = [r for r in rows if r.action == "updated"]
    assert len(update_rows) >= 1
    row = update_rows[-1]
    # first_name should appear in the diff
    assert "first_name" in row.new_values
    assert row.new_values["first_name"] == "Updated First Name"
    # hashed_password should NOT appear in either column — stripped by deny-list
    assert "hashed_password" not in row.old_values
    assert "hashed_password" not in row.new_values


@pytest.mark.asyncio
async def test_user_sensitive_only_update_writes_no_row(
    db: AsyncSession, admin_user: User
) -> None:
    """When ONLY sensitive fields change, the listener emits no audit row at
    all (there's nothing safe to log). This is the listener's correct
    behavior — see ``app/core/audit/listeners.py`` _on_update early-exit."""
    # Count audit rows for this user before the mutation
    before = await _audit_rows_for(db, resource_type="User", resource_id=str(admin_user.id))

    admin_user.hashed_password = "another_new_hash"
    await db.flush()

    after = await _audit_rows_for(db, resource_type="User", resource_id=str(admin_user.id))
    assert len(after) == len(before)  # no new row
