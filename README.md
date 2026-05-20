# FieldPro

**The operating system for field service businesses.**

A multi-tenant SaaS platform that runs the day-to-day for janitorial, landscaping, HVAC, and pest control companies — from the work order on a manager's screen to the GPS check-in in a worker's pocket to the invoice in a client's inbox.

> This repository is a **proof-of-concept showcase** of the MVP Phase 1 build. It is a curated snapshot, not the active development repo.

---

## The Problem

Field service operators run their business across five disconnected tools: a spreadsheet for the schedule, a group chat for dispatch, a paper checklist for the crew, a separate app for invoicing, and a folder somewhere for client records. Information falls through the cracks. Owners can't see what's happening in real time. Clients have no visibility. Compliance and audit trails are an afterthought.

FieldPro replaces all of it with one tenant-isolated platform — built for the way these businesses actually operate.

---

## MVP Phase 1 — What's Shipped Here

This proof-of-concept implements the **complete closed loop** a field service business needs to operate end-to-end without falling back to spreadsheets, paper, or group chat.

| # | Capability | What it gives the business |
|---|---|---|
| 1 | Multi-tenant secure account | Each business fully isolated; tenant admin signs in and only sees their own data |
| 2 | User & role management | Admin / Manager / Employee with RBAC at every route and UI surface |
| 3 | Client records | Who you serve, contacts, industry |
| 4 | Location records | Where the work happens; multiple per client |
| 5 | Crew management | Workers grouped into crews; crews assigned to jobs |
| 6 | Work order lifecycle | Create → schedule → assign → execute → complete, with state machine |
| 7 | Task checklists per work order | Granular step-by-step; toggle, skip with reason, undo |
| 8 | Calendar / schedule view | Today / week / month of scheduled work |
| 9 | GPS check-in / check-out | Workers check in at the site; arrival distance captured |
| 10 | Invoice generation | From completed work, line items, payment tracking, mark paid |
| 11 | Analytics dashboard | Revenue, work order trends, crew productivity in one view |

**Compliance-grade extras included in this snapshot:**

- **Audit logging** — Every mutation across 11 core models writes an immutable audit row with actor, timestamp, before/after diff, and request correlation ID. Built for SOC 2 readiness from day one.
- **Recurring work orders** — RRULE-based recurrence with `spawn_next_occurrence` on completion (built for cleaning/maintenance contracts).
- **Crew assignment UI** — Assign crews directly from the work order detail.

---

## Quick Start

### Prerequisites

| Tool | Min Version |
|------|-------------|
| Docker Desktop | 24.x |
| Node.js | 20 LTS *(for local frontend dev only)* |
| Python | 3.12 *(for local backend dev only)* |

### Run the full stack

```bash
git clone https://github.com/one-repo-to-rule-them-all/poc_fieldpro.git
cd poc_fieldpro

cp .env.example .env                                              # review and edit if needed
docker compose build                                              # build all images
docker compose up -d                                              # start all services
docker compose run --rm backend alembic upgrade head              # apply DB migrations
docker compose run --rm backend python scripts/seed_data.py       # seed demo data
```

> **Volume wipe recovery:** If you run `docker compose down --volumes`, re-run the migration and seed commands above.
>
> **Frontend build files baked into image:** `postcss.config.js`, `tailwind.config.ts`, `next.config.mjs`. After changing any of them, run `docker compose build frontend && docker compose up -d frontend`.

### Access URLs

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Swagger API docs | http://localhost:8000/docs |
| ReDoc API docs | http://localhost:8000/redoc |
| MailHog (email testing) | http://localhost:8025 |

