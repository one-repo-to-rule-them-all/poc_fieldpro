"""Add request_id column and v_audit_events view.

Two complementary improvements for audit log usability (#52 Phase 3 follow-up):

1. ``audit_logs.request_id`` — pulled from ``AuditContext.request_id`` which
   already binds the per-request UUID set by ``RequestIDMiddleware``. Lets
   queries group every audit row produced by a single HTTP request — e.g.,
   "Invoice + 5 InvoiceLineItem rows in one POST" become a single
   ``WHERE request_id = ?`` query.

2. ``v_audit_events`` view — pre-JOINs audit_logs to users so any psql
   session reads the actor's email/name without writing a JOIN every time.
   The view is the easy-to-query surface; the table stays the source of
   truth.

Revision ID: 002_audit_request_id_and_view
Revises: 001_initial
Create Date: 2026-05-18 22:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_audit_request_id_and_view"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # 1. audit_logs.request_id
    # ------------------------------------------------------------------ #
    op.add_column(
        "audit_logs",
        sa.Column("request_id", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_audit_logs_request_id",
        "audit_logs",
        ["request_id"],
    )

    # ------------------------------------------------------------------ #
    # 2. v_audit_events — readable JOIN of audit_logs + users
    #
    # Reads return one row per audit_logs row, with the actor's email
    # and full name decoded. Falls back to NULL when the actor was
    # anonymous (login_failed) or the user has since been deleted.
    # ------------------------------------------------------------------ #
    op.execute(
        """
        CREATE OR REPLACE VIEW v_audit_events AS
        SELECT
            al.id,
            al.created_at,
            al.tenant_id,
            al.user_id,
            u.email                                         AS actor_email,
            CONCAT_WS(' ', u.first_name, u.last_name)       AS actor_name,
            al.action,
            al.resource_type,
            al.resource_id,
            al.request_id,
            al.ip_address,
            al.user_agent,
            al.old_values,
            al.new_values
        FROM audit_logs al
        LEFT JOIN users u ON u.id = al.user_id
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_audit_events")
    op.drop_index("ix_audit_logs_request_id", table_name="audit_logs")
    op.drop_column("audit_logs", "request_id")
