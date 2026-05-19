# Deployment Plan B — Production First-Client Onboarding

**Goal:** First real janitorial business operating their day-to-day on FieldPro, paying or in a structured pilot
**Timebox:** 6–10 weeks from green-light to customer live
**Monthly cost:** $150–250 baseline infrastructure + insurance + dev time

---

## What "production" means here

- A real customer doing real billable work on the platform
- Real data with backups, recovery procedures, and a tested restore drill
- Real domain email with SPF/DKIM/DMARC so transactional mail doesn't go to spam
- Real SLA (even if it's just 99% uptime and informal)
- Legal cover: Terms of Service, Privacy Policy, optional DPA
- Operational readiness: status page, incident runbook, support inbox
- A pilot framework with explicit success criteria and a go/no-go decision point

---

## Decisions to make BEFORE starting (1 week of thinking)

These shape every downstream choice. Don't skip.

- [ ] **Company entity** — LLC for liability separation
- [ ] **Brand name + domain** — `fieldpro.app` may be taken; register what you'll actually use
- [ ] **Pricing model** — flat / per-seat / per-WO / tiered freemium-to-paid
- [ ] **Pilot terms** — free pilot? paid pilot at discount? duration (30 / 60 / 90 days)?
- [ ] **Target customer profile** — vertical, size (5–50 employees), geography
- [ ] **Identified first customer** — warm intro >> cold outbound for #1
- [ ] **Deal-breaker integrations** — QuickBooks for accounting is the most common ask in janitorial
- [ ] **Insurance posture** — E&O / Cyber liability before signing first contract

---

## Phase 1 — Engineering prerequisites (3–4 weeks)

### 1.1 MUST close before going live

These are non-negotiable for a real customer.

| # | Item | Why it matters | Effort |
|---|---|---|---|
| 1 | **Real PDF invoice export** | `window.print()` is unacceptable as a billing artifact emailed to a client | 2 days |
| 2 | **ARQ worker deployed + email send wired** | Invoice email, WO assignment notification, password reset all blocked without it | 3 days |
| 3 | **Email templates (transactional)** | Hand-coded HTML for: invoice sent, WO assigned, WO completed, password reset, account created. MJML or React Email | 2 days |
| 4 | **Domain email auth (SPF + DKIM + DMARC)** | Without this, transactional mail goes to spam — customer can't sign in | 1 day |
| 5 | **MFA frontend flow** | Backend exists; ship setup/verify UI | 2 days |
| 6 | **Password reset flow end-to-end** | Verify: button → email arrives → reset link → new password → relogin | 1 day |
| 7 | **Hard geofence enforcement** | Workers can currently check in from anywhere — defeats the GPS feature's value | 2 days |
| 8 | **Audit log retention policy** | Decide: keep forever? archive to S3 after 90 days? document the policy | 0.5 day |
| 9 | **DB backup + tested restore** | Automated daily PITR-style backup + at least one successful restore drill into staging | 2 days |
| 10 | **Sentry production setup** | Real DSN, error grouping rules, alerting → phone, release tracking | 1 day |
| 11 | **Account / tenant deletion flow** | Admin can delete a user; superadmin can deactivate/delete a tenant. GDPR + data hygiene | 2 days |
| 12 | **Tenant data export** | Admin can dump their data — CSV per resource minimum, JSON ideal | 2 days |
| 13 | **Staging environment** | Fly app + DB matching production config; deploys go here first | 1 day |

**Total: ~22 working days ≈ 4–5 weeks if focused full-time.**

### 1.2 SHOULD close ideally

| # | Item | Notes |
|---|---|---|
| 14 | Inventory + equipment UI | Backend models exist; janitorial often tracks supplies |
| 15 | Recurring WO at scale | Verify next-instance generation under load |
| 16 | Drag-and-drop dispatch | View-only schedule is OK for pilot |
| 17 | Inline help / tour | First-run experience for admin |
| 18 | Customer-facing changelog | `/changelog` page with release notes |

---

## Phase 2 — Production infrastructure (1 week)

### 2.1 Compute

- **Backend:** 2× shared-cpu-2x @ 1GB RAM, auto-scale 1–3 = ~$30/mo
- **Frontend:** 2× shared-cpu-1x @ 256MB = ~$5/mo
- **ARQ worker:** 1× shared-cpu-1x @ 512MB = ~$5/mo

Multiple machines per app gives zero-downtime deploys and tolerates a machine going down.

### 2.2 Database

- **Fly Postgres** managed cluster — `shared-cpu-2x` with 2GB RAM, 10GB volume, automated daily snapshots
- Or **Supabase** if you want managed PITR + a nicer admin UI
- Cost: $25–40/mo

**Backup verification (one-time):**
1. Trigger a manual snapshot
2. Restore it into a fresh DB
3. Document the exact procedure (commands, time taken)
4. Add to the incident runbook

### 2.3 Redis

- **Upstash paid** — $10/mo for 100k commands/day, multi-AZ
- Free tier won't survive a real workload

### 2.4 Object storage

- **Cloudflare R2** with custom domain (`uploads.yourdomain.com`)
- $0.015/GB/mo storage, $0 egress
- Required for: WO attachments, employee photo uploads, future inventory photos

### 2.5 Email provider

**Postmark** (recommended for transactional — best deliverability)
- First 100 emails/mo free; $15/mo for 10k emails
- Set up DKIM + Return-Path with their domain wizard

Or **Resend** — similar pricing, React Email templates work out of the box

**Not** SendGrid for transactional in 2026 — deliverability has degraded.

### 2.6 CDN / edge

- Fly's built-in edge handles static asset caching for free
- If you need more (image transforms, broader edge presence): Cloudflare in front of frontend

### 2.7 Secrets management

- Fly secrets (encrypted at rest, never logged)
- Document **quarterly rotation procedure** for SECRET_KEY and REFRESH_SECRET_KEY

### 2.8 Container registry

- GitHub Container Registry: free for public repos, $4/mo for private
- Decide if going private — if so, switch repo visibility and budget for it

### 2.9 Staging environment

**Critical and easy to skip — don't skip.**

- Mirror production: same Fly regions, same DB tier, same Redis
- Separate Fly apps: `fieldpro-staging-backend`, `fieldpro-staging`
- Separate subdomain: `staging.yourdomain.com`
- Test data not real data
- CI/CD: every push to `main` deploys to staging; production deploys are tagged releases

Cost adds ~$30–50/mo but you'll thank yourself.

---

## Phase 3 — Legal / compliance (parallel with Phases 1–2, 1–2 weeks)

### 3.1 Customer-facing documents

- [ ] **Terms of Service** — drafted, lawyer-reviewed
- [ ] **Privacy Policy** — drafted, lawyer-reviewed
- [ ] **Data Processing Agreement template** — ready to send if customer requests
- [ ] **Cookie banner** — if any chance of EU traffic
- [ ] **Acceptable Use Policy** — what customers can't do on the platform

**Cost:** $1,500–3,500 for a startup-friendly lawyer to draft + review all three.

Templates to start from: Common Paper (free, well-respected templates for SaaS).

### 3.2 Technical compliance checks

- [ ] **Tenant data isolation regression test** in CI — try to query tenant B's data as tenant A; must return empty
- [ ] **Audit log immutability** — verified at DB level: no application UPDATE / DELETE grants
- [ ] **Encryption at rest** — Fly volumes handle this; verify and document
- [ ] **Encryption in transit** — TLS on all endpoints
- [ ] **Password hashing cost** — bcrypt cost ≥12
- [ ] **Session timeout policy** — refresh token lifetime aligned with stated policy

### 3.3 Liability / business

- [ ] **LLC formed**
- [ ] **E&O + Cyber liability insurance** — $50–150/mo via Vouch, Embroker, or Coalition
- [ ] **Customer contract template** — covers SLA / payment / term / termination
- [ ] **Bank account in LLC name**

---

## Phase 4 — Security pass (1 week)

### 4.1 Automated scanning (add to CI)

- [ ] **Snyk** or **Semgrep** SAST on every PR
- [ ] **`pip-audit`** on backend dependencies
- [ ] **`npm audit`** on frontend dependencies
- [ ] **Trivy** scan on built Docker images
- [ ] **OWASP ZAP baseline** scan against staging — weekly cron

### 4.2 Manual review against OWASP Top 10 2021

| ID | Risk | Defense in this codebase |
|---|---|---|
| A01 | Broken Access Control | Tenant isolation tests + RBAC dependency injection — verify exhaustive |
| A02 | Cryptographic Failures | Verify bcrypt cost ≥12, JWT signing key ≥32 bytes |
| A03 | Injection | SQLAlchemy parameterizes; verify no raw `text()` with user input |
| A04 | Insecure Design | Run a threat model session |
| A05 | Security Misconfiguration | `DEBUG=false`, `ALLOWED_HOSTS` strict, `BACKEND_CORS_ORIGINS` strict |
| A06 | Vulnerable Components | CI dep-scan must be clean before deploy |
| A07 | Authentication Failures | Rate limit `/auth/login`, lockout after 5 failed attempts, MFA available |
| A08 | Software/Data Integrity | Deploy from CI only, signed commits ideal |
| A09 | Logging Failures | Audit log covers; errors → Sentry; access logs preserved 30 days |
| A10 | SSRF | Review any URL-fetching endpoints |

### 4.3 Optional: third-party pen test

- **Cobalt.io** or **Bugcrowd** — $5k–$15k for a small-scope test
- Worth it before signing any customer who'll store sensitive data
- Schedule for ~2 weeks before Customer Discovery so findings can be remediated

---

## Phase 5 — Operational readiness (1 week)

### 5.1 Status page

- **Better Stack** (free tier) or **Atlassian Statuspage** ($29/mo)
- Auto-poll `/health` from **outside Fly** to detect outages independently
- Subscribe customer to email/SMS status updates

### 5.2 Incident response runbook

A doc that answers "if X breaks, what do I do?" Cover at minimum:

- DB down
- App down
- Deploy broke prod (rollback procedure)
- Customer reports data loss
- Suspected breach
- Email not sending (SPF/DKIM/DMARC misalignment)
- Sentry alert fatigue (when to ignore vs page)

### 5.3 On-call

- Just you for the first customer — document the escalation path anyway
- **PagerDuty free** for one user, OR Sentry alerts forwarded to your phone via push

### 5.4 Support

- `support@yourdomain` → **Help Scout** ($25/mo) or **Front** or just a Gmail label
- Response SLA documented (e.g., business hours <4hr; P0 <1hr 24/7)

### 5.5 Monitoring dashboards

**Fly built-in metrics:**
- Request rate / error rate / p50-p95-p99 latency
- DB connection pool utilization
- Background worker queue depth

**Custom business metrics:**
- MAU per tenant, WOs/day, check-ins/day, invoices/week, $$ processed
- Audit-log volume

### 5.6 Communications

- **Customer-facing changelog** — Productlane, Headway, or a static `/changelog` page
- **Maintenance window policy** — when can you deploy without notification?

### 5.7 Backup verification drill

Run this exactly once before going live:

1. Take a snapshot of production
2. Restore into a fresh DB
3. Verify counts match: users, work orders, audit logs, invoices
4. Time the restore (you'll quote this as recovery time objective)
5. Document the exact commands

---

## Phase 6 — Customer discovery (1–2 weeks)

### 6.1 Identify

- **Warm intro >> cold outbound** for customer #1
- Target: existing janitorial business with 5–50 employees, ideally local
- Sources: your network, local chamber of commerce, BNI, industry Facebook groups

### 6.2 Discovery call (45 min)

**Business shape**
- How many crews? How many employees per crew?
- How many clients? How many service locations per client?
- What's your recurring service pattern?

**Current workflow**
- How do you currently schedule / dispatch / track / bill?
- What tools? (Excel? group chat? paper checklists? other apps?)

**Pain**
- What's your biggest pain right now?
- What would have to be true for FieldPro to replace your current tools?

**Integration requirements**
- QuickBooks? Stripe? something else?

### 6.3 Pricing + pilot offer

- Present the pricing model
- Pilot terms: 30–60 day pilot, free or discounted
- Success metrics agreed upfront

### 6.4 Pilot agreement

- **Light-touch:** 1–2 page agreement covering term, scope, success criteria, exit clauses
- Both parties sign before any data import

---

## Phase 7 — Customer onboarding (1–2 weeks)

### 7.1 Pre-kickoff

- Tenant provisioned in production
- Admin user created + invite email sent
- Subscription plan attached
- Welcome email sent

### 7.2 Kickoff meeting (60 min)

- Walk through the platform live
- Confirm onboarding plan + key dates
- Set expectations: pilot duration, communication cadence, escalation path

### 7.3 Data import

**Option A — CSV import**
- Build a quick CSV import tool (~3 days of dev — defer to "should" if not done)
- Templates for: clients, locations, employees, crews, recurring schedules

**Option B — White-glove**
- 2–3 hour session, screen-share, enter data together
- **Recommended for customer #1** — you learn an enormous amount

### 7.4 Training sessions (record for reuse)

Three 45-min sessions:

- **Admin training** — tenant settings, RBAC, billing, reports
- **Manager training** — dispatch, scheduling, invoicing, analytics
- **Employee training** — mobile flow, check-in, task completion

### 7.5 First-week hand-holding

- **Daily 15-min check-in**
- **Shared channel** for ad-hoc questions
- **Watch their telemetry** — are they actually logging in?

### 7.6 Feedback capture

- Shared Linear / Notion / Sheet
- **Don't promise features in the heat of the pilot** — capture, prioritize, communicate later

---

## Phase 8 — Pilot period (30–60 days)

### 8.1 Cadence

- Weekly 30-min check-in with customer
- Internal weekly review of customer metrics
- Bi-weekly feature request review

### 8.2 Issue triage SLA (during pilot)

| Severity | Definition | Response | Resolve |
|---|---|---|---|
| **P0** | App down or data loss | 1 hour | Same day |
| **P1** | Major feature broken | Same business day | 3 business days |
| **P2** | Minor bug or UX issue | 3 business days | Sprint |
| **P3** | Feature request | 1 week ack | Roadmap |

### 8.3 Metrics to track

**Adoption:** DAU/MAU, % employees logged in/week, WOs created/day, check-ins/day, invoices/week, $$ processed
**Quality:** Bug count by severity, customer NPS at day 30, support response/resolution times

### 8.4 Mid-pilot review (day 30)

- Are they using it daily?
- Is data flowing through the platform?
- Have they stopped using their old tools?
- Are blocker bugs still occurring?
- Honest conversation: are we on track for conversion at day 60?

---

## Phase 9 — Pilot → Paid (or kill) decision (1 week)

### 9.1 Go criteria (all must be true)

- ≥80% of WOs in the customer's business flow through the platform
- They've stopped using their old spreadsheets / group chat
- DAU > 70% of their employee headcount
- ≤5 open P1/P2 bugs
- Customer explicitly wants to continue
- Pricing has been validated

### 9.2 Conversion

- Move to paid tier
- Auto-bill via Stripe
- Sign full contract
- Capture testimonial / case study material with permission

### 9.3 No-go

- Run retro: what didn't fit?
- Archive their data (give them export first)
- Refund any pilot fees if applicable
- Update target customer profile based on learnings

---

## Phase 10 — Post-conversion

### 10.1 Reference customer agreement

- Permission to use logo, name, quote
- Case study (mutual review and sign-off)
- Reference call availability for next 5 prospects

### 10.2 Expansion

- Their highest-priority feature requests → top of roadmap
- They become a co-developer of the next features
- Identify referral candidates in their network

### 10.3 Documentation

- Build out customer help library (training session recordings + FAQ from support)
- Write customer #2 onboarding template based on #1's experience

---

## Cost summary

### Monthly recurring

| Item | Cost |
|---|---|
| Fly compute (5 machines across prod + staging) | $50 |
| Fly Postgres (prod + staging) | $40 |
| Upstash Redis (paid) | $10 |
| Postmark email (10k tier) | $15 |
| Cloudflare R2 storage | $5 |
| Sentry Team | $26 |
| Status page (Better Stack Pro) | $29 |
| Help Scout (1 mailbox) | $25 |
| Domain | $1 |
| Insurance (E&O + Cyber liability) | $75 |
| **Subtotal** | **$276/mo** |

### One-time

| Item | Cost |
|---|---|
| Domain registration | $12 |
| Legal review (ToS + Privacy + DPA) | $1,500–3,500 |
| Optional: pen test (Cobalt.io) | $5,000–15,000 |
| LLC formation (if needed) | $50–500 |

### Time cost

- **Engineering:** 4 weeks full-time (Phase 1)
- **Infrastructure + legal + security:** 2 weeks (Phases 2–4, partially parallel)
- **Sales / discovery:** 1–2 weeks
- **Onboarding + pilot launch:** 2 weeks
- **Pilot monitoring:** 30–60 days (10 hr/week)

**Total: 6–10 weeks to first customer live, then 30–60 days pilot.**

---

## Success criteria — when is "production-ready" actually true?

Hard gates (all must be met before going live):

- [ ] All Phase 1 MUST items shipped and tested in staging
- [ ] Backup restore drill completed and timed
- [ ] Pen test or security review completed (findings addressed)
- [ ] Status page live and publicly subscribed
- [ ] Incident runbook written and a tabletop exercise run
- [ ] Insurance policy active
- [ ] Customer signed pilot agreement
- [ ] Domain auth (SPF/DKIM/DMARC) verified via `mxtoolbox.com`
- [ ] First customer admin user can log in and complete the "create WO → assign → check in → mark complete → invoice" loop end-to-end on production

Soft signals (you'll know production is working when):

- One full month of operation with no P0 incidents
- Sentry showing healthy error rate (<0.5% of requests)
- Customer logs in every business day
- Customer has issued and collected on at least one invoice via the platform
- Pilot converted to paid

---

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| First customer churns | Medium | High | Choose a warm intro; over-invest in white-glove onboarding |
| ARQ email delivery breaks silently | Medium | High | Sentry alerting on worker errors + manual queue-depth check daily |
| DB corruption | Low | Critical | Tested restore drill before go-live; daily backups; monitor disk usage |
| Pricing rejected | Medium | High | Validate pricing in discovery, not in the contract phase |
| Eng prerequisites slip past 4 weeks | High | Medium | Cut SHOULD items aggressively; only MUST items block launch |
| Legal review slow | Medium | Medium | Start in parallel with eng, not after |
| Customer's data doesn't fit our model | Medium | High | Discovery call must surface this; if surfaced, defer pilot until model adjusted |
| Compliance request (SOC 2) before ready | Low | High | Have a clear "we're not SOC 2 yet, here's our roadmap" response; audit log is the head start |

---

## What you don't need to do for customer #1 (but will for #5+)

- SOC 2 Type I audit (start the journey in parallel; certification is for customer #5 or when contract requires)
- Self-serve signup
- Subscription tier UI / Stripe portal
- Multi-region active-active
- Mobile native apps
- HIPAA compliance (irrelevant unless you target healthcare-adjacent janitorial)
- White-label tenant branding
