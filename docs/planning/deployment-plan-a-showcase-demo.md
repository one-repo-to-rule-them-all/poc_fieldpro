# Deployment Plan A — Public Showcase Demo

**Goal:** Live HTTPS URL anyone can visit; polished enough to show an investor or first-meeting prospect.
**Timebox:** ~1 working day end-to-end
**Monthly cost:** ~$1–15
**Source repo:** https://github.com/one-repo-to-rule-them-all/poc_fieldpro

---

## What "demo" means here

- Frozen seed data, reset nightly
- Anyone with the URL can log in with public demo credentials
- No real customer data, no real billing, no compliance burden
- Polished enough that the first 60 seconds feels intentional, not "this thing was a side project"

## What's intentionally NOT in this plan

(All of these live in Plan B.)

- Real domain email auth (SPF / DKIM / DMARC)
- Stripe billing
- Multi-region or active backup region
- DB backups beyond Fly's default snapshots
- Status page
- Real SLA
- Customer support inbox
- MFA, account deletion, GDPR data export

---

## Phase 0 — Prerequisites (15 min)

- [ ] **Fly.io account + payment method on file** (free tier covers a demo but a card is required)
- [ ] **`flyctl` installed** — Windows: `iwr https://fly.io/install.ps1 -useb | iex`
- [ ] **Local clone of this repo**
- [ ] **GitHub Container Registry access** — automatic via `gh` auth, but you may need to enable Packages on the repo
- [ ] **Sentry account** (optional, free tier — recommended)
- [ ] **Domain** (optional — `*.fly.dev` works; skip if budget-tight)

---

## Phase 1 — Provision backing services (30 min)

### 1.1 Fly Postgres

```bash
flyctl postgres create \
  --name fieldpro-poc-db \
  --region dfw \
  --vm-size shared-cpu-1x \
  --volume-size 1 \
  --initial-cluster-size 1
```

Output gives the connection string. **Save it.** Fly's free tier covers a single 256MB shared-cpu-1x with 1GB volume = $0/mo.

### 1.2 Redis via Upstash (Fly extension)

```bash
flyctl extensions create upstash-redis \
  --name fieldpro-poc-redis \
  --region us-east-1
```

Free tier covers 10k commands/day, more than enough for a demo. Upstash uses one DB; for ARQ you'll re-use the same URL but specify `/1` instead of `/0`.

### 1.3 Sentry (optional)

1. Create a new project at sentry.io (Python platform)
2. Copy the DSN — you'll set it as a Fly secret later

---

## Phase 2 — Deploy backend (45 min)

### 2.1 Launch the Fly app

```bash
flyctl launch --no-deploy --name fieldpro-poc-backend --region dfw
```

Reuses the existing `fly.toml`. Answer **No** to "create Postgres" and "create Redis" — already done in Phase 1.

### 2.2 Attach the Postgres cluster

```bash
flyctl postgres attach fieldpro-poc-db --app fieldpro-poc-backend
```

> ⚠️ **Gotcha:** Fly's attach gives a `postgres://` URL. The app expects `postgresql+asyncpg://`. After attach, manually edit the `DATABASE_URL` secret to add the `+asyncpg` prefix.

### 2.3 Set remaining secrets

```bash
flyctl secrets set --app fieldpro-poc-backend \
  SECRET_KEY="$(python -c "import secrets; print(secrets.token_hex(32))")" \
  REFRESH_SECRET_KEY="$(python -c "import secrets; print(secrets.token_hex(32))")" \
  REDIS_URL="<upstash-url>/0" \
  ARQ_REDIS_URL="<upstash-url>/1" \
  ENVIRONMENT=production \
  DEBUG=false \
  LOG_LEVEL=INFO \
  ALLOWED_HOSTS="fieldpro-poc-backend.fly.dev" \
  BACKEND_CORS_ORIGINS='["https://fieldpro-poc.fly.dev"]' \
  FRONTEND_URL="https://fieldpro-poc.fly.dev" \
  BACKEND_URL="https://fieldpro-poc-backend.fly.dev" \
  STORAGE_BACKEND=local \
  SMTP_HOST=localhost \
  SMTP_PORT=1025 \
  SENTRY_DSN="<sentry-dsn-or-leave-blank>" \
  SENTRY_ENVIRONMENT=production
```

### 2.4 Fix the fly.toml image reference

Current line 7 of `fly.toml`:
```
image = "ghcr.io/YOUR_GITHUB_ORG/fieldpro/backend:latest"
```

Either replace `YOUR_GITHUB_ORG` with `one-repo-to-rule-them-all` AND build/push the image to GHCR, OR delete this line and let Fly build from `backend/Dockerfile`.

**Recommended:** delete the line. Fly will build from the Dockerfile on each deploy — slower (3–5 min) but no GHCR setup needed.

### 2.5 First deploy

```bash
flyctl deploy --app fieldpro-poc-backend
```

