# FieldPro E2E Tests

Playwright end-to-end tests for the FieldPro frontend + backend. Scoped to critical user flows only — not a substitute for the unit/component tests outlined in `docs/proposals/testing-infrastructure-overhaul.md`.

## Quick start

```bash
# From the frontend/ directory, with the full docker compose stack running.

# 1. Install Playwright browsers (one time)
npx playwright install chromium

# 2. Run all specs
npm run test:e2e

# 3. Run a single spec
npx playwright test specs/login-and-create-wo.spec.ts

# 4. Run with UI mode (interactive)
npx playwright test --ui

# 5. View the last HTML report
npx playwright show-report
```

Requires:
- Backend at `http://localhost:8000` (or override via `API_URL=...`)
- Frontend at `http://localhost:3000` (or override via `BASE_URL=...`)
- Demo seed data loaded — `docker compose run --rm backend python scripts/seed_data.py`

## Folder layout

```
e2e/
├── auth.setup.ts            # runs once; logs in admin/manager/employee → .auth/{role}.json
├── .auth/                   # gitignored; per-role storageState JSON
├── fixtures/
│   └── test.ts              # extended `test` with POMs + ApiClient injected as fixtures
├── pages/                   # Page Object Models (one per route or shared component)
│   ├── base.page.ts
│   ├── login.page.ts
│   ├── work-orders-list.page.ts
│   ├── work-order-detail.page.ts
│   └── work-order-form.page.ts
├── specs/                   # the actual tests
│   └── login-and-create-wo.spec.ts
└── support/
    ├── api-client.ts        # authenticated APIRequestContext wrapper for spec setup
    ├── roles.ts             # demo credentials + storage-state paths
    └── selectors.ts         # data-testid constants — the only place to hard-code testids
```

## Conventions

### Page Objects
- One POM per route. Generic UI components (forms, modals) get their own POM and are constructed inside route POMs.
- Concrete POMs extend `BasePage` so they inherit sidebar nav + page header helpers. Non-authenticated pages (like `LoginPage`) don't extend it.
- Locators are getters that return `Locator` — Playwright auto-waits, so no manual `waitForSelector`.
- Actions return `Promise<void>` (or a result when relevant, like `waitForUrlAndExtractId`).
- Keep POMs *thin*. Add a helper method only when 2+ specs would duplicate it.

### Selectors
- All `data-testid` values live in `support/selectors.ts` under `TID`. Specs and POMs reference `TID.xxx`, never hard-coded strings.
- Add a testid to the UI only when an E2E touches that element. Don't sweep the whole codebase preemptively.
- Use `getByRole` / `getByLabel` for accessibility-friendly selectors when no testid exists yet.

### Auth
- `auth.setup.ts` logs in once per role and saves storage state to `.auth/{role}.json`. Specs reuse it via `playwright.config.ts` projects.
- Default role is `admin`. To use another role in a spec: `test.use({ storageState: AUTH_FILE.employee })` at file or describe scope.

### Setup data
- Use the `apiAsAdmin` fixture for spec setup (creating clients, locations, crews, work orders). Going through the UI for setup is 10× slower and couples specs to form regressions.
- Each spec should clean up after itself when possible. If cleanup fails, swallow the error — the per-test isolation is good enough.

### Adding a new spec
1. Pick or create the right POM under `pages/`. Add only the locators and actions your spec needs.
2. If the POM needs new `data-testid` values, add them to `TID` in `selectors.ts` *and* to the React component.
3. Create the spec file under `specs/`.
4. Import `test, expect` from `../fixtures/test`, not from `@playwright/test`.
5. Run locally; ensure it passes 5× in a row before pushing (catches flake).

## Critical flows tracked

| # | Spec | Status |
|---|------|--------|
| 1 | login → create WO → mark complete | ✅ `login-and-create-wo.spec.ts` |
| 2 | reassign crew + verify list reflection | ⏳ planned |
| 3 | field worker → /jobs → check in | ⏳ planned (needs geolocation harness) |

See `docs/proposals/testing-infrastructure-overhaul.md` §4 Phase 6 for the broader plan.
