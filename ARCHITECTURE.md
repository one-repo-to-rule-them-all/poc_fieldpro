# FieldPro — Multi-Tenant Field Service Management Platform
## System Architecture & Engineering Reference

**Version:** 1.0  
**Stack:** FastAPI · PostgreSQL · Next.js 14 · Docker  
**Audience:** Engineering team — senior level assumed throughout  

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Recommended Tech Stack](#2-recommended-tech-stack)
3. [Database Schema Design](#3-database-schema-design)
4. [Multi-Tenant Strategy](#4-multi-tenant-strategy)
5. [RBAC Design](#5-rbac-design)
6. [API Design](#6-api-design)
7. [Frontend Architecture](#7-frontend-architecture)
8. [Folder / Project Structure](#8-folder--project-structure)
9. [MVP Feature Scope](#9-mvp-feature-scope)
10. [Future Scalability Roadmap](#10-future-scalability-roadmap)
11. [Deployment Architecture](#11-deployment-architecture)
12. [Security Considerations](#12-security-considerations)
13. [CI/CD Workflow](#13-cicd-workflow)
14. [Analytics & KPIs](#14-analytics--kpis)
15. [Wireframe / Page Map](#15-wireframe--page-map)
16. [Example Workflows](#16-example-workflows)
17. [Development Phases](#17-development-phases)
18. [Testing Strategy](#18-testing-strategy)
19. [Monitoring & Logging](#19-monitoring--logging)
20. [Cost-Conscious MVP Recommendations](#20-cost-conscious-mvp-recommendations)

---

## 1. System Architecture Overview

### High-Level Topology

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLIENTS                                     │
│  Browser (Admin/Manager)    Mobile Browser (Field Worker)            │
└─────────────────┬───────────────────────────┬───────────────────────┘
                  │                           │
                  ▼                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       CDN / Edge (Cloudflare)                        │
│           Static assets · TLS termination · DDoS protection         │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                  ┌───────────────┴──────────────────┐
                  ▼                                  ▼
      ┌─────────────────────┐           ┌──────────────────────┐
      │   Next.js Frontend  │           │    nginx / Traefik    │
      │   (SSR + API Routes)│           │   (Reverse Proxy)     │
      │   Port 3000         │           │   Port 80/443         │
      └─────────────────────┘           └──────────┬───────────┘
                                                   │
                                        ┌──────────▼──────────┐
                                        │   FastAPI Backend    │
                                        │   (Async Python)     │
                                        │   Port 8000          │
                                        │   /api/v1/*          │
                                        └──────┬───────────────┘
                                               │
                    ┌──────────────────────────┼──────────────────────┐
                    ▼                          ▼                      ▼
        ┌───────────────────┐     ┌───────────────────┐  ┌──────────────────┐
        │   PostgreSQL 16   │     │    Redis 7         │  │  Object Storage  │
        │   Primary DB      │     │    Cache · Queue   │  │  S3 / R2         │
        │   Port 5432       │     │    Sessions        │  │  (Photo uploads) │
        └───────────────────┘     └───────────────────┘  └──────────────────┘
                    │
        ┌───────────▼──────────┐
        │  ARQ Worker Process  │
        │  (Background Jobs)   │
        │  Scheduled tasks     │
        │  Email/SMS dispatch  │
        └──────────────────────┘
```

### Architectural Principles

**Clean Architecture layers** — no circular imports between layers. Dependencies flow inward: `API → Service → Repository → Model`. The domain (models + schemas) is independent of transport.

**Shared-schema multi-tenancy** — single database, `tenant_id` UUID on every tenant-scoped table. Enforced at the repository layer via a mandatory filter, not trusted from the request. Every query that touches tenant data goes through a `TenantRepository` base that injects the filter automatically.

**Async-first backend** — FastAPI with `asyncpg` driver. All I/O paths are `async/await`. CPU-bound work (PDF generation, report aggregation) is offloaded to ARQ workers.

**API-first design** — the frontend is a consumer of the same API that third parties or mobile apps will use. No server-side rendering shortcuts that bypass the API layer.

**Stateless API servers** — JWT auth, no server-side session state. Scales horizontally with no session affinity requirement. Redis used for token blacklisting (logout/revocation), rate limiting, and job queues only.

---

## 2. Recommended Tech Stack

### Backend

| Component | Choice | Reasoning |
|-----------|--------|-----------|
| Framework | FastAPI 0.115+ | Async-native, Pydantic v2 validation, auto-generated OpenAPI docs, dependency injection built-in |
| Language | Python 3.12 | Type hints everywhere, excellent async story, strong data ecosystem (useful when analytics layer matures) |
| ORM | SQLAlchemy 2.0 (async) | Mature, full-featured, explicit query control, works with Alembic, avoids N+1 with selectinload |
| DB Driver | asyncpg | Fastest PostgreSQL async driver; paired with SQLAlchemy async session |
| Migrations | Alembic | Battle-tested, auto-generates from models, downgrade support |
| Background Jobs | ARQ (async Redis queue) | Lightweight, async-native, simpler than Celery for the MVP scale; upgrade path to Celery exists |
| Caching | Redis 7 | Sorted sets for leaderboards/analytics, Pub/Sub for real-time events later, TTL-based token blacklist |
| Password Hashing | bcrypt via passlib | Industry standard, intentionally slow, supported everywhere |
| JWT | python-jose or PyJWT | Access token (15 min) + refresh token (7 days) pattern |
| Email | FastMail + Jinja2 templates | async-native SMTP wrapper; swap to SendGrid/SES in prod |
| File Storage | boto3 (S3-compatible) | Works with AWS S3, Cloudflare R2, MinIO — same API |
| Structured Logging | structlog | JSON output, request context propagation, integrates with Sentry |
| HTTP Client | httpx | Async-capable, used for outbound webhooks and integration calls |

**Why not NestJS?** The platform will eventually need data science tooling (ML scheduling, anomaly detection, predictive analytics). Python keeps that in-language. FastAPI's Pydantic v2 schema validation is on par with NestJS's class-validator. Tradeoff: loses end-to-end TypeScript uniformity, gains better data ecosystem.

### Frontend

| Component | Choice | Reasoning |
|-----------|--------|-----------|
| Framework | Next.js 14 (App Router) | RSC reduces client bundle, server actions for forms, native streaming, Vercel-deployable |
| Language | TypeScript 5 | Non-negotiable for a production codebase |
| Styling | Tailwind CSS 3 | Mobile-first, utility-first, no runtime CSS-in-JS overhead |
| UI Components | shadcn/ui | Un-opinionated, copy-owned components, accessible, Radix primitives |
| Data Fetching | TanStack Query v5 | Server state management, optimistic updates, background refetch, offline detection |
| Global State | Zustand | Lightweight; auth context, UI state (sidebar, modals). No Redux complexity at MVP |
| Forms | React Hook Form + Zod | Type-safe form validation, minimal re-renders |
| Tables | TanStack Table v8 | Headless, works with Tailwind, virtualization support for large datasets |
| Calendar/Scheduling | react-big-calendar | Resource views for crew scheduling |
| Charts | Recharts | Good defaults, composable, React-native |
| Maps | Mapbox GL JS or Leaflet | Geofencing and location views |
| Icons | Lucide React | Tree-shakeable, consistent style |

### Database

| Component | Choice |
|-----------|--------|
| Primary DB | PostgreSQL 16 |
| Extensions | `uuid-ossp` (UUID generation), `pg_trgm` (fuzzy search), `postgis` (future geofencing) |
| Connection Pooling | PgBouncer (transaction mode) in production |

### Infrastructure

| Component | Choice | Notes |
|-----------|--------|-------|
| Containers | Docker + Docker Compose | Dev and prod parity |
| Orchestration | Fly.io (MVP) → Kubernetes (scale) | Fly.io is significantly cheaper and simpler than EKS for solo/small team MVPs |
| Object Storage | Cloudflare R2 | S3-compatible, zero egress fees — crucial cost saving |
| CDN | Cloudflare | Free tier covers MVP |
| CI/CD | GitHub Actions | Tight GitHub integration, generous free tier |
| Secrets | GitHub Secrets → fly secrets | Rotate via CI; Vault for enterprise later |
| Monitoring | Sentry (errors) + Grafana Cloud free tier | Free tiers cover MVP volume |

---

## 3. Database Schema Design

### Conventions

- All PKs are `UUID` (gen_random_uuid()), not auto-increment integers. Avoids sequential guessing and works naturally with distributed systems.
- All tables have `created_at TIMESTAMPTZ DEFAULT now()` and `updated_at TIMESTAMPTZ`.
- Soft deletes via `deleted_at TIMESTAMPTZ NULL` on all user-facing entities. Hard deletes only for system tables.
- `tenant_id UUID NOT NULL REFERENCES tenants(id)` on every tenant-scoped table.
- Audit fields: `created_by UUID`, `updated_by UUID` referencing users.
- All `status` and `type` columns use `VARCHAR` with a check constraint (not ENUMs, which require migration to alter).

### Core Schema

```sql
-- ============================================================
-- PLATFORM LEVEL (no tenant_id)
-- ============================================================

CREATE TABLE subscription_plans (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          VARCHAR(100) NOT NULL,          -- 'Starter', 'Professional', 'Enterprise'
    slug          VARCHAR(50) UNIQUE NOT NULL,
    price_monthly NUMERIC(10,2) NOT NULL,
    max_employees INT,                             -- NULL = unlimited
    max_clients   INT,
    max_locations INT,
    features      JSONB DEFAULT '{}',             -- feature flags per plan
    is_active     BOOLEAN DEFAULT true,
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE tenants (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name             VARCHAR(200) NOT NULL,
    slug             VARCHAR(100) UNIQUE NOT NULL,  -- used in subdomain: {slug}.fieldpro.app
    plan_id          UUID REFERENCES subscription_plans(id),
    industry         VARCHAR(100),                  -- 'janitorial', 'landscaping', 'hvac', etc.
    logo_url         TEXT,
    primary_color    VARCHAR(7),                    -- hex, for white-labeling
    timezone         VARCHAR(50) DEFAULT 'America/Chicago',
    subscription_status VARCHAR(20) DEFAULT 'trial' -- 'trial','active','past_due','cancelled'
        CHECK (subscription_status IN ('trial','active','past_due','suspended','cancelled')),
    trial_ends_at    TIMESTAMPTZ,
    billing_email    VARCHAR(255),
    stripe_customer_id VARCHAR(100),               -- Stripe integration hook
    settings         JSONB DEFAULT '{}',            -- tenant-level config overrides
    deleted_at       TIMESTAMPTZ,
    created_at       TIMESTAMPTZ DEFAULT now(),
    updated_at       TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- USERS & AUTH
-- ============================================================

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,  -- NULL for platform admins
    email           VARCHAR(255) NOT NULL,
    email_verified  BOOLEAN DEFAULT false,
    hashed_password VARCHAR(255) NOT NULL,
    first_name      VARCHAR(100) NOT NULL,
    last_name       VARCHAR(100) NOT NULL,
    phone           VARCHAR(30),
    avatar_url      TEXT,
    role            VARCHAR(50) NOT NULL
        CHECK (role IN ('platform_admin','tenant_admin','manager','employee','client_user')),
    is_active       BOOLEAN DEFAULT true,
    mfa_secret      VARCHAR(100),                  -- TOTP secret, encrypted at rest
    mfa_enabled     BOOLEAN DEFAULT false,
    last_login_at   TIMESTAMPTZ,
    password_reset_token VARCHAR(255),
    password_reset_expires_at TIMESTAMPTZ,
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (tenant_id, email)
);

CREATE TABLE refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) NOT NULL UNIQUE,       -- hashed, not stored in plain text
    device_info JSONB,                              -- user-agent, IP for session management
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- CLIENTS & LOCATIONS
-- ============================================================

CREATE TABLE clients (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            VARCHAR(200) NOT NULL,
    client_type     VARCHAR(50) DEFAULT 'commercial'
        CHECK (client_type IN ('commercial','government','residential','medical')),
    email           VARCHAR(255),
    phone           VARCHAR(30),
    billing_address JSONB,                          -- {street, city, state, zip, country}
    billing_terms   VARCHAR(50) DEFAULT 'net30'
        CHECK (billing_terms IN ('immediate','net15','net30','net45','net60')),
    tax_id          VARCHAR(50),
    notes           TEXT,
    is_active       BOOLEAN DEFAULT true,
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    created_by      UUID REFERENCES users(id)
);

CREATE TABLE service_locations (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    client_id         UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name              VARCHAR(200) NOT NULL,         -- 'Southside Park', 'City Hall - Floor 2'
    address           JSONB NOT NULL,
    latitude          NUMERIC(10, 7),
    longitude         NUMERIC(10, 7),
    geofence_radius_m INT DEFAULT 100,               -- meters, for GPS check-in validation
    access_instructions TEXT,
    special_requirements TEXT,
    service_days      VARCHAR(20)[],                 -- ['mon','tue','wed','thu','fri']
    is_active         BOOLEAN DEFAULT true,
    deleted_at        TIMESTAMPTZ,
    created_at        TIMESTAMPTZ DEFAULT now(),
    updated_at        TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- EMPLOYEES & CREWS
-- ============================================================

CREATE TABLE employee_profiles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    employee_number VARCHAR(50),
    hire_date       DATE,
    hourly_rate     NUMERIC(8,2),
    certifications  JSONB DEFAULT '[]',              -- [{name, issued_at, expires_at, document_url}]
    emergency_contact JSONB,                         -- {name, phone, relationship}
    notes           TEXT,
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (tenant_id, user_id)
);

CREATE TABLE crews (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,
    lead_id     UUID REFERENCES users(id),           -- crew lead (employee)
    is_active   BOOLEAN DEFAULT true,
    deleted_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE crew_members (
    crew_id    UUID NOT NULL REFERENCES crews(id) ON DELETE CASCADE,
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at  TIMESTAMPTZ DEFAULT now(),
    left_at    TIMESTAMPTZ,
    PRIMARY KEY (crew_id, user_id)
);

-- ============================================================
-- WORK ORDERS
-- ============================================================

CREATE TABLE work_orders (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    client_id           UUID NOT NULL REFERENCES clients(id),
    location_id         UUID NOT NULL REFERENCES service_locations(id),
    crew_id             UUID REFERENCES crews(id),
    title               VARCHAR(200) NOT NULL,
    description         TEXT,
    status              VARCHAR(30) NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('draft','scheduled','assigned','in_progress','on_hold','completed','cancelled','requires_review')),
    priority            VARCHAR(20) DEFAULT 'normal'
        CHECK (priority IN ('low','normal','high','urgent')),
    work_type           VARCHAR(50) DEFAULT 'recurring'
        CHECK (work_type IN ('recurring','one_time','emergency','inspection')),
    scheduled_start     TIMESTAMPTZ,
    scheduled_end       TIMESTAMPTZ,
    actual_start        TIMESTAMPTZ,
    actual_end          TIMESTAMPTZ,
    estimated_hours     NUMERIC(5,2),
    actual_hours        NUMERIC(5,2),               -- computed from check-in records
    sla_deadline        TIMESTAMPTZ,
    sla_met             BOOLEAN,
    recurrence_rule     JSONB,                       -- iCal RRULE as JSON: {freq, interval, byday, until}
    parent_work_order_id UUID REFERENCES work_orders(id),  -- for generated recurrences
    invoice_id          UUID,                        -- set when billed (FK added after invoices table)
    internal_notes      TEXT,
    completion_notes    TEXT,
    requires_approval   BOOLEAN DEFAULT false,
    approved_by         UUID REFERENCES users(id),
    approved_at         TIMESTAMPTZ,
    deleted_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now(),
    created_by          UUID REFERENCES users(id)
);

CREATE TABLE work_order_tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_order_id   UUID NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    title           VARCHAR(200) NOT NULL,
    description     TEXT,
    sort_order      INT DEFAULT 0,
    is_required     BOOLEAN DEFAULT true,
    completed       BOOLEAN DEFAULT false,
    completed_by    UUID REFERENCES users(id),
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE work_order_attachments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_order_id   UUID NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    uploaded_by     UUID NOT NULL REFERENCES users(id),
    file_url        TEXT NOT NULL,
    file_key        TEXT NOT NULL,                   -- S3/R2 object key for deletion
    file_name       VARCHAR(255),
    file_size_bytes INT,
    mime_type       VARCHAR(100),
    attachment_type VARCHAR(30) DEFAULT 'photo'
        CHECK (attachment_type IN ('photo','before_photo','after_photo','document','signature')),
    caption         TEXT,
    latitude        NUMERIC(10,7),
    longitude       NUMERIC(10,7),
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- CHECK-INS / TIME TRACKING
-- ============================================================

CREATE TABLE location_check_ins (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    work_order_id   UUID REFERENCES work_orders(id),
    user_id         UUID NOT NULL REFERENCES users(id),
    location_id     UUID NOT NULL REFERENCES service_locations(id),
    checked_in_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    checked_out_at  TIMESTAMPTZ,
    check_in_lat    NUMERIC(10,7),
    check_in_lng    NUMERIC(10,7),
    check_out_lat   NUMERIC(10,7),
    check_out_lng   NUMERIC(10,7),
    within_geofence BOOLEAN,                         -- was check-in within allowed radius?
    duration_minutes INT GENERATED ALWAYS AS (
        EXTRACT(EPOCH FROM (checked_out_at - checked_in_at)) / 60
    ) STORED,
    notes           TEXT
);

-- ============================================================
-- INVENTORY & EQUIPMENT
-- ============================================================

CREATE TABLE equipment (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            VARCHAR(200) NOT NULL,
    serial_number   VARCHAR(100),
    assigned_crew_id UUID REFERENCES crews(id),
    purchase_date   DATE,
    purchase_cost   NUMERIC(10,2),
    condition       VARCHAR(20) DEFAULT 'good'
        CHECK (condition IN ('new','good','fair','poor','out_of_service')),
    next_service_date DATE,
    notes           TEXT,
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE inventory_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            VARCHAR(200) NOT NULL,
    sku             VARCHAR(100),
    unit            VARCHAR(30) DEFAULT 'each',      -- 'each', 'gallon', 'lb', 'box'
    quantity_on_hand NUMERIC(10,2) DEFAULT 0,
    reorder_threshold NUMERIC(10,2),
    unit_cost       NUMERIC(8,2),
    assigned_crew_id UUID REFERENCES crews(id),
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE inventory_transactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    item_id         UUID NOT NULL REFERENCES inventory_items(id),
    work_order_id   UUID REFERENCES work_orders(id),
    transaction_type VARCHAR(20) NOT NULL
        CHECK (transaction_type IN ('restock','usage','adjustment','transfer','loss')),
    quantity_delta  NUMERIC(10,2) NOT NULL,          -- positive=in, negative=out
    notes           TEXT,
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- BILLING & INVOICES
-- ============================================================

CREATE TABLE invoices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    client_id       UUID NOT NULL REFERENCES clients(id),
    invoice_number  VARCHAR(50) NOT NULL,             -- human-readable: INV-2025-0042
    status          VARCHAR(30) DEFAULT 'draft'
        CHECK (status IN ('draft','sent','viewed','partial','paid','overdue','void','refunded')),
    issue_date      DATE NOT NULL DEFAULT CURRENT_DATE,
    due_date        DATE NOT NULL,
    subtotal        NUMERIC(12,2) NOT NULL DEFAULT 0,
    tax_rate        NUMERIC(5,4) DEFAULT 0,           -- e.g. 0.0825 for 8.25%
    tax_amount      NUMERIC(12,2) DEFAULT 0,
    discount_amount NUMERIC(12,2) DEFAULT 0,
    total_amount    NUMERIC(12,2) NOT NULL DEFAULT 0,
    amount_paid     NUMERIC(12,2) DEFAULT 0,
    balance_due     NUMERIC(12,2) GENERATED ALWAYS AS (total_amount - amount_paid) STORED,
    notes           TEXT,
    pdf_url         TEXT,
    pdf_generated_at TIMESTAMPTZ,
    sent_at         TIMESTAMPTZ,
    paid_at         TIMESTAMPTZ,
    void_reason     TEXT,
    quickbooks_id   VARCHAR(100),                    -- QuickBooks sync hook
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    created_by      UUID REFERENCES users(id)
);

CREATE TABLE invoice_line_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id      UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    work_order_id   UUID REFERENCES work_orders(id),  -- links back to work order
    description     VARCHAR(500) NOT NULL,
    quantity        NUMERIC(10,2) NOT NULL DEFAULT 1,
    unit_price      NUMERIC(10,2) NOT NULL,
    line_total      NUMERIC(12,2) GENERATED ALWAYS AS (quantity * unit_price) STORED,
    sort_order      INT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE payments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    invoice_id      UUID NOT NULL REFERENCES invoices(id),
    amount          NUMERIC(12,2) NOT NULL,
    payment_date    DATE NOT NULL,
    payment_method  VARCHAR(30)
        CHECK (payment_method IN ('check','ach','credit_card','cash','wire','other')),
    reference_number VARCHAR(100),
    notes           TEXT,
    recorded_by     UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- AUDIT LOG
-- ============================================================

CREATE TABLE audit_logs (
    id           BIGSERIAL PRIMARY KEY,             -- use BIGSERIAL, not UUID — high volume append-only
    tenant_id    UUID REFERENCES tenants(id),
    user_id      UUID REFERENCES users(id),
    action       VARCHAR(100) NOT NULL,             -- 'work_order.status_changed', 'invoice.sent'
    resource_type VARCHAR(100),                     -- 'work_order', 'invoice', 'user'
    resource_id  UUID,
    old_values   JSONB,
    new_values   JSONB,
    ip_address   INET,
    user_agent   TEXT,
    created_at   TIMESTAMPTZ DEFAULT now()
);

-- Back-fill FK on work_orders
ALTER TABLE work_orders ADD CONSTRAINT fk_invoice FOREIGN KEY (invoice_id) REFERENCES invoices(id);
```

### Indexing Strategy

```sql
-- Tenant isolation — every query starts with tenant_id
CREATE INDEX idx_clients_tenant          ON clients(tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_locations_tenant        ON service_locations(tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_locations_client        ON service_locations(client_id);
CREATE INDEX idx_work_orders_tenant      ON work_orders(tenant_id, status) WHERE deleted_at IS NULL;
CREATE INDEX idx_work_orders_location    ON work_orders(location_id, scheduled_start);
CREATE INDEX idx_work_orders_crew        ON work_orders(crew_id, scheduled_start);
CREATE INDEX idx_check_ins_user          ON location_check_ins(user_id, checked_in_at);
CREATE INDEX idx_check_ins_location      ON location_check_ins(location_id, checked_in_at);
CREATE INDEX idx_invoices_client         ON invoices(tenant_id, client_id, status);
CREATE INDEX idx_invoices_due            ON invoices(tenant_id, due_date) WHERE status NOT IN ('paid','void');
CREATE INDEX idx_audit_logs_tenant       ON audit_logs(tenant_id, created_at DESC);
CREATE INDEX idx_audit_logs_resource     ON audit_logs(resource_type, resource_id);
-- Full-text search
CREATE INDEX idx_clients_name_trgm       ON clients USING gin(name gin_trgm_ops);
CREATE INDEX idx_locations_name_trgm     ON service_locations USING gin(name gin_trgm_ops);
CREATE INDEX idx_work_orders_title_trgm  ON work_orders USING gin(title gin_trgm_ops);
-- Geospatial (phase 2 — after PostGIS)
-- CREATE INDEX idx_locations_geo ON service_locations USING gist(ST_MakePoint(longitude, latitude));
```

---

## 4. Multi-Tenant Strategy

### Approach: Shared Schema, Tenant-Isolated Rows

**Decision:** Shared database, shared schema, `tenant_id` on every table.

| Approach | Pros | Cons |
|----------|------|------|
| Separate DB per tenant | Strongest isolation, easy per-tenant backup | Expensive, complex connection management |
| Separate schema per tenant | Good isolation, Postgres native | Schema migrations multiply, connection pool pressure |
| **Shared schema (chosen)** | Lowest cost, simplest ops, scales to 1000s of tenants | Must enforce isolation in code — not free |

The risk of the shared-schema approach is a data leak between tenants if a query omits `tenant_id`. This is mitigated architecturally, not just by convention.

### Enforcement Architecture

```python
# repositories/base.py — every repository inherits this
class TenantRepository(Generic[ModelT]):
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id          # injected from validated JWT claim

    def _tenant_filter(self) -> ColumnElement:
        return self.model.tenant_id == self.tenant_id

    async def get_by_id(self, id: UUID) -> ModelT | None:
        result = await self.session.execute(
            select(self.model)
            .where(self.model.id == id)
            .where(self._tenant_filter())    # ALWAYS applied, not optional
            .where(self.model.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()
```

The `tenant_id` is extracted from the JWT by a FastAPI dependency and is **never** read from the request body. A user cannot pass a different `tenant_id` in their request payload and access another tenant's data.

```python
# api/deps.py
async def get_current_tenant(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    payload = decode_access_token(token)      # raises 401 if invalid
    tenant_id = UUID(payload["tenant_id"])    # extracted from signed JWT
    tenant = await TenantRepository(db, tenant_id).get_by_id(tenant_id)
    if not tenant or tenant.subscription_status == "suspended":
        raise HTTPException(status_code=403, detail="Tenant access denied")
    return tenant
```

### Tenant Routing

Tenants are identified by subdomain: `acme.fieldpro.app`. The Next.js middleware extracts the subdomain and passes it as a request header. The backend reads from the JWT — the subdomain is only used for UI routing, never for authorization decisions.

### Subscription Enforcement

```python
# services/tenant_service.py
async def check_plan_limits(tenant: Tenant, resource: str) -> None:
    plan = tenant.plan
    counts = await get_resource_counts(tenant.id)
    limits = {
        "employees": plan.max_employees,
        "clients": plan.max_clients,
        "locations": plan.max_locations,
    }
    if limits[resource] and counts[resource] >= limits[resource]:
        raise PlanLimitExceeded(f"Plan limit reached for {resource}. Upgrade to add more.")
```

---

## 5. RBAC Design

### Role Hierarchy

```
platform_admin          (cross-tenant — god mode)
└── tenant_admin        (owns their tenant)
    └── manager         (operational control within tenant)
        └── employee    (field worker — limited own-data access)
client_user             (external — read-only portal)
```

### Permission Matrix

| Permission | platform_admin | tenant_admin | manager | employee | client_user |
|-----------|:-:|:-:|:-:|:-:|:-:|
| Manage tenants | ✓ | — | — | — | — |
| View platform analytics | ✓ | — | — | — | — |
| Manage billing/subscription | ✓ | ✓ | — | — | — |
| Manage users (CRUD) | ✓ | ✓ | — | — | — |
| Manage clients | ✓ | ✓ | ✓ | — | — |
| Manage locations | ✓ | ✓ | ✓ | — | — |
| Create/edit work orders | ✓ | ✓ | ✓ | — | — |
| Assign crews | ✓ | ✓ | ✓ | — | — |
| View assigned work orders | ✓ | ✓ | ✓ | own | — |
| Check in/out | — | — | — | ✓ | — |
| Complete tasks / upload photos | — | — | ✓ | ✓ | — |
| Approve completed work orders | ✓ | ✓ | ✓ | — | — |
| Manage invoices | ✓ | ✓ | — | — | — |
| View invoices (own client) | — | — | — | — | ✓ |
| View service reports (own client) | — | ✓ | ✓ | — | ✓ |
| Manage inventory/equipment | ✓ | ✓ | ✓ | — | — |
| View KPI dashboard | ✓ | ✓ | ✓ | — | — |

### Implementation

```python
# core/permissions.py
from enum import Enum
from functools import wraps

class Permission(str, Enum):
    # Work orders
    WORK_ORDER_CREATE = "work_order:create"
    WORK_ORDER_READ   = "work_order:read"
    WORK_ORDER_UPDATE = "work_order:update"
    WORK_ORDER_DELETE = "work_order:delete"
    WORK_ORDER_ASSIGN = "work_order:assign"
    WORK_ORDER_APPROVE = "work_order:approve"
    WORK_ORDER_CHECKIN = "work_order:checkin"
    # Clients
    CLIENT_CREATE = "client:create"
    CLIENT_READ   = "client:read"
    CLIENT_UPDATE = "client:update"
    CLIENT_DELETE = "client:delete"
    # Invoices
    INVOICE_CREATE = "invoice:create"
    INVOICE_READ   = "invoice:read"
    INVOICE_SEND   = "invoice:send"
    # Users
    USER_MANAGE = "user:manage"
    # Analytics
    ANALYTICS_VIEW = "analytics:view"

ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "platform_admin": set(Permission),  # all permissions
    "tenant_admin": {
        Permission.WORK_ORDER_CREATE, Permission.WORK_ORDER_READ,
        Permission.WORK_ORDER_UPDATE, Permission.WORK_ORDER_DELETE,
        Permission.WORK_ORDER_ASSIGN, Permission.WORK_ORDER_APPROVE,
        Permission.CLIENT_CREATE, Permission.CLIENT_READ,
        Permission.CLIENT_UPDATE, Permission.CLIENT_DELETE,
        Permission.INVOICE_CREATE, Permission.INVOICE_READ, Permission.INVOICE_SEND,
        Permission.USER_MANAGE, Permission.ANALYTICS_VIEW,
    },
    "manager": {
        Permission.WORK_ORDER_CREATE, Permission.WORK_ORDER_READ,
        Permission.WORK_ORDER_UPDATE, Permission.WORK_ORDER_ASSIGN,
        Permission.WORK_ORDER_APPROVE,
        Permission.CLIENT_READ, Permission.CLIENT_UPDATE,
        Permission.ANALYTICS_VIEW,
    },
    "employee": {
        Permission.WORK_ORDER_READ, Permission.WORK_ORDER_CHECKIN,
    },
    "client_user": {
        Permission.WORK_ORDER_READ,  # filtered to own client only
        Permission.INVOICE_READ,     # filtered to own client only
    },
}

# FastAPI dependency
def require_permission(permission: Permission):
    async def dependency(current_user: User = Depends(get_current_user)):
        if permission not in ROLE_PERMISSIONS.get(current_user.role, set()):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return Depends(dependency)

# Usage in router
@router.post("/work-orders")
async def create_work_order(
    data: WorkOrderCreate,
    user: User = require_permission(Permission.WORK_ORDER_CREATE),
):
    ...
```

---

## 6. API Design

### Base URL & Versioning

```
https://api.fieldpro.app/api/v1/
```

All routes are versioned in the URL path. Version negotiation is not done via headers — URL versioning is explicit and cacheable. Breaking changes create a new `/v2/` router; old versions are maintained for 12 months.

### Auth Endpoints

```
POST   /api/v1/auth/register        Register a new tenant + admin user
POST   /api/v1/auth/login           Returns { access_token, refresh_token, user }
POST   /api/v1/auth/refresh         Exchange refresh token for new access token
POST   /api/v1/auth/logout          Revoke refresh token (adds to Redis blacklist)
POST   /api/v1/auth/password-reset  Request reset email
POST   /api/v1/auth/password-reset/confirm
GET    /api/v1/auth/me              Current user profile
PATCH  /api/v1/auth/me              Update own profile
POST   /api/v1/auth/mfa/setup       Returns TOTP QR code
POST   /api/v1/auth/mfa/verify      Verify TOTP and enable MFA
```

### Resource Endpoints

```
# Tenants (platform_admin only)
GET    /api/v1/tenants
POST   /api/v1/tenants
GET    /api/v1/tenants/{id}
PATCH  /api/v1/tenants/{id}
DELETE /api/v1/tenants/{id}

# Users
GET    /api/v1/users                 List users in tenant
POST   /api/v1/users                 Create user (tenant_admin only)
GET    /api/v1/users/{id}
PATCH  /api/v1/users/{id}
DELETE /api/v1/users/{id}

# Clients
GET    /api/v1/clients               ?search=city&page=1&limit=25
POST   /api/v1/clients
GET    /api/v1/clients/{id}
PATCH  /api/v1/clients/{id}
DELETE /api/v1/clients/{id}          (soft delete)
GET    /api/v1/clients/{id}/locations
GET    /api/v1/clients/{id}/invoices
GET    /api/v1/clients/{id}/work-orders

# Locations
GET    /api/v1/locations             ?client_id=&is_active=true
POST   /api/v1/locations
GET    /api/v1/locations/{id}
PATCH  /api/v1/locations/{id}
DELETE /api/v1/locations/{id}

# Work Orders
GET    /api/v1/work-orders           ?status=&crew_id=&location_id=&date_from=&date_to=
POST   /api/v1/work-orders
GET    /api/v1/work-orders/{id}
PATCH  /api/v1/work-orders/{id}
DELETE /api/v1/work-orders/{id}
POST   /api/v1/work-orders/{id}/assign
POST   /api/v1/work-orders/{id}/start
POST   /api/v1/work-orders/{id}/complete
POST   /api/v1/work-orders/{id}/approve
POST   /api/v1/work-orders/{id}/attachments
GET    /api/v1/work-orders/{id}/tasks
PATCH  /api/v1/work-orders/{id}/tasks/{task_id}

# Check-ins
POST   /api/v1/check-ins             { work_order_id, location_id, latitude, longitude }
PATCH  /api/v1/check-ins/{id}/checkout
GET    /api/v1/check-ins             ?user_id=&date=&location_id=

# Crews
GET    /api/v1/crews
POST   /api/v1/crews
GET    /api/v1/crews/{id}
PATCH  /api/v1/crews/{id}
POST   /api/v1/crews/{id}/members
DELETE /api/v1/crews/{id}/members/{user_id}

# Invoices
GET    /api/v1/invoices              ?client_id=&status=&date_from=&date_to=
POST   /api/v1/invoices
GET    /api/v1/invoices/{id}
PATCH  /api/v1/invoices/{id}
POST   /api/v1/invoices/{id}/send
POST   /api/v1/invoices/{id}/record-payment
GET    /api/v1/invoices/{id}/pdf     (triggers PDF generation if stale)
POST   /api/v1/invoices/from-work-orders  { work_order_ids: [...] }

# Analytics
GET    /api/v1/analytics/dashboard        ?date_from=&date_to=
GET    /api/v1/analytics/completion-rate  ?crew_id=&location_id=
GET    /api/v1/analytics/labor            ?date_from=&date_to=
GET    /api/v1/analytics/revenue          ?group_by=month|client|crew

# Health
GET    /health                        { status: "ok", db: "ok", redis: "ok", version: "1.0.0" }
```

### Response Envelope

```json
// Success (list)
{
  "data": [...],
  "meta": {
    "total": 150,
    "page": 1,
    "limit": 25,
    "pages": 6
  }
}

// Success (single)
{
  "data": { "id": "...", ... }
}

// Error
{
  "error": {
    "code": "WORK_ORDER_NOT_FOUND",
    "message": "Work order not found or access denied",
    "details": null,
    "request_id": "req_abc123"
  }
}
```

### Example: Create Work Order

**Request:**
```http
POST /api/v1/work-orders
Authorization: Bearer eyJ...
Content-Type: application/json

{
  "title": "Weekly restroom cleaning — Southside Park",
  "client_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "location_id": "7c4d8b0e-1234-4567-b89a-0def01234567",
  "crew_id": "9b1e2f3a-4567-4890-b1c2-3d4e5f6a7b8c",
  "work_type": "recurring",
  "priority": "normal",
  "scheduled_start": "2025-05-12T08:00:00-05:00",
  "scheduled_end": "2025-05-12T11:00:00-05:00",
  "estimated_hours": 3.0,
  "recurrence_rule": {
    "freq": "WEEKLY",
    "interval": 1,
    "byday": ["MO", "WE", "FR"]
  },
  "tasks": [
    { "title": "Clean all restrooms", "sort_order": 1 },
    { "title": "Empty trash receptacles", "sort_order": 2 },
    { "title": "Inspect facilities — log issues", "sort_order": 3 }
  ]
}
```

**Response (201):**
```json
{
  "data": {
    "id": "c3d4e5f6-...",
    "title": "Weekly restroom cleaning — Southside Park",
    "status": "assigned",
    "crew": { "id": "...", "name": "Crew Alpha" },
    "location": { "id": "...", "name": "Southside Park", "address": {...} },
    "scheduled_start": "2025-05-12T08:00:00-05:00",
    "tasks": [
      { "id": "...", "title": "Clean all restrooms", "completed": false },
      ...
    ],
    "created_at": "2025-05-08T14:23:00Z"
  }
}
```

---

## 7. Frontend Architecture

### App Router Structure

Next.js 14 App Router with route groups for role-based layouts:

```
app/
├── (auth)/               # Login / register — no sidebar
│   ├── layout.tsx
│   ├── login/page.tsx    → /login
│   └── register/page.tsx → /register
├── (dashboard)/          # Main app — tenant users (sidebar + navbar)
│   ├── layout.tsx        # Auth guard + sidebar + navbar shell
│   └── dashboard/        # All sub-routes live one level deeper so URLs are /dashboard/*
│       ├── page.tsx                  → /dashboard
│       ├── work-orders/page.tsx      → /dashboard/work-orders
│       ├── work-orders/[id]/page.tsx → /dashboard/work-orders/:id
│       ├── schedule/page.tsx         → /dashboard/schedule
│       ├── clients/page.tsx          → /dashboard/clients
│       ├── crews/page.tsx            → /dashboard/crews
│       ├── invoices/page.tsx         → /dashboard/invoices
│       ├── invoices/[id]/page.tsx    → /dashboard/invoices/:id
│       ├── locations/page.tsx        → /dashboard/locations
│       ├── analytics/page.tsx        → /dashboard/analytics
│       └── settings/page.tsx         → /dashboard/settings
```

> **Field worker UX:** The native FieldPro mobile app is the canonical field worker experience (consumes the same backend API via `?client=mobile`). Web-based field work is served through `/dashboard/check-in` inside the standard dashboard chrome with an employee-restricted sidebar.

> **Route group note:** `(dashboard)` and `(auth)` are Next.js route groups — the parenthesized folder name is not part of the URL. The extra `dashboard/` directory inside `(dashboard)/` is what makes all management URLs resolve to `/dashboard/*` rather than the root.

> **PostCSS requirement:** `postcss.config.js` must be present in `frontend/` root for Tailwind CSS to compile. This file is baked into the Docker image (not volume-mounted), so any change to it requires `docker compose build frontend`.

### State Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Zustand Store                        │
│  authStore:  { user, tenant, tokens, isAuthenticated }  │
│  uiStore:    { sidebarOpen, activeFilters, modals }     │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                  TanStack Query                          │
│  Server state: work orders, clients, crews, analytics   │
│  Handles: caching, background refetch, optimistic UI    │
│  Keys: ['work-orders', filters], ['clients', page]      │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    API Client (lib/api.ts)               │
│  Axios instance with:                                    │
│  - Auth header injection from Zustand                    │
│  - 401 interceptor → refresh token → retry              │
│  - Error normalization                                   │
│  - Request/response logging in dev                       │
└─────────────────────────────────────────────────────────┘
```

### Auth Flow

```
1. User visits protected route
2. middleware.ts checks for access_token in cookie
3. If missing/expired → redirect to /login
4. Login form → POST /api/v1/auth/login
5. Store tokens: access in memory (Zustand), refresh in httpOnly cookie
6. All API requests include Bearer token from Zustand
7. 401 response → axios interceptor reads refresh cookie → POST /auth/refresh
8. New tokens set → original request retried
9. Logout → POST /auth/logout → clear Zustand + cookie
```

**Security note:** Access token in memory (not localStorage, not sessionStorage) prevents XSS token theft. Refresh token in httpOnly cookie prevents JS access.

### Mobile Field Worker UX

The native **FieldPro mobile app** is the canonical field worker experience and consumes the same backend API (mobile auth path via `?client=mobile`, shipped in PR #69). It provides:
- Native bottom navigation, large tap targets
- Camera + Geolocation + offline sync at the platform level

For the web, field workers land on `/dashboard/check-in` inside the standard dashboard chrome with an employee-restricted sidebar (Work Orders + Check In only). Web is the fallback path for kiosks, troubleshooting, or before the native app is installed — not a parallel UX surface.

---

## 8. Folder / Project Structure

```
fieldpro/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml
│   │   └── deploy.yml
│   └── pull_request_template.md
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app factory
│   │   ├── core/
│   │   │   ├── config.py              # Pydantic Settings (reads .env)
│   │   │   ├── database.py            # Async engine + session factory
│   │   │   ├── security.py            # JWT encode/decode, bcrypt
│   │   │   ├── dependencies.py        # FastAPI Depends: db, current_user, tenant
│   │   │   ├── exceptions.py          # Custom exception classes
│   │   │   └── logging.py             # structlog setup
│   │   ├── models/
│   │   │   ├── base.py                # DeclarativeBase, TimestampMixin, SoftDeleteMixin
│   │   │   ├── tenant.py
│   │   │   ├── user.py
│   │   │   ├── client.py
│   │   │   ├── location.py
│   │   │   ├── crew.py
│   │   │   ├── work_order.py
│   │   │   ├── inventory.py
│   │   │   ├── invoice.py
│   │   │   └── audit_log.py
│   │   ├── schemas/                   # Pydantic v2 schemas (DTOs)
│   │   │   ├── auth.py                # LoginRequest, TokenResponse, etc.
│   │   │   ├── common.py              # PaginatedResponse, ErrorResponse
│   │   │   ├── tenant.py
│   │   │   ├── user.py
│   │   │   ├── client.py
│   │   │   ├── location.py
│   │   │   ├── crew.py
│   │   │   ├── work_order.py
│   │   │   ├── inventory.py
│   │   │   └── invoice.py
│   │   ├── repositories/              # Data access layer
│   │   │   ├── base.py                # TenantRepository[T] generic base
│   │   │   ├── tenant_repo.py
│   │   │   ├── user_repo.py
│   │   │   ├── client_repo.py
│   │   │   ├── location_repo.py
│   │   │   ├── crew_repo.py
│   │   │   ├── work_order_repo.py
│   │   │   ├── invoice_repo.py
│   │   │   └── analytics_repo.py
│   │   ├── services/                  # Business logic
│   │   │   ├── auth_service.py
│   │   │   ├── tenant_service.py
│   │   │   ├── user_service.py
│   │   │   ├── client_service.py
│   │   │   ├── work_order_service.py
│   │   │   ├── schedule_service.py    # Recurrence expansion
│   │   │   ├── invoice_service.py     # Invoice generation from work orders
│   │   │   ├── pdf_service.py         # PDF generation (WeasyPrint)
│   │   │   ├── notification_service.py
│   │   │   ├── storage_service.py     # S3/R2 file operations
│   │   │   └── analytics_service.py
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── router.py          # Aggregates all v1 routers
│   │   │   │   ├── auth.py
│   │   │   │   ├── tenants.py
│   │   │   │   ├── users.py
│   │   │   │   ├── clients.py
│   │   │   │   ├── locations.py
│   │   │   │   ├── crews.py
│   │   │   │   ├── work_orders.py
│   │   │   │   ├── check_ins.py
│   │   │   │   ├── inventory.py
│   │   │   │   ├── invoices.py
│   │   │   │   └── analytics.py
│   │   │   └── middleware.py          # Request ID, audit logging, tenant header
│   │   └── workers/
│   │       ├── tasks.py               # ARQ task definitions
│   │       └── main.py                # ARQ worker entrypoint
│   ├── migrations/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       ├── 001_initial_schema.py
│   │       └── 002_add_geofence.py
│   ├── tests/
│   │   ├── conftest.py                # Fixtures: test DB, test client, seed data
│   │   ├── unit/
│   │   │   ├── test_auth_service.py
│   │   │   ├── test_work_order_service.py
│   │   │   └── test_invoice_service.py
│   │   ├── integration/
│   │   │   ├── test_auth_api.py
│   │   │   ├── test_work_orders_api.py
│   │   │   └── test_invoices_api.py
│   │   └── e2e/                       # Playwright or httpx-based flows
│   ├── scripts/
│   │   └── seed_data.py
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── alembic.ini
│
├── frontend/
│   ├── src/
│   │   ├── app/                       # Next.js App Router (see §7)
│   │   ├── components/
│   │   │   ├── ui/                    # shadcn/ui component copies
│   │   │   ├── layout/
│   │   │   │   ├── sidebar.tsx
│   │   │   │   ├── navbar.tsx
│   │   │   │   └── mobile-nav.tsx
│   │   │   ├── work-orders/
│   │   │   │   ├── work-order-table.tsx
│   │   │   │   ├── work-order-form.tsx
│   │   │   │   ├── status-badge.tsx
│   │   │   │   └── task-checklist.tsx
│   │   │   ├── clients/
│   │   │   ├── invoices/
│   │   │   ├── schedule/
│   │   │   │   └── dispatch-calendar.tsx
│   │   │   └── analytics/
│   │   │       ├── kpi-card.tsx
│   │   │       └── completion-chart.tsx
│   │   ├── lib/
│   │   │   ├── api.ts                 # Axios instance + type-safe fetchers
│   │   │   ├── auth.ts                # Token helpers
│   │   │   └── utils.ts               # cn(), formatDate(), etc.
│   │   ├── hooks/
│   │   │   ├── use-work-orders.ts
│   │   │   ├── use-clients.ts
│   │   │   ├── use-analytics.ts
│   │   │   └── use-geolocation.ts
│   │   ├── stores/
│   │   │   ├── auth-store.ts
│   │   │   └── ui-store.ts
│   │   └── types/
│   │       ├── api.ts                 # Mirror of backend Pydantic schemas
│   │       └── index.ts
│   ├── public/
│   ├── Dockerfile
│   ├── next.config.ts
│   ├── middleware.ts                  # Subdomain routing + auth guard
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── package.json
│
├── nginx/
│   └── nginx.conf
├── scripts/
│   ├── setup.sh
│   └── seed_data.py
├── docker-compose.yml
├── docker-compose.override.yml
├── docker-compose.prod.yml
├── .env.example
├── .gitignore
├── .ruff.toml
├── pyproject.toml
└── README.md
```

---

## 9. MVP Feature Scope

**6–8 week solo sprint target.** Cut ruthlessly. Ship the core loop that makes the platform usable for the janitorial use case.

### In MVP

| Feature | Why |
|---------|-----|
| Tenant registration + JWT auth | Table stakes |
| User management (5 roles) | Core to everything |
| Client CRUD | Foundation of the data model |
| Location CRUD | Foundation of the data model |
| Work order CRUD (one-time + recurring) | Core product value |
| Task checklists on work orders | Differentiator from simple todo apps |
| Crew assignment | Core dispatch workflow |
| Employee GPS check-in / check-out | Proves the field workflow |
| Photo/note attachments on work orders | Evidence of work done |
| Basic invoice generation from work orders | Revenue-enabling |
| Work order status board (dashboard) | Manager operational view |
| Mobile-responsive field worker view | Required for real-world use |
| Audit logging | Compliance and debugging |
| Basic KPI dashboard (completion rate, active orders) | Business owner visibility |

### Explicitly Out of MVP (Phase 2+)

Drag-and-drop scheduling calendar, route optimization, recurring invoice billing, automated SMS/email notifications, PDF invoice export, MFA, geofencing enforcement, QuickBooks integration, real-time updates (WebSocket), offline mode, white-label branding.

**Tradeoff rationale:** Each deferred feature is additive. The MVP loop — create client → create location → create work order → assign crew → employee checks in and completes tasks → manager sees completion — is complete and commercially demoable without them.

---

## 10. Future Scalability Roadmap

### Phase 2 (Months 3–5)

- Recurring invoice engine with auto-generation
- Drag-and-drop dispatch calendar (react-big-calendar resource view)
- Email notifications (FastMail → SendGrid)
- SMS notifications (Twilio)
- PDF invoice export (WeasyPrint or Puppeteer)
- Geofencing enforcement on check-in
- MFA (TOTP)
- Client portal (read-only view for client_user role)
- Equipment maintenance logs

### Phase 3 (Months 6–9)

- Route optimization (Google Maps Directions API or OSRM self-hosted)
- QuickBooks Online integration (OAuth2 + Webhook sync)
- Mobile apps (React Native + Expo, sharing API and some business logic)
- Offline sync engine (IndexedDB + background sync API)
- Real-time updates (WebSockets via FastAPI or Server-Sent Events)
- Advanced analytics: labor utilization heatmaps, SLA trend analysis
- White-label tenant branding (per-tenant color scheme, logo, subdomain)

### Phase 4 (Months 10–15)

- AI scheduling optimization (constraint solver + ML demand forecasting)
- Predictive inventory management (reorder alerts based on usage patterns)
- Voice-enabled field reporting (Whisper API transcription)
- IoT sensor integration (asset tracking tags)
- GIS mapping with PostGIS (route visualization, territory management)
- Real-time fleet tracking
- Marketplace for service templates (share task checklist templates across tenants)

### Scaling Architecture Triggers

| Metric | Action |
|--------|--------|
| > 100 tenants | Add PgBouncer connection pooler |
| > 500 req/s | Horizontal scale API (Fly.io machines or K8s) |
| > 1M work orders | Partition `work_orders` and `audit_logs` by `tenant_id` hash |
| Analytics queries > 5s | Materialize KPI aggregates in a dedicated `analytics_snapshots` table; update via ARQ job hourly |
| > 50GB object storage | Evaluate R2 vs S3 pricing, add image compression pipeline |
| Enterprise requirements | Migrate to separate schema per tenant for regulatory isolation |

---

## 11. Deployment Architecture

### MVP: Fly.io (Cost-Optimal)

```
┌──────────────────────────────────────────────────────────┐
│                   Cloudflare (DNS + CDN)                  │
│    fieldpro.app → frontend     api.fieldpro.app → backend │
└─────────────────────┬───────────────────┬────────────────┘
                      │                   │
            ┌─────────▼──────┐  ┌─────────▼──────────┐
            │  Fly.io App    │  │  Fly.io App         │
            │  fieldpro-web  │  │  fieldpro-api        │
            │  Next.js       │  │  FastAPI             │
            │  1x shared CPU │  │  1x shared CPU       │
            │  512MB RAM     │  │  512MB RAM           │
            └────────────────┘  └──────────┬───────────┘
                                           │
                              ┌────────────┼────────────┐
                              ▼            ▼            ▼
                    ┌──────────────┐ ┌──────────┐ ┌─────────────┐
                    │ Fly Postgres │ │ Upstash  │ │ Cloudflare  │
                    │ (managed PG) │ │ Redis    │ │ R2 Storage  │
                    │ 1x shared   │ │ (free)   │ │ (free egress│
                    └──────────────┘ └──────────┘ └─────────────┘
```

**Estimated monthly cost (MVP, < 50 tenants):**
- Fly.io (2 machines): ~$14/mo
- Fly.io Postgres (shared): ~$7/mo
- Upstash Redis (free tier): $0
- Cloudflare R2 (< 10GB): $0
- **Total: ~$21/mo**

### Production Scale: Kubernetes (EKS / GKE)

```
┌────────────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                               │
│                                                                    │
│  ┌──────────────────────┐   ┌──────────────────────┐             │
│  │   Backend Deployment │   │  Worker Deployment   │             │
│  │   replicas: 3        │   │  replicas: 2         │             │
│  │   HPA: CPU > 70%     │   │  (ARQ workers)       │             │
│  └──────────────────────┘   └──────────────────────┘             │
│                                                                    │
│  ┌──────────────────────┐   ┌──────────────────────┐             │
│  │  Frontend Deployment │   │  PgBouncer Deployment│             │
│  │  replicas: 2         │   │  (connection pooler) │             │
│  └──────────────────────┘   └──────────────────────┘             │
└────────────────────────────────────────────────────────────────────┘
         │                            │
         ▼                            ▼
┌─────────────────┐          ┌────────────────┐
│ AWS RDS PG 16   │          │ ElastiCache    │
│ Multi-AZ        │          │ Redis Cluster  │
│ Read replica    │          └────────────────┘
└─────────────────┘
```

---

## 12. Security Considerations

### Authentication

- **Access tokens:** JWT, HS256, 15-minute TTL. Signed with `SECRET_KEY` env var (min 32 bytes, cryptographically random).
- **Refresh tokens:** Opaque (random bytes), stored hashed in `refresh_tokens` table. 7-day TTL. Single-use: each refresh issues new pair and revokes old.
- **Token storage:** Access token in-memory (Zustand); refresh token in `httpOnly; Secure; SameSite=Strict` cookie.
- **Logout:** Adds token JTI to Redis blacklist (TTL = remaining token lifetime). All endpoints check blacklist.
- **MFA:** TOTP (RFC 6238) via `pyotp`. Secret stored AES-256 encrypted in DB. Recovery codes hashed.

### API Security

- **CORS:** Explicit allowlist of origins (no `*` in production).
- **Rate limiting:** Nginx-level (10 req/s general, 3 req/s auth) + Redis token bucket in FastAPI for granular limits.
- **Input validation:** All inputs validated by Pydantic v2 with strict mode. No raw SQL (SQLAlchemy ORM only). SQLAlchemy parameterized queries prevent SQL injection.
- **File uploads:** Type validation (magic bytes, not just extension), size limit (10MB per file), MIME whitelist (image/jpeg, image/png, image/webp, application/pdf). Files stored in R2 with randomized keys — never predictable URLs.
- **API versioning:** Breaking changes require version increment, preventing silent contract violations.
- **Request IDs:** Every request tagged with UUID. Logged and returned in `X-Request-ID` header for tracing.

### Data Security

- **Passwords:** bcrypt with cost factor 12 (auto-rehash on login if factor changes).
- **Tenant isolation:** Enforced at repository layer, tested with cross-tenant access tests in CI.
- **PII at rest:** Sensitive fields (MFA secrets, payment references) encrypted using `cryptography` library (Fernet/AES-256-GCM). DB-level encryption via Fly.io Postgres encrypted volumes.
- **Audit trail:** Immutable `audit_logs` table. All mutations logged with old/new values, user, IP.
- **Soft deletes:** Records never permanently deleted unless legally required. Supports recovery and audit.

### Infrastructure Security

- **Secrets:** Never in code or committed to Git. Managed via `fly secrets set` or GitHub Secrets → injected at runtime.
- **TLS:** Enforced at Cloudflare and nginx. HSTS with `includeSubDomains`.
- **Dependency scanning:** Dependabot + `pip-audit` in CI.
- **Docker images:** Non-root user, read-only filesystem where possible, minimal base image (python:3.12-slim).
- **SSRF:** `httpx` configured with timeout and allowlisted domains for any outbound calls.

---

## 13. CI/CD Workflow

```
Developer pushes feature branch
         │
         ▼
┌─────────────────────────────────────┐
│ GitHub Actions — CI (on PR)         │
│                                     │
│  ┌───────────────────────────────┐  │
│  │ backend-lint                  │  │
│  │  ruff check + mypy            │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │ backend-test                  │  │
│  │  postgres + redis services    │  │
│  │  alembic upgrade head         │  │
│  │  pytest --cov ≥ 80%           │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │ frontend-lint                 │  │
│  │  eslint + tsc --noEmit        │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │ frontend-test                 │  │
│  │  vitest --coverage            │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
         │  All pass
         ▼
    PR approved + merged to develop
         │
         ▼
┌─────────────────────────────────────┐
│ GitHub Actions — Deploy Staging     │
│  Build Docker images (buildx cache) │
│  Push to ghcr.io                    │
│  fly deploy → fieldpro-api-staging  │
│  fly deploy → fieldpro-web-staging  │
│  Run smoke tests (curl /health)     │
│  Run Playwright e2e suite           │
└─────────────────────────────────────┘
         │  Pass
         ▼
    Merge develop → main
         │
         ▼
┌─────────────────────────────────────┐
│ GitHub Actions — Deploy Production  │
│  (Requires manual approval gate)    │
│  fly deploy → fieldpro-api          │
│  fly deploy → fieldpro-web          │
│  fly postgres connect → migrate     │
│  Notify Slack/Discord on success    │
└─────────────────────────────────────┘
```

### Branch Strategy

```
main          ← production (protected, requires PR + CI green + 1 review)
develop       ← integration branch (auto-deploys to staging)
feature/*     ← developer work
hotfix/*      ← urgent prod fixes (merge to main + develop)
release/*     ← release prep (version bump, CHANGELOG)
```

### Migration Safety

Migrations run as part of the deploy process, before new app instances come up. This requires backward-compatible schema changes:

1. **Never drop a column in the same PR that removes code reading it** — two-step process
2. **Add columns as nullable first**, backfill, then add NOT NULL constraint
3. **Test migrations in staging with production data snapshot** (anonymized)

---

## 14. Analytics & KPIs

### Operational KPIs (Manager Dashboard)

| KPI | Definition | Target |
|-----|-----------|--------|
| Work Order Completion Rate | completed / (completed + overdue) | > 95% |
| On-Time Completion Rate | completed before scheduled_end / total | > 90% |
| SLA Compliance Rate | sla_met = true / total with SLA | > 98% |
| Average Actual vs Estimated Hours | actual_hours / estimated_hours | 0.9–1.1 |
| Open Issues Count | work orders in `requires_review` | → 0 |
| Active Check-ins | employees currently checked in | Live |

### Business KPIs (Owner Dashboard)

| KPI | Definition |
|-----|-----------|
| Monthly Recurring Revenue | sum(invoice totals) by month |
| Outstanding AR | sum(balance_due) where status in ('sent','overdue') |
| Revenue per Client | sum(invoice totals) grouped by client |
| Revenue per Crew | sum(invoice totals) linked to crew |
| Days Sales Outstanding (DSO) | avg days from invoice_sent to paid_at |
| Invoice Collection Rate | paid / (paid + overdue) |

### Workforce KPIs

| KPI | Definition |
|-----|-----------|
| Labor Utilization Rate | actual_hours_on_work_orders / total_hours_clocked |
| Crew Productivity Score | completed work orders per crew per week |
| Check-in Accuracy | within_geofence = true / total check-ins |
| Task Completion Rate | tasks completed / tasks assigned per work order |

### Analytics Implementation

```python
# repositories/analytics_repo.py (example query)
async def get_completion_rate(
    tenant_id: UUID,
    date_from: date,
    date_to: date,
    crew_id: UUID | None = None,
) -> dict:
    query = """
        SELECT
            COUNT(*) FILTER (WHERE status = 'completed') AS completed,
            COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled,
            COUNT(*) FILTER (
                WHERE status = 'completed'
                AND actual_end <= scheduled_end
            ) AS on_time,
            COUNT(*) AS total,
            ROUND(
                COUNT(*) FILTER (WHERE status = 'completed')::NUMERIC
                / NULLIF(COUNT(*), 0) * 100, 1
            ) AS completion_rate_pct
        FROM work_orders
        WHERE tenant_id = :tenant_id
          AND scheduled_start BETWEEN :date_from AND :date_to
          AND deleted_at IS NULL
          AND (:crew_id IS NULL OR crew_id = :crew_id)
    """
    result = await self.session.execute(
        text(query),
        {"tenant_id": tenant_id, "date_from": date_from, "date_to": date_to, "crew_id": crew_id}
    )
    return result.mappings().one()
```

**Performance:** For real-time dashboards, pre-aggregate KPIs into a `kpi_snapshots` table via an ARQ job that runs hourly. Dashboard API reads from snapshots (millisecond response) not live aggregate queries.

---

## 15. Wireframe / Page Map

```
PUBLIC
├── / — Marketing landing page
└── /login — Auth forms

DASHBOARD (sidebar nav)
├── /dashboard — KPI summary cards + today's work orders + active check-ins
│
├── /clients — Searchable table + New Client button
│   └── /clients/[id] — Profile, contacts, billing, locations list, work order history
│
├── /locations — All locations with client, address, last service date
│   └── /locations/[id] — Location detail, schedule, attached work orders
│
├── /work-orders — Filterable table (status, crew, date, client)
│   └── /work-orders/[id] — Full detail: tasks, attachments, check-ins, timeline, approval
│
├── /schedule — Weekly/monthly calendar (resource view by crew), drag to assign
│
├── /crew — Crew list + members + today's assignments
│   └── /crew/[id] — Members, equipment, history, performance metrics
│
├── /invoices — List with status filter (draft/sent/overdue/paid)
│   └── /invoices/[id] — Line items, status actions (Send, Record Payment), PDF download
│
├── /analytics — Date-filtered charts: completion rate, revenue, labor, SLA compliance
│
└── /settings
    ├── /settings — Company info, timezone, logo
    ├── /settings/users — User list, invite, role management
    └── /settings/billing — Plan, usage, subscription actions

FIELD WORKER (web fallback — native mobile app is canonical)
└── /dashboard/check-in — Active + scheduled jobs; tap a WO to check in, complete tasks, check out

PLATFORM ADMIN (/admin/*)
├── /admin/tenants — All tenant organizations
└── /admin/analytics — Platform-wide metrics
```

---

## 16. Example Workflows

### Workflow A: Janitorial Job Cycle (Happy Path)

```
1. Business Owner (tenant_admin)
   → POST /clients                     { name: "City of Corpus Christi", ... }
   → POST /locations                   { client_id: ..., name: "Southside Park", ... }
   → POST /work-orders                 { location_id, crew_id, recurrence_rule: {freq:WEEKLY,...} }

2. System (ARQ worker — every night at midnight)
   → Expand recurrence rule
   → Generate work_order instances for next 30 days
   → Status: 'scheduled'

3. Manager
   → PATCH /work-orders/{id}/assign    { crew_id: "crew-alpha" }
   → Status: 'assigned'

4. Employee (mobile browser, 8:00 AM)
   → POST /check-ins                   { work_order_id, latitude, longitude }
   → System validates: within_geofence = true
   → Status: 'in_progress'

5. Employee
   → PATCH /work-orders/{id}/tasks/{task_id}  { completed: true }  (×3 tasks)
   → POST /work-orders/{id}/attachments       (before/after photos)

6. Employee (10:45 AM)
   → PATCH /check-ins/{id}/checkout    { latitude, longitude }
   → duration_minutes = 165

7. Manager (dashboard notification)
   → Reviews photos and task completions
   → POST /work-orders/{id}/approve
   → Status: 'completed'

8. Business Owner (end of month)
   → POST /invoices/from-work-orders   { work_order_ids: [...completed ids...] }
   → System creates invoice with line items per work order
   → POST /invoices/{id}/send
   → Client receives invoice email with PDF attachment
```

### Workflow B: Emergency Work Order

```
1. Manager receives urgent call
   → POST /work-orders { work_type: 'emergency', priority: 'urgent', ... }
   → POST /work-orders/{id}/assign { crew_id: 'nearest-available' }

2. System: notifies crew lead via SMS (ARQ job)

3. Employee checks in immediately
   → Completes work
   → Uploads evidence photos

4. Manager reviews, approves, invoices at premium rate
```

### Workflow C: Invoice-to-Payment

```
Business Owner:
1. Selects completed work orders for billing period
2. POST /invoices/from-work-orders → draft invoice generated
3. Reviews line items, adjusts any pricing
4. POST /invoices/{id}/send → PDF generated, email dispatched
5. Client views invoice in client portal
6. Client pays by check
7. POST /invoices/{id}/record-payment { amount, payment_method: 'check', reference }
8. Invoice status → 'paid', balance_due → 0
```

---

## 17. Development Phases

### Phase 1 — MVP (Weeks 1–8)

**Week 1–2: Foundation**
- Docker Compose environment running (Postgres + Redis + backend + frontend)
- Alembic migration with full schema
- FastAPI app skeleton: health check, exception handlers, logging, CORS
- JWT auth: register, login, refresh, logout
- User model + basic RBAC dependency

**Week 3–4: Core Domain**
- Tenant management (CRUD + subscription plan)
- Client + Location CRUD (with full service layer + repo pattern)
- Employee profiles + Crew management
- Multi-tenant isolation tests proving cross-tenant access fails

**Week 5–6: Work Orders**
- Work order CRUD + task checklists
- Status state machine (draft → scheduled → assigned → in_progress → completed)
- GPS check-in / check-out endpoint
- Attachment upload (R2 storage)
- Recurrence rule expansion (ARQ worker)

**Week 7: Dashboard + Mobile**
- Next.js frontend: auth flow, dashboard layout, sidebar
- Work order list + detail pages
- Mobile field worker view (my orders, check-in, task complete, photo upload)

**Week 8: Invoicing + QA**
- Invoice generation from work orders
- Basic KPI dashboard (5 key metrics)
- Manual QA pass with seed data
- CI pipeline green: lint + test + staging deploy

### Phase 2 (Months 3–4)

- Drag-and-drop scheduling calendar
- PDF invoice export
- Email/SMS notifications
- Client portal
- Geofencing enforcement
- Recurring invoice automation

### Phase 3 (Months 5–8)

- Route optimization
- QuickBooks integration
- React Native mobile apps
- Real-time WebSocket updates
- Advanced analytics + KPI snapshots

---

## 18. Testing Strategy

### Pyramid

```
               /\
              /  \
             / E2E \          (Playwright — 10%)
            /--------\
           /Integration\      (pytest + httpx TestClient — 30%)
          /--------------\
         /  Unit Tests    \   (pytest — 60%)
        /------------------\
```

### Backend Unit Tests

Focus on service layer business logic. Repositories are mocked.

```python
# tests/unit/test_invoice_service.py
async def test_create_invoice_from_work_orders_sums_correctly():
    # Arrange
    work_orders = [
        FakeWorkOrder(estimated_hours=3.0, hourly_rate=45.0),
        FakeWorkOrder(estimated_hours=5.0, hourly_rate=45.0),
    ]
    service = InvoiceService(repo=MockInvoiceRepo(), ...)
    # Act
    invoice = await service.create_from_work_orders(work_orders, tax_rate=0.0825)
    # Assert
    assert invoice.subtotal == Decimal("360.00")   # 8h × $45
    assert invoice.tax_amount == Decimal("29.70")  # 8.25%
    assert invoice.total_amount == Decimal("389.70")
```

### Backend Integration Tests

Real test DB (Postgres in Docker or CI service). Tests full HTTP cycle through FastAPI TestClient.

```python
# tests/integration/test_work_orders_api.py
async def test_create_work_order_requires_auth(client: AsyncClient):
    response = await client.post("/api/v1/work-orders", json={...})
    assert response.status_code == 401

async def test_employee_cannot_create_work_order(
    client: AsyncClient, employee_token: str
):
    response = await client.post(
        "/api/v1/work-orders",
        json={...},
        headers={"Authorization": f"Bearer {employee_token}"}
    )
    assert response.status_code == 403

async def test_tenant_isolation(
    client: AsyncClient, tenant_a_token: str, tenant_b_work_order_id: UUID
):
    # Tenant A cannot access Tenant B's work order
    response = await client.get(
        f"/api/v1/work-orders/{tenant_b_work_order_id}",
        headers={"Authorization": f"Bearer {tenant_a_token}"}
    )
    assert response.status_code == 404  # Not 403 — don't reveal existence
```

**Tenant isolation tests** are required in CI — they specifically verify that cross-tenant data access returns 404 (not the data).

### Frontend Testing

- **Vitest + React Testing Library:** Component behavior (forms submit, tables render, status badges show correct color)
- **MSW (Mock Service Worker):** Intercept API calls in tests — no actual network
- **Playwright E2E:** Full flows in headless browser: login → create work order → assign crew → complete. Runs in CI on staging.

### Coverage Requirements

- Backend: 80% line coverage (enforced in CI via `--cov-fail-under=80`)
- Frontend: 70% (components + hooks)
- E2E: Critical paths (auth, create work order, invoice generation)

---

## 19. Monitoring & Logging

### Structured Logging (Backend)

```python
# core/logging.py
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.JSONRenderer(),       # JSON in production
    ],
)

# In every request (middleware):
structlog.contextvars.bind_contextvars(
    request_id=request.headers.get("X-Request-ID", str(uuid4())),
    tenant_id=str(tenant_id),
    user_id=str(user_id),
    path=request.url.path,
    method=request.method,
)
```

Every log line contains `request_id`, `tenant_id`, `user_id` — making cross-service correlation trivial.

### Error Tracking

- **Sentry SDK** — installed in both FastAPI and Next.js
- Alerts on: new error types, error rate spikes, P95 latency regressions
- PII scrubbing configured: strip email, password fields from Sentry payloads

### Metrics (Fly.io → Grafana Cloud)

| Metric | Alert Threshold |
|--------|----------------|
| API P99 latency | > 2000ms |
| API error rate (5xx) | > 1% over 5m |
| DB connection pool exhausted | > 80% pool used |
| Redis memory | > 80% |
| Failed login attempts | > 10/min per IP |
| ARQ queue depth | > 100 pending jobs |

### Health Check Endpoint

```python
@app.get("/health")
async def health(db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    db_ok = await check_db(db)
    redis_ok = await check_redis(redis)
    return {
        "status": "ok" if (db_ok and redis_ok) else "degraded",
        "db": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "error",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }
```

### Uptime Monitoring

- **Better Uptime** (free tier) pings `/health` every 60 seconds from 3 locations
- SMS alert to on-call number on consecutive failures

---

## 20. Cost-Conscious MVP Recommendations

### Where to Spend Nothing

| Cost | Free Alternative |
|------|-----------------|
| Redis hosting | Upstash free tier (10K daily commands) |
| Object storage egress | Cloudflare R2 ($0 egress vs S3's $0.09/GB) |
| CDN | Cloudflare free |
| Email (dev) | MailHog (local), Resend (3000/month free) |
| SMS | Skip for MVP — email only |
| Monitoring | Sentry free (5000 errors/month), Grafana Cloud free tier |
| Uptime monitoring | Better Uptime free (10 monitors) |
| CI/CD | GitHub Actions (2000 min/month free) |

### Optimize Fly.io Costs

- Use `auto_stop_machines = true` on staging — stops idle machines (saves ~$7/mo)
- Start with shared-cpu-1x@512MB — scales to dedicated when needed
- One Fly Postgres shared instance instead of managed RDS (~$65/mo savings)

### Development Shortcuts That Don't Create Tech Debt

- **shadcn/ui** — copy-owned components, no dependency lock-in, production quality immediately
- **Alembic autogenerate** — generate migrations from SQLAlchemy models, saves hours of hand-writing SQL
- **Pydantic Settings** — environment config validation catches misconfiguration at startup, not at runtime
- **ARQ over Celery** — half the dependencies, async-native, simpler worker process at MVP scale

### What to Avoid Early

- **WebSockets before you need them** — polling with TanStack Query (30-second interval) covers MVP real-time needs at zero infrastructure cost
- **Kubernetes before 10 tenants** — Fly.io handles this range better and cheaper
- **Microservices** — monolith is the right call until you have multiple teams or a clear hot-scaling domain; the modular folder structure enables extraction later without rewriting

### Total Estimated MVP Cost

| Service | Monthly |
|---------|---------|
| Fly.io (2 apps × $7) | $14 |
| Fly.io Postgres (shared) | $7 |
| Cloudflare (free) | $0 |
| Upstash Redis (free) | $0 |
| Resend email (free) | $0 |
| Sentry (free) | $0 |
| GitHub (free) | $0 |
| **Total** | **~$21/mo** |

At $21/month you can run a commercially demoable SaaS platform for your first paying customer.

---

*Document version 1.0 — generated May 2025*  
*Update this document when major architectural decisions change.*