Watch the output — backend should come up healthy in 2–3 min after build completes.

### 2.6 Run migrations + seed

```bash
flyctl ssh console --app fieldpro-poc-backend -C "alembic upgrade head"
flyctl ssh console --app fieldpro-poc-backend -C "python scripts/seed_data.py"
```

### 2.7 Smoke test

```bash
curl https://fieldpro-poc-backend.fly.dev/health
# Expect: {"status":"ok","db":"ok","redis":"ok","version":"1.0.0","environment":"production"}
```

---

## Phase 3 — Deploy frontend (30 min)

### 3.1 Critical gotcha: `NEXT_PUBLIC_API_URL` is build-time

Next.js bakes `NEXT_PUBLIC_*` env vars into the JS bundle at `npm run build`. Setting them as runtime secrets does nothing. The frontend's API client uses whatever URL was in scope during the docker build.

**Two options:**

**Option A — Pass build-arg on deploy (recommended):**

Update `frontend/Dockerfile`:

```dockerfile
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build
```

Then on every deploy:
```bash
flyctl deploy -c fly.frontend.toml \
  --build-arg NEXT_PUBLIC_API_URL=https://fieldpro-poc-backend.fly.dev \
  --app fieldpro-poc
```

**Option B — Set in `fly.frontend.toml`:**

```toml
[env]
  NEXT_PUBLIC_API_URL = "https://fieldpro-poc-backend.fly.dev"
```

Easier to manage but means changing the toml when URLs change.

### 3.2 Launch frontend app

```bash
flyctl launch -c fly.frontend.toml --no-deploy --name fieldpro-poc --region dfw
```

### 3.3 Same image fix as backend

Delete the `image = "ghcr.io/..."` line from `fly.frontend.toml`.

### 3.4 Deploy

```bash
flyctl deploy -c fly.frontend.toml \
  --build-arg NEXT_PUBLIC_API_URL=https://fieldpro-poc-backend.fly.dev \
  --app fieldpro-poc
```

### 3.5 Smoke test

- Open https://fieldpro-poc.fly.dev/login
- Log in as `admin@demo.fieldpro.app` / `Admin123!`
- Verify dashboard renders with KPIs populated

---

## Phase 4 — Custom domain (optional, 30 min)

Skip if `*.fly.dev` is fine.

1. Register domain (Namecheap, Cloudflare, Porkbun — $12/yr)
2. Add CNAME records:
   - `app.yourdomain.com` → `fieldpro-poc.fly.dev`
   - `api.yourdomain.com` → `fieldpro-poc-backend.fly.dev`
3. Create Fly certs:
   ```bash
   flyctl certs create app.yourdomain.com --app fieldpro-poc
   flyctl certs create api.yourdomain.com --app fieldpro-poc-backend
   ```
4. Update backend secrets to reflect custom domain:
   ```bash
   flyctl secrets set --app fieldpro-poc-backend \
     ALLOWED_HOSTS="api.yourdomain.com" \
     BACKEND_CORS_ORIGINS='["https://app.yourdomain.com"]' \
     FRONTEND_URL="https://app.yourdomain.com" \
     BACKEND_URL="https://api.yourdomain.com"
   ```
5. Rebuild frontend with the new API URL.

---

## Phase 5 — Nightly demo reset (1 hr)

Without a reset, demo visitors will dirty the data over a few weeks. Two patterns:

### 5.1 Write the reset script

Create `scripts/reset_demo.py`:

```python
"""Drop and recreate the public schema, then re-seed demo data."""
import asyncio
import subprocess
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings
from scripts.seed_data import seed

async def reset():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute("DROP SCHEMA public CASCADE")
        await conn.execute("CREATE SCHEMA public")
    await engine.dispose()

    subprocess.run(["alembic", "upgrade", "head"], check=True)
    await seed()

if __name__ == "__main__":
    asyncio.run(reset())
```

### 5.2 Option A — Fly scheduled machine (simplest)

```bash
flyctl machine run --schedule "0 8 * * *" \
  --app fieldpro-poc-backend \
  --image registry.fly.io/fieldpro-poc-backend:latest \
  -- python scripts/reset_demo.py
```

Runs daily at 08:00 UTC (3am Central) — fine for a US-facing demo.

### 5.3 Option B — GitHub Actions cron

`.github/workflows/demo-reset.yml`:

```yaml
name: Reset Demo Data
on:
  schedule:
    - cron: '0 8 * * *'
  workflow_dispatch:

jobs:
  reset:
    runs-on: ubuntu-latest
    steps:
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl ssh console --app fieldpro-poc-backend -C "python scripts/reset_demo.py"
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
```

Easier to monitor (you can see runs in the Actions tab).

---

## Phase 6 — Demo UX polish (1–2 hr, optional but recommended)

This is what makes the difference between "polished POC" and "abandoned side project."

### 6.1 Always-visible demo banner

