# Plan A Retrospective — Hiccups & Lessons for Plan B

**Date deployed:** 2026-05-20 (single working day, start to finish)
**Demo URLs:**
- Frontend: https://fieldpro-poc.fly.dev
- Backend: https://fieldpro-poc-backend.fly.dev

**Summary:** the public POC demo went live in one day on Fly.io, but the path was bumpier than the original Plan A doc suggested. **8 PRs** shipped during the deploy alone (numbered 15 → 23), each fixing a real issue surfaced by actual deployment rather than predicted ahead of time.

This document catalogs every hiccup chronologically, the actual root cause, the fix that landed, and what Plan B (production onboarding for a real first customer) should do differently to skip the same pain.

---

## How to read this doc

For each hiccup:

- **Symptom** — what we saw (error message, behavior)
- **Cause** — what was actually wrong
- **Fix** — what we changed (with PR reference)
- **Lesson for Plan B** — what to do differently next time

The doc is grouped by **theme**, not strictly chronological — easier to reference. Items inside each section are roughly in the order encountered.

Related docs:
- [`docs/planning/roadmap.md`](roadmap.md) — current active milestone
- [`docs/planning/plan-a.md`](plan-a.md) — original Plan A deploy plan
- [`docs/planning/plan-b.md`](plan-b.md) — Plan B production-onboarding plan (this retrospective feeds into it)
- [`docs/runbooks/smoke-test.md`](../runbooks/smoke-test.md) — the smoke-test runbook for the deployed demo
- [`scripts/smoke_test.py`](../../scripts/smoke_test.py) — automated version of the smoke test

---

## A. Tooling + environment setup

### A1. PowerShell 5.1 TLS handshake error on `flyctl` install

- **Symptom:** `iwr https://fly.io/install.ps1 -useb | iex` → `Invoke-WebRequest : The decryption operation failed`
- **Cause:** Windows PowerShell 5.1 defaults to TLS 1.0/1.1. fly.io requires TLS 1.2+.
- **Fix:** `[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12` before the install command. (Alternative: install via `winget install Fly.Flyctl`.)
- **Lesson for Plan B:** Anyone provisioning Fly resources from Windows should be on **PowerShell 7+** or use winget. Document this in the Plan B prerequisites — don't make ops staff debug TLS issues live.

### A2. PowerShell pipes inject a UTF-8 BOM into native command stdin

- **Symptom:** `$body | flyctl secrets import` → `"﻿DATABASE_URL" is not a valid secret name`
- **Cause:** PS 5.1 prepends a UTF-8 BOM when piping multi-line strings to native commands. Even setting `$OutputEncoding = [System.Text.UTF8Encoding]::new($false)` doesn't always help.
- **Fix:** Write to a temp file via `[IO.File]::WriteAllText($path, $content, [Text.UTF8Encoding]::new($false))`, then use `cmd /c "tool < file"` to bypass PowerShell's pipe encoding entirely.
- **Lesson for Plan B:** For any "set N secrets" operation, use a here-file + `cmd /c` redirect, or do it through a CI workflow with proper Linux shell semantics. Don't run secret-import operations from PS 5.1 ad-hoc.

### A3. `flyctl launch` choked on the root `pyproject.toml`

- **Symptom:** `flyctl launch --no-deploy --name fieldpro-poc-backend --region dfw` → `Error: No dependencies found in pyproject.toml`
- **Cause:** Fly's launch flow tries to auto-detect framework + dependencies. The root `pyproject.toml` is tooling-only (pytest/mypy/coverage config) and has no `[project]` section; Fly's detector bails. Even though we had a perfectly good `fly.toml` and `Dockerfile` ready.
- **Fix:** Skip `flyctl launch` entirely. Use `flyctl apps create <name> --org personal` to make the app slot, then `flyctl deploy` from the service dir.
- **Lesson for Plan B:** In any monorepo with per-service Dockerfiles + fly.tomls, **use `apps create` + `deploy`, not `launch`**. Add this to the Plan B runbook explicitly.

---

## B. Dockerfile and image issues

### B1. CMD used bare command names; Fly's init does `execve` without PATH lookup

