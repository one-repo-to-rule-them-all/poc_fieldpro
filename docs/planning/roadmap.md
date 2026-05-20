# Roadmap

**Current focus:** Plan A — ship the public showcase demo to a live URL.
**Next milestone after that:** Plan B — production-ready first client onboarding.

---

## Active milestone — Plan A: Public Showcase Demo

**Why now:** This repo is the polished snapshot of the MVP Phase 1 build. Shipping it to a live demo URL converts the "yeah it builds" pitch into "click here." Cheap (~$1/mo), fast (~1 working day), low risk.

**Target:** Live demo at a public URL within 1 week of starting.

**Detailed plan:** [Deployment Plan A — Public Showcase Demo](./deployment-plan-a-showcase-demo.md)

### Plan A phases

| Phase | Description | Status | Notes |
|---|---|---|---|
| 0 | Prerequisites (Fly account + payment, `flyctl` install) | ⏳ Not started | Owner action — needs ~15 min |
| 1 | Provision Postgres + Redis on Fly | ⏳ Not started | Depends on Phase 0 |
| 2 | Deploy backend + migrate + seed | ⏳ Not started | |
| 3 | Deploy frontend (with `NEXT_PUBLIC_API_URL` build-arg fix) | ⏳ Not started | |
| 4 | Custom domain (optional) | ⏳ Not started | Skip if `*.fly.dev` is fine for now |
| 5 | Nightly demo data reset | ⏳ Not started | Can pre-write `reset_demo.py` |
| 6 | UX polish: demo banner, quick-login buttons, disable signup, robots.txt | ⏳ Not started | Can pre-write code; deploy with Phase 3 |
| 7 | Monitoring: Sentry + UptimeRobot | ⏳ Not started | |
| 8 | CI/CD via GitHub Actions | ⏳ Not started | Workflow file already in repo; needs `FLY_API_TOKEN` |
| 9 | Final verification checklist | ⏳ Not started | |

**Graduation criterion → Plan B:** Demo has been live and stable for ≥2 weeks AND a specific business owner has signaled real interest in being customer #1.

---

## Next milestone — Plan B: Production First-Client Onboarding

**Why deferred:** 6–10 weeks of work and $150–250/mo; no point starting before a real customer is identified.

**Detailed plan:** [Deployment Plan B — Production First-Client Onboarding](./deployment-plan-b-production-onboarding.md)

**Trigger to start:** First customer identified + pricing decided + 4–6 weeks of focused engineering time available.

---

## Reference

- **Repo README**: [`../../README.md`](../../README.md) — what FieldPro does + MVP Phase 1 capability matrix
- **Architecture doc**: [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md)
- **Showcase repo**: https://github.com/one-repo-to-rule-them-all/poc_fieldpro

---

## Status log

- **2026-05-19** — Roadmap created. Plan A and Plan B docs written. Showcase repo `poc_fieldpro` published, fresh-clone smoke test passed end-to-end. Plan A locked in as next active work.