### Demo Logins

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@demo.fieldpro.app` | `Admin123!` |
| Manager | `manager@demo.fieldpro.app` | `Manager123!` |
| Employee | `carlos@demo.fieldpro.app` | `Employee123!` |

---

## Architecture

| Layer | Stack |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS, Radix UI |
| State / data | React Query (server state), Zustand (UI state) |
| Backend API | FastAPI, Python 3.12, Pydantic v2, SQLAlchemy 2 (async) |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Auth | JWT (access + refresh tokens), bcrypt via passlib |
| File storage | S3-compatible (MinIO in dev) |
| Email | SMTP (MailHog in dev) |
| Deployment | Fly.io (Docker containers) |
| CI/CD | GitHub Actions |

**Production-grade from the start:** function-scoped test isolation, async SQLAlchemy throughout, response-model validation on every endpoint, type-checked frontend with React Query for cache coherence, request-correlated audit logs, no localhost shortcuts.

For full architectural detail, ADRs, and diagrams see [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Project Structure

```
poc_fieldpro/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # FastAPI routers — one file per resource
│   │   ├── core/            # Config, DB session, dependencies, security, audit
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   ├── services/        # Business logic
│   │   └── main.py          # FastAPI app factory
│   ├── migrations/          # Alembic migration scripts
│   └── tests/               # pytest test suite
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── (auth)/                  # /login, /register
│       │   └── (dashboard)/dashboard/   # All authenticated pages
│       ├── components/
│       ├── hooks/                   # React Query hooks
│       ├── lib/                     # API client, utils
│       └── stores/                  # Zustand stores
├── scripts/seed_data.py     # Demo data seed
├── docs/                    # Operational runbooks (audit query cookbook, etc.)
├── docker-compose.yml
└── .env.example
```

---

## Development

### Running services individually

```bash
# Backend (outside Docker)
cd backend
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (outside Docker)
cd frontend
npm install
npm run dev
```

### Database operations

```bash
# Apply pending migrations
docker compose run --rm backend alembic upgrade head

# Create a migration from model changes
docker compose run --rm backend alembic revision --autogenerate -m "add_column_to_work_orders"

# Roll back one migration
docker compose run --rm backend alembic downgrade -1
```

### Tests

```bash
# Backend pytest (run inside container for the test Postgres)
docker exec poc_fieldpro_backend pytest tests/

# Backend lint + type-check
docker compose run --rm backend ruff check app
docker compose run --rm backend mypy app --ignore-missing-imports

# Frontend lint + type-check
docker compose run --rm frontend npm run lint
docker compose run --rm frontend npm run type-check
```

100+ backend integration tests covering the full Phase 1 surface, including the 36-test audit-log verification matrix.

---

## Deployment

Reference Fly.io configuration is included for both services (`fly.toml` for backend, `fly.frontend.toml` for frontend). Update `image = "ghcr.io/YOUR_GITHUB_ORG/..."` to point at your own container registry before deploying.

For a full step-by-step plan to deploy this as a public demo (~1 working day, ~$1/month), see [`docs/planning/deployment-plan-a-showcase-demo.md`](docs/planning/deployment-plan-a-showcase-demo.md). For the production-first-customer playbook (6–10 weeks), see [`docs/planning/deployment-plan-b-production-onboarding.md`](docs/planning/deployment-plan-b-production-onboarding.md).

---

## What's Intentionally Not Included

This snapshot is **strictly the MVP Phase 1 closed loop.** The following are deferred to Phase 2+ and are not in this codebase:

- Real PDF invoice export (current snapshot uses `window.print()` as a stopgap)
- Email notifications (no background worker)
- Inventory & equipment management UI
- Client portal (read-only customer-facing view)
- MFA enrollment UI (TOTP backend is in place)
- Hard geofence enforcement (distance is computed but not enforced)
- Drag-and-drop dispatch
- Self-serve tenant signup + subscription tiers
- Mobile native apps, offline sync
- Route optimization, AI scheduling, QuickBooks/Xero integration

---

## Roadmap

Current focus and what's queued live in [`docs/planning/roadmap.md`](docs/planning/roadmap.md). The two detailed deployment plans (showcase demo and production onboarding) live alongside it in `docs/planning/`.

---

## License

[MIT](LICENSE) © 2026 Rodolfo Baez Jr.