- **Symptom:** Backend machine cold-loops with `Error: failed to spawn command: gunicorn ... No such file or directory (os error 2)`. Same shape would have hit the frontend with `node server.js`.
- **Cause:** Fly's init calls `execve(argv[0], ...)` directly. POSIX `execve` requires an absolute path for `argv[0]` — it does NOT do PATH lookup. Bare `gunicorn` or `node` resolves to `${WORKDIR}/gunicorn` (which doesn't exist) and fails.
- **Fix (PR #18):** Use absolute paths in CMD:
  - `["/opt/venv/bin/uvicorn", "app.main:app", ...]` (backend)
  - `["/usr/local/bin/node", "server.js"]` (frontend)
- **Lesson for Plan B:** This is a Fly.io-specific gotcha vs Docker/k8s. **Always use absolute paths in production Dockerfile CMDs.** Set this as a repo-wide convention; consider a linter rule.

### B2. Backend Dockerfile CMD referenced `gunicorn` but `requirements.txt` only had `uvicorn[standard]`

- **Symptom:** Same `No such file or directory` error as B1, but persists even after fixing the PATH issue — because gunicorn truly isn't installed.
- **Cause:** Stale Dockerfile from an earlier iteration when gunicorn was the choice; requirements were trimmed to uvicorn but the CMD wasn't updated.
- **Fix:** Switch backend CMD to uvicorn directly (`/opt/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000`). Single worker, since 4 workers × ~88 MB Python heap > 512 MB demo machine RAM.
- **Lesson for Plan B:** Pin the server choice clearly (uvicorn vs gunicorn+uvicorn-workers). Add a CI step that smoke-builds the production image and runs `docker run image --version` style sanity check.

### B3. `fly.toml` at repo root broke the backend Dockerfile's build context

- **Symptom:** First deploy attempt → `ERROR [builder 5/6] COPY requirements.txt .` failed because the file wasn't in the context.
- **Cause:** `backend/Dockerfile` does `COPY requirements.txt .` — it expects build context = `backend/`. But with `fly.toml` at the repo root, Fly's default context was the repo root. `requirements.txt` lived at `backend/requirements.txt`, not root.
- **Fix (PR #17):** Move `fly.toml` → `backend/fly.toml` and `fly.frontend.toml` → `frontend/fly.toml`. Update CI to `cd backend && flyctl deploy` / `cd frontend && flyctl deploy`. Per-service tomls is the Fly-recommended monorepo pattern anyway.
- **Lesson for Plan B:** **Always put fly.tomls in the same directory as the service's Dockerfile.** Add a check to the deploy workflow that verifies this.

### B4. fly.toml had a `ghcr.io/YOUR_GITHUB_ORG/fieldpro/backend:latest` placeholder image

- **Symptom:** Even after fixing build context, Fly was trying to pull a non-existent GHCR image.
- **Cause:** Snapshot of an upstream config that assumed CI built + pushed to GHCR. The placeholder string was never updated.
- **Fix (PR #16):** Remove the `[build] image = "..."` line entirely so Fly builds from Dockerfile on each deploy.
- **Lesson for Plan B:** **Production deploys should pre-build images in CI** (GHCR or ECR or similar), not build-on-deploy. Plan B should wire this up properly so deploys are fast + reproducible. The Plan A "build on Fly" pattern is fine for a demo but not for production rollouts where you want the image to be the same artifact you tested.

### B5. The seed/reset scripts lived at `scripts/` but the Dockerfile only copies `backend/`

- **Symptom:** `flyctl ssh console -C "python scripts/seed_data.py"` → `python: can't open file '/app/scripts/seed_data.py': [Errno 2] No such file or directory`
- **Cause:** Scripts were at repo-root `scripts/` and not in the backend Docker build context. Dev mode had `docker-compose.override.yml` mounting `./scripts:/app/scripts:ro` which masked the issue.
- **Fix (PR #19):** Move `scripts/seed_data.py` and `scripts/reset_demo.py` into `backend/scripts/`. Drop the redundant compose mount. `scripts/setup.sh` (host-side dev script) stayed at repo root.
- **Lesson for Plan B:** **Anything that imports from `backend/app/...` must physically live inside `backend/`.** The dev-mode mount that hid this is a smell. Plan B should audit any other "lives at root but imports from a service" files.

---

## C. Fly.io platform behaviors

### C1. Single-node Fly Postgres + auto-stop = leader-election timeout on cold start

- **Symptom:** `flyctl postgres attach` returned `Error: no active leader found`. `flyctl status --app fieldpro-poc-db` showed `STATE: started, ROLE: error`.
- **Cause:** Free-tier `shared-cpu-1x` Postgres has auto-stop enabled by default. When it cold-starts from `stopped`, the single replica takes ~30 sec to elect itself leader. Operations during that window fail.
- **Fix:** Wait 30 sec for the role to stabilize to `primary`, retry. Long-term: disable auto-stop on the Postgres machine, OR migrate to Fly Managed Postgres (`fly mpg`) which doesn't have this issue.
- **Lesson for Plan B:** **Do not use Unmanaged Postgres in production.** Fly is actively steering people to Managed Postgres for a reason. Plan B should provision via `fly mpg create` from day one. The cost difference (~$5–10/mo for the small tier) is trivial vs the operational fragility.

### C2. uvicorn auto-reads `WEB_CONCURRENCY=4` → 4 workers × 88 MB = OOM on 512 MB machine

- **Symptom:** `Out of memory: Killed process 649 (python)` in logs every few minutes. Workers respawn and immediately die.
- **Cause:** fly.toml had `[env] WEB_CONCURRENCY = "4"` (left over from a gunicorn config). Modern uvicorn (≥ 0.30) reads this env var and spawns 4 workers. Each Python worker is ~88 MB resident; 4 of them on a 512 MB machine = OOM.
- **Fix:** Override via secret (`flyctl secrets set WEB_CONCURRENCY=1`) since secrets take precedence over `[env]`. Single worker handles demo traffic easily.
- **Lesson for Plan B:** **Always right-size workers to machine RAM.** Rule of thumb: `workers = min(2, RAM_MB / 200)`. Document the machine RAM and worker count together in the Plan B fly.toml — a comment block beside the `[[vm]]` section.

### C3. `flyctl deploy` hangs on "Checking health of machine" even when the app is fine

- **Symptom:** Deploy spinner runs for 5+ minutes. App is actually serving 200s.
- **Cause:** Fly's health-check status is sticky after rolling deploys; the new check doesn't always re-poll quickly. Especially noticeable with auto_stop enabled.
- **Fix:** Ctrl+C the spinner (rollout continues server-side), verify with `flyctl status` + `curl /health` directly. If status shows `critical` but the app responds, restart the machine to force a fresh check.
- **Lesson for Plan B:** Don't trust the deploy spinner alone. CI should treat "deploy command exited 0 OR /health returns 200" as success. Add an explicit `curl /health` step after every `flyctl deploy` in the workflow.

### C4. `DATABASE_URL` from `flyctl postgres attach` has wrong driver prefix + wrong SSL param

- **Symptom:** Backend can't connect: `asyncpg.ConnectionResetError` during TLS handshake.
- **Cause:** `flyctl postgres attach` writes `DATABASE_URL=postgres://user:pass@host:5432/db?sslmode=disable`. The app needs `postgresql+asyncpg://...` prefix, and asyncpg doesn't recognize libpq's `sslmode` param. Worse, asyncpg's default is to attempt SSL, and Fly's internal `.flycast` network doesn't support SSL.
- **Fix:** Manually override the secret:
  ```
  postgresql+asyncpg://fieldpro_poc_backend:PASSWORD@fieldpro-poc-db.flycast:5432/fieldpro_poc_backend?ssl=disable
  ```
  Note `+asyncpg` prefix and `?ssl=disable` (asyncpg-native param, NOT `sslmode`).
- **Lesson for Plan B:** **Have a `post_attach.sh` script that auto-corrects the DATABASE_URL after attach.** Or use Managed Postgres which gives proper SSL with a TLS cert. Either way, never let the auto-attached URL ship to production unmodified.

### C6. Schema reset invalidates the always-on backend's cached prepared statement plans

- **Symptom:** ~5–10 sec window of 500s on the backend immediately after the daily reset machine runs. Logs show `asyncpg.exceptions.InvalidCachedStatementError: cached statement plan is invalid due to a database schema or configuration change`.
- **Cause:** The reset script drops + recreates the `public` schema, which changes table/column OIDs. The always-on backend has cached prepared statement plans (asyncpg's default `prepared_statement_cache_size=100`) pointing at the *old* OIDs. The first few queries after the reset hit those stale plans and fail.
- **Fix (self-healing):** SQLAlchemy's asyncpg dialect auto-invalidates the prepared-statement cache on the first such error. Subsequent queries succeed. Net effect: a few seconds of 500s at 03:00 Central when no one's hitting the demo, then back to normal.
- **Lesson for Plan B:** Two options:
  1. **Engine config:** `create_async_engine(..., connect_args={"prepared_statement_cache_size": 0})` — disables the cache entirely. Minor perf cost (~1ms per query for re-prepare), zero invalidation issues.
  2. **Cycle the backend on reset:** add a `flyctl machine restart <id> --app fieldpro-poc-backend` step to the reset script. Cleaner from a connection-state perspective, but adds ~30 sec downtime per night.

  Option 1 is the right call for Plan B — schemas DO change during deploys (Alembic migrations), and disabling the prepared statement cache makes the backend resilient to that.

### C5. Fly's `redirect_slashes=True` + FastAPI `@router.get("/")` + frontend without trailing slash = 307 loop that strips auth

- **Symptom:** Frontend dashboard showed empty lists for work orders, clients, etc. HAR showed every API call returning 307. Backend had the data.
- **Cause:** FastAPI registered routes at `/work-orders/` (prefix + `/`). Frontend called `/work-orders` (no slash). FastAPI 307-redirected. Browser security: **same-origin redirects across path boundaries strip the `Authorization` header**. The redirected request hit the backend unauthenticated, returned 401, frontend rendered empty.
- **Fix (PR #22):** Change all collection routes from `@router.get("/")` to `@router.get("")`. Combined with prefix, the registered path becomes `/work-orders` (no slash) and matches the frontend.
- **Lesson for Plan B:** **Standardize on no-trailing-slash for collection routes.** Add a lint rule or convention test. This is one of those cross-cutting issues that's incredibly hard to debug live but trivial to prevent.

---

## D. Frontend issues

### D1. Next.js `experimental.typedRoutes` rejects `Link` hrefs that don't map to actual routes

- **Symptom:** `next build` failed: `"/forgot-password" is not an existing route. If it is intentional, please type it explicitly with as Route.`
- **Cause:** `experimental.typedRoutes: true` validates every `<Link href>` and `router.push()` target at build time. The codebase had multiple pre-existing broken targets that had never been caught — because CI runs `tsc --noEmit`, which doesn't run typedRoutes generation. The validation only fires inside `next build`.
- **Fix:** PR #20 patched the specific `/forgot-password` link. PR #21 disabled `typedRoutes` to unblock the demo. Follow-up task queued to audit every broken Link, fix them, then re-enable.
- **Lesson for Plan B:** **CI's lint job must include `next build`, not just `tsc`.** A separate chip is open for this. Plan B should never ship without this guardrail.

### D2. Frontend `INDUSTRIES` dropdown hardcoded display labels; backend wanted enum codes

- **Symptom:** Every "New Client" attempt returned 422: `Invalid industry 'Commercial Real Estate'. Must be one of: commercial_cleaning, janitorial, ...`
- **Cause:** Frontend dropdown was a `string[]` of display labels (Commercial Real Estate, Healthcare, Retail, ...). The backend's `Industry` enum is a completely different list of field-service industries in snake_case. Two different lists with zero overlap.
- **Fix (PR #23):** Replace `INDUSTRIES` with `{value, label}[]` matching the backend enum. Display label in the dropdown, submit snake_case value.
- **Lesson for Plan B:** **Generate frontend enum types from the backend OpenAPI schema.** Use `openapi-typescript` or similar. Manual `INDUSTRIES = [...]` lists drift the moment anyone edits either side. This is a categorical fix, not just for industry — every enum (status, role, priority, work_type) has the same exposure.

### D3. `NEXT_PUBLIC_API_URL` is build-time, not runtime

- **Symptom:** Without explicit handling, the frontend bundles whatever default URL was in scope at build time, regardless of any runtime `flyctl secrets set`.
- **Cause:** Next.js bakes `NEXT_PUBLIC_*` vars into the JS bundle during `npm run build`. Setting them as Fly runtime env or secrets does nothing.
- **Fix (PR #16):** Add `ARG NEXT_PUBLIC_API_URL` + `ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL` to the frontend Dockerfile's builder stage. Pass on every deploy: `flyctl deploy --build-arg NEXT_PUBLIC_API_URL=https://fieldpro-poc-backend.fly.dev`.
- **Lesson for Plan B:** Document this loudly in the Plan B runbook. Better: **set `NEXT_PUBLIC_API_URL` in `frontend/fly.toml` `[env]` for production-stable URLs**, and only override via `--build-arg` for non-prod environments.

---

## E. Test suite gaps

### E1. CI didn't catch the trailing-slash regression because `httpx.AsyncClient` defaults to `follow_redirects=False`

- **Symptom:** PR #22 (route fix) passed CI green, but then PR #23's CI failed with `assert resp.status_code == 201` returning 307 on every test that POSTed to `/api/v1/clients/`.
- **Cause:** Test fixtures called `/api/v1/clients/` (trailing slash) which now 307-redirected. httpx in test mode doesn't follow redirects by default. PR #22 didn't update the tests, and CI run for #22 still finished before merge so the broken state never blocked.
- **Fix (PR #23 fixup):** `sed`-fix all `/api/v1/<collection>/` → `/api/v1/<collection>` across 8 test files. 48 lines.
- **Lesson for Plan B:** Two lessons here:
  1. **Treat test URLs as production contracts.** If you refactor routes, refactor tests in the same PR.
  2. **CI should be required + must complete before a merge can land.** Branch protection: enable "required status checks must pass" AND "branches must be up to date".

### E2. No E2E test exercises create flows under realistic frontend conditions

- **Symptom:** The frontend industry/enum mismatch (D2) wasn't caught until live demo testing. Playwright tests exist but don't cover create flows.
- **Cause:** E2E suite focuses on auth + read flows. Create flows are skipped.
- **Lesson for Plan B:** **Playwright must exercise the critical create flows** (client, work-order at minimum). One test per write endpoint, using the actual UI form, asserting the network response is 201.

### E3. CI's "Frontend Lint & Type Check" job doesn't run `next build`

- **Symptom:** Broken Link targets (D1) shipped to deploy uncaught.
- **Cause:** `tsc --noEmit` runs but `next build` doesn't, so the `typedRoutes` validation never fires.
- **Lesson for Plan B:** Already filed as a follow-up. Add a `frontend-build` job that runs `npm run build` and produces the standalone artifact. Cache `node_modules` aggressively to keep it fast.

---

## F. Process + workflow

### F1. We shipped 8 PRs for the deploy itself (PRs 15 → 23)

- **PR 15** — planning docs
- **PR 16** — initial code prep (fly tomls, Dockerfile build-arg, demo polish, seed reset script)
- **PR 17** — fly tomls into per-service dirs
- **PR 18** — absolute paths in CMD + uvicorn switch
- **PR 19** — scripts into backend/
- **PR 20** — forgot-password Link fix
- **PR 21** — disable typedRoutes
- **PR 22** — drop trailing slashes from routes
- **PR 23** — client industry enum + drop trailing slashes from tests

Each was small + scoped, which is good. But that's **8 round-trips of "branch → CI → merge → pull → redeploy → discover next issue"**. Each round-trip averaged ~10 minutes.

- **Lesson for Plan B:** Before the first production deploy, do a **"dry run"** locally: build the image, run it with prod-like env vars, hit the health endpoint, run the seed, hit a few API endpoints. Most of B1, B2, B5 would have been caught in 30 min of dry-run testing on a developer machine.

### F2. Branch protection was on, which forced PR-per-fix

- This was the right call — preserved a clean git history and forced CI to gate every change. But it amplified the round-trip time.
- **Lesson for Plan B:** Keep branch protection on. But have a Plan B "deploy week" runbook that batches related fixes when CI signal is clear: e.g. one PR for "all Dockerfile fixes" rather than four sequential one-line PRs.

### F3. Some fixes (e.g. the analytics dashboard 500) were deferred to follow-ups

- A few real bugs (notably `/api/v1/analytics/dashboard` returning 500) were filed as follow-up tasks rather than fixed inline. Right call for time-boxing the demo deploy, but they need to be tracked.
- **Lesson for Plan B:** **Maintain a "deploy debt" list** during the deploy. Every "we'll fix that later" becomes a tracked item. Don't let them rot.

---

### F4. Deferring monitoring to Phase 7 worked for the deploy itself, but Sentry would have shortened later debugging

- **Observation:** during phases 0–3, every bug was surfaced by `flyctl logs` within seconds. Sentry wouldn't have been faster. So sequencing monitoring at Phase 7 (after the demo is live) was correct.
- **BUT:** the moment Sentry was wired in Phase 7, it caught the long-mysterious `/api/v1/analytics/dashboard` 500 in 5 minutes — `AmbiguousParameterError` on a bare-NULL SQL param. We'd been chasing this through HAR captures and SSH consoles for hours. The Sentry traceback made it obvious; fix landed in PR #26 (2 lines of SQL CAST).
- **Lesson for Plan B:** This validates the Plan B principle. Sequencing rule:
  - For a brand-new service deploy: get it running first, monitoring can be Phase ~5+
  - For an existing service that's already live and being debugged: monitoring is the *first* thing you set up, not the last
  - Once you have monitoring, hidden bugs become visible bugs — and visible bugs get fixed in minutes instead of hours

### F5. CI/CD pipeline broke itself the same way manual deploys did

- **Symptom:** First auto-deploy from CI hung for 12 minutes on the "Deploy backend" step, same sticky-spinner pattern from manual deploys (C3). Workflow eventually marked the run as failure even though the deploy had actually succeeded — the app was serving 200s within 60 seconds.
- **Cause:** The shipped `deploy.yml` used `flyctl deploy --wait-timeout 600`. With Fly's sticky-spinner bug, the workflow waited the full 10 minutes before marking the step as failed.
- **Fix (PR #29):** Two changes to `.github/workflows/deploy.yml`:
  1. Reduce `--wait-timeout` from 600 to 120 (2 min — bounded fail-fast).
  2. Mark both deploy steps `continue-on-error: true`, and make the curl-based **Smoke Test step** the source of truth. If `/health` and `/login` return 200, the deploy worked regardless of what `flyctl deploy` thought.
- **Lesson for Plan B:** **Never trust a deploy tool's own opinion of success.** Hit the actual endpoint with curl. Build this pattern into the deploy workflow from day one — don't wait until a sticky-spinner bites you in CI.

## G. What Plan A got right

A few things from the original Plan A doc worked as predicted:

- **Fly.io was the right platform choice.** Free tier covered the demo at ~$0/month. The dev experience for a single-region demo is excellent.
- **Per-service tomls (after we moved them)** is clean and scales to more services.
- **The demo banner + quick-login buttons + disabled signup + robots.txt** package made the live demo feel intentional, not abandoned.
- **The roadmap doc** kept us honest about Plan A scope vs Plan B scope when we were tempted to fix everything inline.
- **The 1-day timebox held** — we landed the demo same-day, even with the hiccups.

---

## H. Plan B checklist additions

Based on the lessons above, the following items must be added or strengthened in the existing Plan B doc:

### Infrastructure
- [ ] Use Fly Managed Postgres (`fly mpg create`), not Unmanaged
- [ ] Provision machines sized for actual workload (≥ 1 GB RAM if running > 1 uvicorn worker)
- [ ] Wire up GHCR builds in CI; production deploys pull pre-built images, not build-on-deploy
- [ ] Have a `post_attach.sh` that fixes the DATABASE_URL prefix + SSL param

### Code conventions
- [ ] Absolute paths in all Dockerfile CMDs (enforce via repo convention or lint)
- [ ] All collection routes use `@router.get("")` not `@router.get("/")`
- [ ] All `<Link href>` and `router.push()` targets are typed against actual routes
- [ ] All frontend enums generated from backend OpenAPI schema (no hand-maintained lists)

### Testing + CI
- [ ] CI runs `next build` in addition to `tsc --noEmit`
- [ ] CI runs `flyctl deploy --dry-run` (or equivalent docker build) on every PR
- [ ] Test fixtures use the same URL conventions as the frontend (no trailing slashes on collections)
- [ ] Playwright covers create flows for every primary entity
- [ ] Post-deploy step in CI does `curl /health` and fails the job if not 200

### Operational
- [ ] Sentry wired from day one (DSN as a secret, not in `.env`)
- [ ] UptimeRobot or similar external monitoring before going public — **two monitors max**: backend `/health` (liveness) and frontend `/login` (page renders). Don't burn a monitor slot per endpoint — they'd all alarm together on a single root cause (Postgres down, etc).
- [ ] **Scheduled smoke test** for deeper per-endpoint verification — run `scripts/smoke_test.py` on a Fly scheduled machine (`--schedule hourly`) against the internal `.internal` URL. Captures auth, write paths, and RBAC behavior on a periodic basis — the kind of coverage UptimeRobot can't give you because of token expiry. Alerts via Sentry on failure.
- [ ] A documented secret-rotation procedure (DB password, JWT signing keys)
- [ ] On-call playbook: how to recognize and recover from each of A1, C1, C2, C3
- [ ] A `post-deploy-smoke.sh` that runs the same checks as the smoke-test runbook, gated on deploy success
- [ ] CI deploy steps use bounded `--wait-timeout` (≤ 120s) + `continue-on-error: true`, with curl-based smoke test as the real source of truth. Don't trust the flyctl spinner — see C3 + F5.

### Process
- [ ] Local dry-run before first deploy of every new service (build → run → smoke test on developer machine)
- [ ] One PR per concern remains the default, BUT a "deploy week" mode where related fixes can be batched
- [ ] Maintain an explicit deploy-debt list during any multi-day deploy; review it before declaring success

---

## I. Reference: full PR list from Plan A

| PR | Title | Why |
|---|---|---|
| #15 | `docs(planning): add roadmap + Plan A + Plan B` | Initial planning docs |
| #16 | `chore(demo): Plan A code prep for Fly.io deployment` | First batch — fly tomls, Dockerfile build-arg, demo banner, quick-login, robots.txt, deploy.yml |
| #17 | `fix(deploy): move fly tomls into service dirs for correct build context` | B3 |
| #18 | `fix(dockerfile): use absolute paths in CMD + switch backend to uvicorn` | B1, B2 |
| #19 | `fix(structure): move python scripts into backend/ so they ship in the image` | B5 |
| #20 | `fix(frontend): replace Link to non-existent /forgot-password route` | D1 |
| #21 | `fix(frontend): disable typedRoutes to unblock production build for demo` | D1 (broader workaround) |
| #22 | `fix(api): drop trailing-slash from collection routes to stop 307 redirect chain` | C5 |
| #23 | `fix(frontend+tests): client industry enum + drop trailing slashes from test URLs` | D2, E1 |
| #25 | `docs: add smoke-test runbook + Plan A retrospective + smoke script` | Ship operational artifacts in the repo, not just in private notes |
| #26 | `fix(analytics): cast nullable date params in dashboard endpoint to fix 500` | Resolves the long-standing `/api/v1/analytics/dashboard` 500. Surfaced via Sentry (Phase 7). |
| #27 | `docs(notes): add plain-language explainer of the whole deployment` | Onboarding doc for non-technical readers |
| #28 | `fix(health): accept HEAD requests on /health for UptimeRobot` | UptimeRobot free tier sends HEAD by default; FastAPI was GET-only |
| #29 | `fix(ci): bound fly deploy waits + make smoke test source of truth` | F5 — hardens deploy.yml against the sticky-spinner |

---

## J. Open follow-ups

These were tracked during Plan A but not blocking the demo:

1. **Build crew + user management UI** — the MVP backend supports both, but no UI exists yet. Both "Create Crew" and any user-management screens are placeholders.
2. ~~**Debug `/analytics/dashboard` 500**~~ → **Resolved via PR #26** once Sentry was wired in Phase 7 (took 5 min after Sentry came online to identify + fix the root cause: `asyncpg.AmbiguousParameterError`).
3. **Re-enable typedRoutes + fix all broken Link targets** — pairs with the CI build step.
4. **Add `next build` step to CI** — prevents D1 from regressing.
5. **Disable asyncpg prepared-statement cache** (from C6) — prevents the brief post-reset 500 window. One-line fix: `connect_args={"prepared_statement_cache_size": 0}` in `create_async_engine`.
