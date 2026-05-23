# POC Issue Tracker

Issues found during manual QA of the deployed POC after Plan A launch. Tracks remediation across sessions.

**Source:** `transcipt_of_issues_on_POC.md` (RBJ walkthrough as Admin/Alex Rivera)
**Date opened:** 2026-05-23
**Tester:** Rodolfo Baez Jr.

---

## Status legend

| Status | Meaning |
|---|---|
| 🔴 Open | Not started |
| 🟡 In Progress | Branch open / PR draft |
| 🟢 Fixed | Merged, verified on deployed POC |
| ⚪ Won't Fix | Out of scope for POC |
| 🔵 Needs Repro | Could not reproduce / needs more info |

## Severity legend

| Severity | Meaning |
|---|---|
| S1 | Crash, data loss, blocking demo path |
| S2 | Feature broken or visibly wrong, demo-impacting |
| S3 | Inconsistency, polish, missing affordance |
| S4 | Verification / test-data gap |

---

## S1 — Critical (crashes, dead routes, blocking demo)

### POC-001 — Locations search crashes app ([#32](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/32))
- **Area:** Locations
- **Status:** 🔴 Open
- **Repro:** Locations page → search "common" → client-side exception screen, browser back button doesn't recover, must re-authenticate.
- **Expected:** Search filters the table; on no-match, show empty state.
- **Accept:** Search works; if error, user can navigate away without re-login.

### POC-002 — `/dashboard/invoices/new` returns "invoice not found or failed to load" ([#33](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/33))
- **Area:** Invoices
- **Status:** 🔴 Open
- **Repro:** Invoices page → "New Invoice" button OR Dashboard → Quick Actions → Generate Invoice → "New".
- **Expected:** Render an invoice creation form.
- **Accept:** Route renders a working create form; submitting persists the invoice.

### POC-003 — `/dashboard/locations/new` returns 404 ([#34](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/34))
- **Area:** Locations
- **Status:** 🔴 Open
- **Repro:** Locations page → "Add Location" → 404 page not found.
- **Expected:** Render a location creation form.
- **Accept:** Route renders form; submit persists and returns to list.

### POC-004 — Locations edit button → 404 ([#35](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/35))
- **Area:** Locations
- **Status:** 🔴 Open
- **Repro:** Locations table → row "Edit" button → 404.
- **Expected:** Either remove the button (preferred — see POC-019) or route to edit form.
- **Accept:** Edit affordance works OR is removed in favor of row click.

### POC-005 — Check-in / check-out flow non-functional ([#36](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/36))
- **Area:** Work Orders
- **Status:** 🔴 Open
- **Repro:** Work order detail → Check In → "not found unavailable". Same for Check Out.
- **Expected:** Geofence + timestamp captured per the original design.
- **Accept:** End-to-end check-in/check-out persists and shows on the work order. (May descope to "demo stub" if real GPS is post-POC — confirm scope.)

### POC-006 — "Mark Complete" fails on some in-progress work orders ([#37](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/37))
- **Area:** Work Orders
- **Status:** 🔴 Open
- **Repro:** Specific case observed: restroom/parking work order — "Mark Complete" no-ops. Other scheduled work orders complete fine.
- **Expected:** Any non-completed work order can be marked complete.
- **Accept:** Mark Complete works regardless of current status (scheduled/in-progress) and current task state.

### POC-007 — Dashboard "Assign Crew" quick action is a dead button ([#38](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/38))
- **Area:** Dashboard
- **Status:** 🔴 Open
- **Repro:** Dashboard → Quick Actions → "Assign Crew" → nothing happens.
- **Expected:** Opens an assign-crew modal or routes to a relevant page.
- **Accept:** Click produces a deliberate action (modal or route) OR button is removed.

### POC-008 — "Create Crew" button non-functional ([#39](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/39))
- **Area:** Crews
- **Status:** 🔴 Open
- **Repro:** Crews page → Create Crew → nothing happens.
- **Expected:** Modal/form to create a new crew with name, lead, members.
- **Accept:** New crews can be created and persist.

---

## S2 — Data correctness

### POC-009 — Locations table shows client UUID instead of client name ([#40](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/40))
- **Area:** Locations
- **Status:** 🔴 Open
- **Repro:** Locations page → "Client" column shows raw UUID.
- **Expected:** Display `client.name` (e.g., "Bay Area Medical").
- **Accept:** Column shows human-readable name; sorting/filtering by client works (see POC-020).

