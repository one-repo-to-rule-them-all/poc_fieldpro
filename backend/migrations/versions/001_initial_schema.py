"""Initial schema — all FieldPro tables.

Revision ID: 001_initial
Revises:
Create Date: 2026-05-08 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------------------------------------------------------------------- #
    # 1. subscription_plans
    # ---------------------------------------------------------------------- #
    op.create_table(
        "subscription_plans",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "price_monthly",
            sa.Numeric(10, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "price_yearly",
            sa.Numeric(10, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "max_users",
            sa.Integer,
            nullable=False,
            server_default=sa.text("10"),
        ),
        sa.Column(
            "max_locations",
            sa.Integer,
            nullable=False,
            server_default=sa.text("50"),
        ),
        sa.Column(
            "features",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # ---------------------------------------------------------------------- #
    # 2. tenants
    # ---------------------------------------------------------------------- #
    op.create_table(
        "tenants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("domain", sa.String(255), nullable=True, unique=True),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "subscription_plan_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("subscription_plans.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("idx_tenants_slug", "tenants", ["slug"])

    # ---------------------------------------------------------------------- #
    # 3. tenant_subscriptions
    # ---------------------------------------------------------------------- #
    op.create_table(
        "tenant_subscriptions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "active", "past_due", "cancelled", "trialing",
                name="subscription_status",
            ),
            nullable=False,
            server_default="trialing",
        ),
        sa.Column("current_period_start", sa.String(50), nullable=True),
        sa.Column("current_period_end", sa.String(50), nullable=True),
        sa.Column(
            "stripe_subscription_id",
            sa.String(255),
            nullable=True,
            unique=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_tenant_subscriptions_tenant_id",
        "tenant_subscriptions",
        ["tenant_id"],
    )

    # ---------------------------------------------------------------------- #
    # 4. users
    # ---------------------------------------------------------------------- #
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column(
            "role",
            sa.Enum(
                "platform_owner",
                "tenant_admin",
                "manager",
                "employee",
                "client_user",
                name="user_role",
            ),
            nullable=False,
            server_default="employee",
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "is_verified",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "mfa_enabled",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("mfa_secret", sa.String(64), nullable=True),
        sa.Column("last_login_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )
    op.create_index("idx_users_tenant_id", "users", ["tenant_id"])
    op.create_index("idx_users_email", "users", ["email"])

    # ---------------------------------------------------------------------- #
    # 4. refresh_tokens
    # ---------------------------------------------------------------------- #
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "expires_at", sa.TIMESTAMP(timezone=True), nullable=False
        ),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("idx_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index(
        "idx_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"]
    )

    # ---------------------------------------------------------------------- #
    # 5. employee_profiles
    # ---------------------------------------------------------------------- #
    op.create_table(
        "employee_profiles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("employee_number", sa.String(50), nullable=True),
        sa.Column("hire_date", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("hourly_rate", sa.Numeric(10, 2), nullable=True),
        sa.Column(
            "certifications",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "emergency_contact",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_employee_profiles_tenant_id", "employee_profiles", ["tenant_id"]
    )
    op.create_index(
        "idx_employee_profiles_user_id", "employee_profiles", ["user_id"]
    )

    # ---------------------------------------------------------------------- #
    # 6. clients
    # ---------------------------------------------------------------------- #
    op.create_table(
        "clients",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column(
            "industry",
            sa.Enum(
                "commercial_cleaning",
                "janitorial",
                "landscaping",
                "hvac",
                "plumbing",
                "electrical",
                "security",
                "pest_control",
                "facility_management",
                "construction",
                "other",
                name="industry_type",
            ),
            nullable=True,
        ),
        sa.Column(
            "billing_address",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("billing_email", sa.String(320), nullable=True),
        sa.Column("billing_phone", sa.String(30), nullable=True),
        sa.Column(
            "contract_start_date", sa.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column(
            "contract_end_date", sa.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "tenant_id", "code", name="uq_clients_tenant_code"
        ),
    )
    op.create_index("idx_clients_tenant_id", "clients", ["tenant_id"])

    # ---------------------------------------------------------------------- #
    # 7. client_contacts
    # ---------------------------------------------------------------------- #
    op.create_table(
        "client_contacts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("title", sa.String(150), nullable=True),
        sa.Column(
            "is_primary",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_client_contacts_tenant_id", "client_contacts", ["tenant_id"]
    )
    op.create_index(
        "idx_client_contacts_client_id", "client_contacts", ["client_id"]
    )

    # ---------------------------------------------------------------------- #
    # 8. locations
    # ---------------------------------------------------------------------- #
    op.create_table(
        "locations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "address",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("latitude", sa.Numeric(10, 8), nullable=True),
        sa.Column("longitude", sa.Numeric(11, 8), nullable=True),
        sa.Column(
            "geofence_radius_meters",
            sa.Integer,
            nullable=False,
            server_default=sa.text("200"),
        ),
        sa.Column("access_instructions", sa.Text, nullable=True),
        sa.Column("special_requirements", sa.Text, nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "qr_code_token", sa.String(128), nullable=True, unique=True
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("idx_locations_tenant_id", "locations", ["tenant_id"])
    op.create_index("idx_locations_client_id", "locations", ["client_id"])
    op.create_index(
        "idx_locations_qr_code_token", "locations", ["qr_code_token"]
    )

    # ---------------------------------------------------------------------- #
    # 8. crews
    # ---------------------------------------------------------------------- #
    op.create_table(
        "crews",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "code", name="uq_crews_tenant_code"),
    )
    op.create_index("idx_crews_tenant_id", "crews", ["tenant_id"])

    # ---------------------------------------------------------------------- #
    # 9. crew_members
    # ---------------------------------------------------------------------- #
    op.create_table(
        "crew_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "crew_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("crews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.Enum("lead", "member", name="crew_member_role"),
            nullable=False,
            server_default="member",
        ),
        sa.Column(
            "joined_at", sa.TIMESTAMP(timezone=True), nullable=False
        ),
        sa.Column("left_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "tenant_id",
            "crew_id",
            "user_id",
            name="uq_crew_member_tenant_crew_user",
        ),
    )
    op.create_index("idx_crew_members_crew_id", "crew_members", ["crew_id"])
    op.create_index("idx_crew_members_user_id", "crew_members", ["user_id"])
    op.create_index(
        "idx_crew_members_tenant_id", "crew_members", ["tenant_id"]
    )

    # ---------------------------------------------------------------------- #
    # 10. work_orders
    # ---------------------------------------------------------------------- #
    op.create_table(
        "work_orders",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("clients.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("locations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "crew_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("crews.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "assigned_to",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "scheduled",
                "in_progress",
                "completed",
                "cancelled",
                "on_hold",
                name="work_order_status",
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "priority",
            sa.Enum(
                "low", "normal", "high", "urgent", name="priority"
            ),
            nullable=False,
            server_default="normal",
        ),
        sa.Column(
            "work_type",
            sa.Enum(
                "recurring", "one_time", "emergency", name="work_type"
            ),
            nullable=False,
            server_default="one_time",
        ),
        sa.Column(
            "scheduled_date", sa.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column(
            "scheduled_start_time",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "scheduled_end_time",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "actual_start_time", sa.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column(
            "actual_end_time", sa.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column("estimated_hours", sa.Numeric(6, 2), nullable=True),
        sa.Column("actual_hours", sa.Numeric(6, 2), nullable=True),
        sa.Column(
            "sla_deadline", sa.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column("sla_met", sa.Boolean, nullable=True),
        sa.Column("recurrence_rule", sa.String(500), nullable=True),
        sa.Column(
            "parent_work_order_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("work_orders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("internal_notes", sa.Text, nullable=True),
        sa.Column("completion_notes", sa.Text, nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("idx_work_orders_tenant_id", "work_orders", ["tenant_id"])
    op.create_index("idx_work_orders_client_id", "work_orders", ["client_id"])
    op.create_index(
        "idx_work_orders_location_id", "work_orders", ["location_id"]
    )
    op.create_index("idx_work_orders_crew_id", "work_orders", ["crew_id"])
    op.create_index(
        "idx_work_orders_assigned_to", "work_orders", ["assigned_to"]
    )
    op.create_index("idx_work_orders_status", "work_orders", ["status"])
    op.create_index(
        "idx_work_orders_scheduled_date",
        "work_orders",
        ["scheduled_date"],
    )
    op.create_index(
        "idx_work_orders_parent_id",
        "work_orders",
        ["parent_work_order_id"],
    )

    # ---------------------------------------------------------------------- #
    # 11. work_order_tasks
    # ---------------------------------------------------------------------- #
    op.create_table(
        "work_order_tasks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "work_order_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("work_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "is_required",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "completed",
                "skipped",
                "blocked",
                name="task_status",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "completed_by",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "completed_at", sa.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column(
            "sort_order",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_work_order_tasks_work_order_id",
        "work_order_tasks",
        ["work_order_id"],
    )
    op.create_index(
        "idx_work_order_tasks_tenant_id",
        "work_order_tasks",
        ["tenant_id"],
    )

    # ---------------------------------------------------------------------- #
    # 12. work_order_attachments
    # ---------------------------------------------------------------------- #
    op.create_table(
        "work_order_attachments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "work_order_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("work_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("work_order_tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "uploaded_by",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("s3_key", sa.String(500), nullable=False),
        sa.Column("thumbnail_s3_key", sa.String(500), nullable=True),
        sa.Column(
            "attachment_type",
            sa.Enum(
                "photo",
                "document",
                "signature",
                name="attachment_type",
            ),
            nullable=False,
            server_default="photo",
        ),
        sa.Column("caption", sa.String(500), nullable=True),
        sa.Column(
            "is_issue",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_work_order_attachments_work_order_id",
        "work_order_attachments",
        ["work_order_id"],
    )
    op.create_index(
        "idx_work_order_attachments_tenant_id",
        "work_order_attachments",
        ["tenant_id"],
    )

    # ---------------------------------------------------------------------- #
    # 13. work_order_check_ins
    # ---------------------------------------------------------------------- #
    op.create_table(
        "work_order_check_ins",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "work_order_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("work_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "check_in_time", sa.TIMESTAMP(timezone=True), nullable=False
        ),
        sa.Column(
            "check_out_time", sa.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column("check_in_latitude", sa.Numeric(10, 8), nullable=True),
        sa.Column("check_in_longitude", sa.Numeric(11, 8), nullable=True),
        sa.Column("check_out_latitude", sa.Numeric(10, 8), nullable=True),
        sa.Column("check_out_longitude", sa.Numeric(11, 8), nullable=True),
        sa.Column(
            "check_in_method",
            sa.Enum("gps", "qr_code", "manual", name="check_in_method"),
            nullable=False,
            server_default="gps",
        ),
        sa.Column(
            "distance_from_location_meters", sa.Integer, nullable=True
        ),
        sa.Column(
            "is_valid",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_work_order_check_ins_work_order_id",
        "work_order_check_ins",
        ["work_order_id"],
    )
    op.create_index(
        "idx_work_order_check_ins_user_id",
        "work_order_check_ins",
        ["user_id"],
    )
    op.create_index(
        "idx_work_order_check_ins_tenant_id",
        "work_order_check_ins",
        ["tenant_id"],
    )

    # ---------------------------------------------------------------------- #
    # 14. equipment
    # ---------------------------------------------------------------------- #
    op.create_table(
        "equipment",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("serial_number", sa.String(150), nullable=True),
        sa.Column("model", sa.String(150), nullable=True),
        sa.Column("manufacturer", sa.String(150), nullable=True),
        sa.Column("purchase_date", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "warranty_expires_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "available",
                "in_use",
                "maintenance",
                "retired",
                name="equipment_status",
            ),
            nullable=False,
            server_default="available",
        ),
        sa.Column(
            "current_crew_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("crews.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "location_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("locations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("idx_equipment_tenant_id", "equipment", ["tenant_id"])
    op.create_index("idx_equipment_status", "equipment", ["status"])

    # ---------------------------------------------------------------------- #
    # 15. inventory_items
    # ---------------------------------------------------------------------- #
    op.create_table(
        "inventory_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sku", sa.String(100), nullable=True),
        sa.Column(
            "unit",
            sa.String(50),
            nullable=False,
            server_default="each",
        ),
        sa.Column(
            "unit_cost",
            sa.Numeric(10, 4),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "current_quantity",
            sa.Numeric(12, 3),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "reorder_point",
            sa.Numeric(12, 3),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "reorder_quantity",
            sa.Numeric(12, 3),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column(
            "is_consumable",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_inventory_items_tenant_id", "inventory_items", ["tenant_id"]
    )
    op.create_index("idx_inventory_items_sku", "inventory_items", ["sku"])
    op.create_index(
        "idx_inventory_items_category", "inventory_items", ["category"]
    )

    # ---------------------------------------------------------------------- #
    # 16. inventory_transactions
    # ---------------------------------------------------------------------- #
    op.create_table(
        "inventory_transactions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("inventory_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity_change", sa.Numeric(12, 3), nullable=False),
        sa.Column(
            "transaction_type",
            sa.Enum(
                "received",
                "used",
                "adjusted",
                "returned",
                name="transaction_type",
            ),
            nullable=False,
        ),
        sa.Column(
            "reference_work_order_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("work_orders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "performed_by",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_inventory_transactions_tenant_id",
        "inventory_transactions",
        ["tenant_id"],
    )
    op.create_index(
        "idx_inventory_transactions_item_id",
        "inventory_transactions",
        ["item_id"],
    )

    # ---------------------------------------------------------------------- #
    # 17. invoices
    # ---------------------------------------------------------------------- #
    op.create_table(
        "invoices",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("invoice_number", sa.String(50), nullable=False),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("clients.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "sent",
                "viewed",
                "partial",
                "paid",
                "overdue",
                "void",
                name="invoice_status",
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "issue_date", sa.TIMESTAMP(timezone=True), nullable=False
        ),
        sa.Column(
            "due_date", sa.TIMESTAMP(timezone=True), nullable=False
        ),
        sa.Column(
            "subtotal",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "tax_rate",
            sa.Numeric(6, 4),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "tax_amount",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "discount_amount",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "total",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("terms", sa.Text, nullable=True),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("paid_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "tenant_id",
            "invoice_number",
            name="uq_invoices_tenant_number",
        ),
    )
    op.create_index("idx_invoices_tenant_id", "invoices", ["tenant_id"])
    op.create_index("idx_invoices_client_id", "invoices", ["client_id"])
    op.create_index("idx_invoices_status", "invoices", ["status"])

    # ---------------------------------------------------------------------- #
    # 18. invoice_line_items
    # ---------------------------------------------------------------------- #
    op.create_table(
        "invoice_line_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "work_order_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("work_orders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column(
            "quantity",
            sa.Numeric(10, 3),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "unit_price",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "line_total",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "sort_order",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_invoice_line_items_invoice_id",
        "invoice_line_items",
        ["invoice_id"],
    )
    op.create_index(
        "idx_invoice_line_items_tenant_id",
        "invoice_line_items",
        ["tenant_id"],
    )

    # ---------------------------------------------------------------------- #
    # 19. payments
    # ---------------------------------------------------------------------- #
    op.create_table(
        "payments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "payment_method",
            sa.Enum(
                "check", "ach", "card", "cash", "other",
                name="payment_method",
            ),
            nullable=False,
            server_default="other",
        ),
        sa.Column("reference_number", sa.String(150), nullable=True),
        sa.Column(
            "payment_date", sa.TIMESTAMP(timezone=True), nullable=False
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "recorded_by",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("idx_payments_tenant_id", "payments", ["tenant_id"])
    op.create_index("idx_payments_invoice_id", "payments", ["invoice_id"])

    # ---------------------------------------------------------------------- #
    # 20. audit_logs
    # ---------------------------------------------------------------------- #
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(36), nullable=True),
        sa.Column(
            "old_values",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "new_values",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("idx_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("idx_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("idx_audit_logs_action", "audit_logs", ["action"])
    op.create_index(
        "ix_audit_logs_tenant_resource_date",
        "audit_logs",
        ["tenant_id", "resource_type", "created_at"],
    )

    # ---------------------------------------------------------------------- #
    # Query-performance indexes (added last, after all tables exist)
    # ---------------------------------------------------------------------- #
    op.create_index(
        "idx_clients_tenant_active",
        "clients",
        ["tenant_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_work_orders_tenant_status",
        "work_orders",
        ["tenant_id", "status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_work_orders_crew_date",
        "work_orders",
        ["crew_id", "scheduled_date"],
    )
    op.create_index(
        "idx_work_orders_location",
        "work_orders",
        ["location_id", "scheduled_date"],
    )
    op.create_index(
        "idx_check_ins_user_date",
        "work_order_check_ins",
        ["user_id", "check_in_time"],
    )
    op.create_index(
        "idx_invoices_client_status",
        "invoices",
        ["tenant_id", "client_id", "status"],
    )
    op.create_index(
        "idx_audit_logs_tenant_date",
        "audit_logs",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    # Drop performance indexes first
    op.drop_index("idx_audit_logs_tenant_date", table_name="audit_logs")
    op.drop_index("idx_invoices_client_status", table_name="invoices")
    op.drop_index("idx_check_ins_user_date", table_name="work_order_check_ins")
    op.drop_index("idx_work_orders_location", table_name="work_orders")
    op.drop_index("idx_work_orders_crew_date", table_name="work_orders")
    op.drop_index("idx_work_orders_tenant_status", table_name="work_orders")
    op.drop_index("idx_clients_tenant_active", table_name="clients")

    # Drop tables in reverse dependency order
    op.drop_table("audit_logs")
    op.drop_table("payments")
    op.drop_table("invoice_line_items")
    op.drop_table("invoices")
    op.drop_table("inventory_transactions")
    op.drop_table("inventory_items")
    op.drop_table("equipment")
    op.drop_table("work_order_check_ins")
    op.drop_table("work_order_attachments")
    op.drop_table("work_order_tasks")
    op.drop_table("work_orders")
    op.drop_table("crew_members")
    op.drop_table("crews")
    op.drop_table("locations")
    op.drop_table("clients")
    op.drop_table("employee_profiles")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
    op.drop_table("tenants")
    op.drop_table("subscription_plans")

    # Drop custom enum types
    op.execute("DROP TYPE IF EXISTS payment_method")
    op.execute("DROP TYPE IF EXISTS invoice_status")
    op.execute("DROP TYPE IF EXISTS transaction_type")
    op.execute("DROP TYPE IF EXISTS equipment_status")
    op.execute("DROP TYPE IF EXISTS check_in_method")
    op.execute("DROP TYPE IF EXISTS attachment_type")
    op.execute("DROP TYPE IF EXISTS task_status")
    op.execute("DROP TYPE IF EXISTS work_type")
    op.execute("DROP TYPE IF EXISTS priority")
    op.execute("DROP TYPE IF EXISTS work_order_status")
    op.execute("DROP TYPE IF EXISTS crew_member_role")
    op.execute("DROP TYPE IF EXISTS industry_type")
    op.execute("DROP TYPE IF EXISTS user_role")
    op.execute("DROP TYPE IF EXISTS subscription_status")