Add to `frontend/src/app/(dashboard)/layout.tsx`:

```tsx
<div className="bg-amber-500 text-white text-sm text-center py-1.5">
  🟡 Demo instance — data resets nightly. Not for real business use.
</div>
```

### 6.2 Pre-filled demo credentials on the login page

On `/login`, add three quick-login buttons under the form:

- "Try as Admin"
- "Try as Manager"
- "Try as Field Worker"

Each posts to `/auth/login` with the seeded credentials and redirects appropriately.

### 6.3 Disable signup

Comment out the `/register` route in `frontend/src/app/(auth)/register/page.tsx` (return a 404 or redirect to login).

### 6.4 Block search engine indexing

Create `frontend/public/robots.txt`:

```
User-agent: *
Disallow: /
```

You don't want Google indexing the demo data.

---

## Phase 7 — Monitoring (30 min)

### 7.1 Sentry

1. Project already created in Phase 0
2. Set the DSN secret (already done in Phase 2.3)
3. Trigger a test error to verify

### 7.2 Fly built-in metrics

```bash
flyctl dashboard --app fieldpro-poc-backend
```

Set up at minimum:
- **Alert: app down >5 min** → email
- **Alert: error rate >5%** → email

### 7.3 Optional: simple uptime ping

[UptimeRobot](https://uptimerobot.com) free tier — pings `/health` every 5 min, alerts if it fails. Independent of Fly's own monitoring.

---

## Phase 8 — CI/CD automation (45 min)

### 8.1 Generate Fly deploy tokens

```bash
flyctl tokens create deploy --app fieldpro-poc-backend
flyctl tokens create deploy --app fieldpro-poc
```

### 8.2 Add as GitHub secrets

Repo settings → Secrets and variables → Actions → New repository secret:
- `FLY_API_TOKEN_BACKEND`
- `FLY_API_TOKEN_FRONTEND`

### 8.3 Update `.github/workflows/deploy.yml`

Confirm it:
- Triggers on push to `main`
- Sets the right `--app` flags
- Runs `alembic upgrade head` post-deploy via `flyctl ssh console`
- Doesn't run the seed (you don't want to wipe data on every deploy)

---

## Phase 9 — Final verification checklist

- [ ] `curl https://fieldpro-poc-backend.fly.dev/health` returns `{"status":"ok",...}`
- [ ] `https://fieldpro-poc.fly.dev/login` loads under 2s
- [ ] Demo admin login works
- [ ] Dashboard KPIs populate
- [ ] Work orders list shows 14+ WOs across 6 statuses
- [ ] Creating a new work order succeeds
- [ ] Sentry receives events (force a 500 if needed)
- [ ] Demo banner is visible
- [ ] Nightly reset has run at least once
- [ ] CI/CD: push a no-op change → auto-deploys without manual intervention

---

## Cost summary

| Item | Monthly |
|---|---|
| Fly machines (2× shared-cpu-1x 256MB) | $0 (free tier) |
| Fly Postgres (1× shared-cpu-1x 1GB) | $0 (free tier) |
| Upstash Redis (10k commands/day) | $0 (free tier) |
| Sentry (5k errors/mo) | $0 (free tier) |
| UptimeRobot | $0 (free tier) |
| Custom domain | $1 ($12/yr amortized) |
| **Total** | **~$1/mo** |

---

## Known gotchas

| # | Issue | Mitigation |
|---|---|---|
| 1 | **`NEXT_PUBLIC_API_URL` is build-time** | Pass as `--build-arg` on every deploy or hard-code in `fly.frontend.toml` |
| 2 | **`BACKEND_CORS_ORIGINS` is a JSON array** | Must include the deployed frontend URL exactly, with `https://`, no trailing slash |
| 3 | **ARQ worker is dormant in this snapshot** | Anything that calls `enqueue_email_job()` becomes a no-op. For demo, fine. Add a "(demo only)" badge to email send buttons |
| 4 | **Seed script is not re-run-safe** | The nightly reset script must drop+recreate schema, not just call seed again |
| 5 | **`fly.toml` image field has placeholder** | Either replace `YOUR_GITHUB_ORG` or delete the line entirely |
| 6 | **`DATABASE_URL` needs `+asyncpg` prefix** | `flyctl postgres attach` writes a bare `postgres://`; manually edit |
| 7 | **`DEBUG=true` in production** | Never expose this externally — leaks stack traces |
| 8 | **Sentry init crashes on garbage DSN** | Already fixed in `.env.example`; make sure Fly secret is either valid DSN or completely unset |

---

## When to graduate to Plan B

You're ready to consider Plan B when:

- You have a specific business owner who has signaled real interest in being your first customer
- The demo has been live and stable for ≥2 weeks
- You've decided on pricing and pilot terms
- You're committing 6–10 weeks to make the platform production-grade for a real customer

See [Plan B](./deployment-plan-b-production-onboarding.md) for the full production roadmap.