### POC-010 — Location addresses malformed ([#41](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/41))
- **Area:** Locations
- **Status:** 🔴 Open
- **Repro:** Locations page → Address column shows `", Corpus Christi, Texas"` — leading comma, missing street.
- **Expected:** Full street address, or graceful fallback when street is null.
- **Accept:** Either seed fixes missing street data OR rendering hides empty segments cleanly.

### POC-011 — QR code shows literal "token undefined" ([#42](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/42))
- **Area:** Locations
- **Status:** 🔴 Open
- **Repro:** Locations table → QR code column renders text "token undefined".
- **Expected:** Either render a real QR token OR hide the column for POC.
- **Accept:** No `undefined` strings visible to users. If feature isn't built, hide the column.

### POC-012 — Analytics revenue totals don't reconcile ([#43](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/43))
- **Area:** Analytics
- **Status:** 🔴 Open
- **Repro:** Analytics → 30 days → top-line revenue shows $395 but per-client breakdown sums to ~$3,950 (Bay Area $1,948.50 + Harbor View $1,055 + Corpus Christi $947).
- **Expected:** Top-line = sum of breakdown.
- **Accept:** Numbers reconcile across all date windows.

### POC-013 — Completion rate & SLA compliance ignore date filter ([#44](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/44))
- **Area:** Analytics
- **Status:** 🔴 Open
- **Repro:** Analytics → switch between 7/30/60/90 days → completion rate & SLA stay at 75% even though last-7-days crew table shows 100% compliance.
- **Expected:** All KPIs recompute based on the active window.
- **Accept:** Completion rate and SLA recompute and match the underlying data per window.

### POC-014 — Invoice marked "Overdue" on the due date itself ([#45](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/45))
- **Area:** Invoices
- **Status:** 🔴 Open
- **Repro:** Invoice INV-2026-0039 (Harbor View) due today, status "Overdue" at 9:10 CT.
- **Expected:** Due-today is not overdue until the day rolls over in the user's timezone.
- **Accept:** Status compares against tenant timezone (or end-of-day UTC equivalent), not raw UTC.

### POC-015 — Work order schedule date display is confusing ([#46](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/46))
- **Area:** Work Orders
- **Status:** 🔴 Open
- **Repro:** Create work order scheduled for tomorrow 2:10 PM → detail page shows today's date as header with the scheduled date below.
- **Expected:** Header reflects the scheduled date.
- **Accept:** Single, unambiguous scheduled-date display. (Confirm: is the header "created date" — if so, relabel.)

### POC-016 — Completed timestamp rendered as raw ISO ([#47](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/47))
- **Area:** Work Orders
- **Status:** 🔴 Open
- **Repro:** Mark a work order complete → completed timestamp shows e.g. `2026-05-23T14:00:00-0800`.
- **Expected:** Formatted like "Completed May 23, 2026 at 2:00 PM CT".
- **Accept:** All timestamps use a shared date formatter helper with locale + tz.

---

## S3 — UX consistency / missing functionality

### POC-017 — No back button on detail pages ([#48](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/48))
- **Area:** Global navigation
- **Status:** 🔴 Open
- **Repro:** Work order / client / invoice / location detail pages have no back affordance.
- **Expected:** Back button (or breadcrumb) on every detail page.
- **Accept:** Consistent back-nav across all detail views.

### POC-018 — Work Orders filter state doesn't persist on back navigation ([#49](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/49))
- **Area:** Work Orders
- **Status:** 🔴 Open
- **Repro:** Work Orders → filter Urgent → click a row → browser back → filter is cleared.
- **Expected:** Filter persists (URL-driven state).
- **Accept:** Filter state survives back-nav, ideally via query params.

### POC-019 — Table component inconsistency across pages ([#50](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/50))
- **Area:** Work Orders, Clients, Locations, Invoices
- **Status:** 🔴 Open
- **Repro:** Each page uses a different table pattern; some have row click, others a "View" or "Edit" button.
- **Expected:** One shared table component. Rows clickable. No redundant View/Edit buttons.
- **Accept:** All four list pages use the same component; rows are the navigation primitive.

### POC-020 — Locations sort + client filter broken ([#51](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/51))
- **Area:** Locations
- **Status:** 🔴 Open
- **Repro:** Locations → click "Name" column header → no sort. "All Clients" dropdown is empty.
- **Expected:** Sortable columns; client dropdown populated with active clients.
- **Accept:** Both work; ideally addressed alongside POC-019 with the shared table.

### POC-021 — Client detail → service location click goes to generic page ([#52](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/52))
- **Area:** Clients
- **Status:** 🔴 Open
- **Repro:** Client detail (Harbor View) → click a service location → routes to `/dashboard/locations` (list), not the specific location.
- **Expected:** Routes to that location's detail.
- **Accept:** Link target is the location detail page.

### POC-022 — Schedule view missing affordances ([#53](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/53))
- **Area:** Schedule
- **Status:** 🔴 Open
- **Repro:**
  - No jump-to-date control (only week ± nav).
  - No filter for "Completed only" etc.
  - Cards on the calendar are not clickable into the work order.
- **Expected:** Date picker, status filter, clickable cards.
- **Accept:** All three present.

### POC-023 — Schedule "Today" highlights wrong day (timezone) ([#54](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/54))
- **Area:** Schedule
- **Status:** 🔴 Open
- **Repro:** At 9:15 AM CT on Friday, Schedule "today" highlight appears on the wrong day.
- **Expected:** Today reflects tenant timezone.
- **Accept:** Highlight matches the user's local "today".

### POC-024 — Profile and Settings nav both route to Settings/Profile tab ([#55](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/55))
- **Area:** Global navigation
- **Status:** 🔴 Open
- **Repro:** User menu → "Profile" and "Settings" both land on `/dashboard/settings` profile tab.
- **Expected:** Either differentiated routes, or dedupe the menu.
- **Accept:** Decision documented + nav reflects it.

### POC-025 — "New Work Order" duplicated in header + Quick Actions ([#56](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/56))
- **Area:** Dashboard
- **Status:** 🔴 Open
- **Repro:** Dashboard has "New Work Order" both in the top header and in Quick Actions.
- **Expected:** Either keep both deliberately (with intent) or dedupe.
- **Accept:** Design decision documented.

---

## S3 — Invoices polish

### POC-026 — Invoice editing not supported ([#57](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/57))
- **Area:** Invoices
- **Status:** 🔴 Open
- **Repro:** Invoice detail → no way to edit number, line items, etc.
- **Expected:** Edit mode (at least for non-finalized drafts).
- **Accept:** Editable drafts; finalized invoices either locked or versioned.

### POC-027 — Invoice download missing ([#58](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/58))
- **Area:** Invoices
- **Status:** 🔴 Open
- **Repro:** Invoice detail shows a screenshot-style preview; no download.
- **Expected:** PDF download.
- **Accept:** Working "Download PDF" button. (Cross-ref Phase 2 roadmap item "invoice PDF".)

### POC-028 — Redundant "View" button on invoice rows ([#59](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/59))
- **Area:** Invoices
- **Status:** 🔴 Open
- **Repro:** Invoice list rows already navigate on click but also have a View button.
- **Expected:** Drop the button (rolls up into POC-019).
- **Accept:** Removed.

---

## S4 — Verification & test data

### POC-029 — Verify dashboard counts against seed ([#60](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/60))
- **Area:** Dashboard / Seed data
- **Status:** 🔴 Open
- **Repro:** Dashboard shows: 7 active work orders, $538 outstanding, 1 overdue.
- **Action:** Cross-reference against `scripts/seed_demo_data.py` (or equivalent) and confirm.
- **Accept:** Numbers verified or seed adjusted.

### POC-030 — Seed needs variance in SLA compliance across windows ([#61](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/61))
- **Area:** Seed data
- **Status:** 🔴 Open
- **Context:** SLA compliance is static across 7/30/60/90 day windows — even if POC-013 is fixed, the demo won't show movement.
- **Accept:** Seed has historical data with deliberate variance so date-range filter is visibly meaningful.

### POC-031 — Crew membership uniqueness policy ([#62](https://github.com/one-repo-to-rule-them-all/poc_fieldpro/issues/62))
- **Area:** Crews
- **Status:** 🔵 Needs Repro / Decision
- **Context:** Can a worker belong to multiple crews? Observed: Linda is lead on Charlie + member on another. Jordan already appears when adding to Alpha.
- **Action:** Define the business rule, then enforce in UI + API.
- **Accept:** Policy documented; UI prevents invalid states.

---

## Working notes

- All routes verified as Admin (Alex Rivera) only. Manager and Field Worker roles not yet walked through — expect additional issues.
- Cross-ref Phase 2 roadmap items already on the list: invoice PDF (POC-027), crews assignment UI (POC-007/008), shared table component (POC-019).
- "Login screen" and "demo profile selector" walked through with no issues found.

## Change log

| Date | Change |
|---|---|
| 2026-05-23 | Initial tracker from RBJ POC walkthrough transcript. 31 items opened. |
| 2026-05-23 | Mirrored as GitHub issues #32–#62 in `one-repo-to-rule-them-all/poc_fieldpro`. POC-NNN ↔ issue #(NNN + 31). |
