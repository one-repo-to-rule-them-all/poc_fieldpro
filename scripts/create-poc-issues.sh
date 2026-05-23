#!/usr/bin/env bash
# One-shot script to create POC QA issues from docs/qa/poc-issues.md.
# Writes a mapping of POC-ID -> issue URL to docs/qa/.issue-urls.txt.

set -euo pipefail

OUT="docs/qa/.issue-urls.txt"
: > "$OUT"

create() {
  local poc_id="$1"; shift
  local title="$1"; shift
  local labels="$1"; shift
  local body="$1"; shift

  local url
  url=$(gh issue create --title "$title" --body "$body" $labels)
  echo "$poc_id $url" | tee -a "$OUT"
}

# ============================================================
# S1 — Critical
# ============================================================

create "POC-001" \
  "[POC-001] Locations search crashes app" \
  "--label severity/S1 --label area:locations --label bug" \
  "$(cat <<'EOF'
**Area:** Locations
**Severity:** S1
**Source:** Manual QA walkthrough 2026-05-23 (Admin role)

### Repro
1. Navigate to Locations page.
2. Type `common` in the search box.

### Actual
Client-side exception screen. Browser back button does not recover — user must re-authenticate to escape the error state.

### Expected
Search filters the table; on no-match, an empty state is shown.

### Acceptance
- [ ] Search works without throwing.
- [ ] If an error occurs, user can navigate away without re-login.
EOF
)"

create "POC-002" \
  "[POC-002] /dashboard/invoices/new returns 'invoice not found or failed to load'" \
  "--label severity/S1 --label area:invoices --label bug" \
  "$(cat <<'EOF'
**Area:** Invoices
**Severity:** S1

### Repro
- Invoices page → click **New Invoice**, OR
- Dashboard → Quick Actions → **Generate Invoice** → New.

### Actual
Lands on an error page reading "invoice not found or failed to load".

### Expected
Renders an invoice creation form.

### Acceptance
- [ ] `/dashboard/invoices/new` renders a working create form.
- [ ] Submitting persists the invoice and routes to its detail page.
EOF
)"

create "POC-003" \
  "[POC-003] /dashboard/locations/new returns 404" \
  "--label severity/S1 --label area:locations --label bug" \
  "$(cat <<'EOF'
**Area:** Locations
**Severity:** S1

### Repro
1. Navigate to Locations page.
2. Click **Add Location**.

### Actual
404 page not found.

### Expected
Renders a location creation form.

### Acceptance
- [ ] `/dashboard/locations/new` renders a form.
- [ ] Submit persists the location and returns to the list with the new row visible.
EOF
)"

create "POC-004" \
  "[POC-004] Locations row Edit button → 404" \
  "--label severity/S1 --label area:locations --label bug" \
  "$(cat <<'EOF'
**Area:** Locations
**Severity:** S1

### Repro
1. Locations table → click the row **Edit** button.

### Actual
404 page not found.

### Expected
Either remove the button (preferred — rows should be clickable, see #POC-019) or route to an edit form.

### Acceptance
- [ ] Edit affordance either works end-to-end OR is removed in favor of row click + edit-on-detail-page.

> Likely closed as a side effect of the unified table component work (#POC-019).
EOF
)"

create "POC-005" \
  "[POC-005] Check-in / check-out flow non-functional" \
  "--label severity/S1 --label area:work-orders --label bug" \
  "$(cat <<'EOF'
**Area:** Work Orders
**Severity:** S1

### Repro
- Work order detail → **Check In** → "not found unavailable".
- Same error for **Check Out**.

### Expected
Geofence + timestamp captured per the original design.

### Acceptance
- [ ] End-to-end check-in/check-out persists and is visible on the work order.

> Cross-ref: Phase 2 roadmap item. May descope to a demo stub if real GPS check-in is post-POC — confirm scope.
EOF
)"

create "POC-006" \
  "[POC-006] Mark Complete fails on some in-progress work orders" \
  "--label severity/S1 --label area:work-orders --label bug" \
  "$(cat <<'EOF'
**Area:** Work Orders
**Severity:** S1

### Repro
Observed case: restroom/parking work order — clicking **Mark Complete** is a no-op. Other scheduled work orders complete fine.

### Expected
Any non-completed work order can be marked complete, regardless of current status (scheduled / in-progress).

### Acceptance
- [ ] Mark Complete works for all status transitions.
- [ ] Add a regression test covering scheduled → completed AND in-progress → completed.
EOF
)"

create "POC-007" \
  "[POC-007] Dashboard 'Assign Crew' quick action is a dead button" \
  "--label severity/S1 --label area:dashboard --label bug" \
  "$(cat <<'EOF'
**Area:** Dashboard
**Severity:** S1

### Repro
1. Dashboard → Quick Actions → **Assign Crew**.

### Actual
Nothing happens.

### Expected
Opens an assign-crew modal or routes to a relevant page.

### Acceptance
- [ ] Click produces a deliberate action (modal or route) OR button is removed from the dashboard.
EOF
)"

create "POC-008" \
  "[POC-008] Create Crew button non-functional" \
  "--label severity/S1 --label area:crews --label bug" \
  "$(cat <<'EOF'
**Area:** Crews
**Severity:** S1

### Repro
1. Crews page → click **Create Crew**.

### Actual
Nothing happens.

### Expected
Modal/form to create a new crew with name, lead, members.

### Acceptance
- [ ] New crews can be created via UI and persist.
- [ ] Required fields validated.
EOF
)"

# ============================================================
# S2 — Data correctness
# ============================================================

create "POC-009" \
  "[POC-009] Locations table shows client UUID instead of client name" \
  "--label severity/S2 --label area:locations --label bug" \
  "$(cat <<'EOF'
**Area:** Locations
**Severity:** S2

### Repro
Locations page → **Client** column shows raw UUID strings.

### Expected
Display `client.name` (e.g., "Bay Area Medical").

### Acceptance
- [ ] Column shows the human-readable client name.
- [ ] Sorting / filtering by client works (see #POC-020).
EOF
)"

create "POC-010" \
  "[POC-010] Location addresses malformed (leading comma, missing street)" \
  "--label severity/S2 --label area:locations --label bug" \
  "$(cat <<'EOF'
**Area:** Locations
**Severity:** S2

### Repro
Locations page → Address column shows e.g. `, Corpus Christi, Texas` (leading comma, missing street).

### Expected
Full street address, or a graceful fallback when the street is null.

### Acceptance
- [ ] Either seed has correct street data OR the renderer hides empty segments cleanly.
- [ ] No stray punctuation visible.
EOF
)"

create "POC-011" \
  "[POC-011] QR code column shows literal 'token undefined'" \
  "--label severity/S2 --label area:locations --label bug" \
  "$(cat <<'EOF'
**Area:** Locations
**Severity:** S2

### Repro
Locations table → QR code column renders the text `token undefined`.

### Expected
Either render a real QR token OR hide the column for POC.

### Acceptance
- [ ] No `undefined` strings visible anywhere in the UI.
- [ ] If the feature isn't built yet, hide the column.
EOF
)"

create "POC-012" \
  "[POC-012] Analytics revenue totals don't reconcile across breakdown" \
  "--label severity/S2 --label area:analytics --label bug" \
  "$(cat <<'EOF'
**Area:** Analytics
**Severity:** S2

### Repro
Analytics → 30 days.
- Top-line revenue: **\$395**
- Per-client breakdown sums to ~**\$3,950**:
  - Bay Area Medical: \$1,948.50
  - Harbor View: \$1,055
  - Corpus Christi: \$947

### Expected
Top-line revenue = sum of breakdown for the selected window.

### Acceptance
- [ ] Numbers reconcile across all date windows (7 / 30 / 60 / 90).
- [ ] Add a guard test that asserts equality.
EOF
)"

create "POC-013" \
  "[POC-013] Completion rate & SLA compliance ignore the date filter" \
  "--label severity/S2 --label area:analytics --label bug" \
  "$(cat <<'EOF'
**Area:** Analytics
**Severity:** S2

### Repro
Analytics → switch between 7 / 30 / 60 / 90 days. Completion rate and SLA stay at **75%**, even though the last-7-days crew table shows **100%** compliance.

### Expected
All KPIs recompute based on the active window.

### Acceptance
- [ ] Completion rate and SLA recompute per window.
- [ ] Values match the underlying data (seed needs variance — see #POC-030).
EOF
)"

create "POC-014" \
  "[POC-014] Invoice marked 'Overdue' on the due date itself (timezone bug)" \
  "--label severity/S2 --label area:invoices --label bug" \
  "$(cat <<'EOF'
**Area:** Invoices
**Severity:** S2

### Repro
Invoice INV-2026-0039 (Harbor View) — due date is **today**, status shows **Overdue** at 9:10 AM CT.

### Expected
Due-today is not overdue until the day rolls over in the user's / tenant timezone.

### Suspected cause
Status comparison happening in UTC instead of tenant tz.

### Acceptance
- [ ] Overdue logic compares against tenant timezone (or end-of-day UTC equivalent).
- [ ] Unit test covering the timezone boundary.
EOF
)"

create "POC-015" \
  "[POC-015] Work order schedule date display is confusing" \
  "--label severity/S2 --label area:work-orders --label bug" \
  "$(cat <<'EOF'
**Area:** Work Orders
**Severity:** S2

### Repro
1. Create a work order scheduled for tomorrow at 2:10 PM.
2. Open its detail page.

### Actual
Header shows today's date; the actual scheduled date appears below.

### Expected
Header reflects the scheduled date. (If the header is actually showing the created-on date, relabel it.)

### Acceptance
- [ ] Single, unambiguous scheduled-date display.
- [ ] Labels distinguish "Scheduled for" vs "Created on" if both are present.
EOF
)"

create "POC-016" \
  "[POC-016] Completed timestamp renders as raw ISO string" \
  "--label severity/S2 --label area:work-orders --label bug" \
  "$(cat <<'EOF'
**Area:** Work Orders
**Severity:** S2

### Repro
Mark any work order complete → the completed timestamp displays as e.g. \`2026-05-23T14:00:00-0800\`.

### Expected
Formatted, e.g. "Completed May 23, 2026 at 2:00 PM CT".

### Acceptance
- [ ] All timestamps use a shared date formatter helper with locale + timezone.
- [ ] No raw ISO strings visible in the UI.
EOF
)"

# ============================================================
# S3 — UX consistency / polish
# ============================================================

create "POC-017" \
  "[POC-017] No back button on detail pages" \
  "--label severity/S3 --label area:nav --label enhancement" \
  "$(cat <<'EOF'
**Area:** Global navigation
**Severity:** S3

### Repro
Work order / client / invoice / location detail pages have no back affordance.

### Expected
Back button (or breadcrumb) on every detail page.

### Acceptance
- [ ] Consistent back-nav across all detail views.
- [ ] Back behavior preserves prior list filters (see #POC-018).
EOF
)"

create "POC-018" \
  "[POC-018] Work Orders filter state doesn't persist on back navigation" \
  "--label severity/S3 --label area:work-orders --label enhancement" \
  "$(cat <<'EOF'
**Area:** Work Orders
**Severity:** S3

### Repro
1. Work Orders → filter by **Urgent**.
2. Click a row to open detail.
3. Browser back.

### Actual
Filter is cleared.

### Expected
Filter persists (URL-driven state).

### Acceptance
- [ ] Filter state survives back-nav, ideally via query params.
- [ ] Direct link to a filtered list works (copy-paste URL preserves filter).
EOF
)"

create "POC-019" \
  "[POC-019] Unify table component across Work Orders / Clients / Locations / Invoices" \
  "--label severity/S3 --label area:nav --label enhancement" \
  "$(cat <<'EOF'
**Area:** Work Orders, Clients, Locations, Invoices
**Severity:** S3

### Problem
Each list page uses a different table pattern; some have row click, others a "View" or "Edit" button. Inconsistent UX.

### Expected
One shared table component. Rows are the navigation primitive. No redundant View/Edit buttons.

### Acceptance
- [ ] All four list pages use the same component.
- [ ] Row click → detail page is the standard interaction.
- [ ] View/Edit row buttons removed.

> Likely closes #POC-004 (locations Edit 404), #POC-020 (sort + filter), #POC-028 (redundant View button) as side effects.
EOF
)"

create "POC-020" \
  "[POC-020] Locations: column sort + 'All Clients' filter broken" \
  "--label severity/S3 --label area:locations --label bug" \
  "$(cat <<'EOF'
**Area:** Locations
**Severity:** S3

### Repro
- Click the **Name** column header → no sort.
- Open the **All Clients** dropdown → empty.

### Expected
Sortable columns; client dropdown populated with active clients.

### Acceptance
- [ ] Sort works on all sortable columns.
- [ ] Client dropdown populated from the clients API.
- [ ] Ideally addressed alongside the unified table component (#POC-019).
EOF
)"

create "POC-021" \
  "[POC-021] Client detail → service location click routes to generic locations page" \
  "--label severity/S3 --label area:clients --label bug" \
  "$(cat <<'EOF'
**Area:** Clients
**Severity:** S3

### Repro
1. Open a client detail (e.g., Harbor View).
2. Click one of its service locations.

### Actual
Routes to \`/dashboard/locations\` (the list), not the specific location.

### Expected
Routes to that location's detail page.

### Acceptance
- [ ] Link target is the location detail page.
EOF
)"

create "POC-022" \
  "[POC-022] Schedule view missing affordances (date picker, filter, click-through)" \
  "--label severity/S3 --label area:schedule --label enhancement" \
  "$(cat <<'EOF'
**Area:** Schedule
**Severity:** S3

### Missing
- No jump-to-date control (only week ± nav).
- No status filter (e.g., "Completed only").
- Calendar cards are not clickable into the work order.

### Acceptance
- [ ] Date picker added.
- [ ] Status filter added.
- [ ] Cards link to the underlying work order detail.
EOF
)"

create "POC-023" \
  "[POC-023] Schedule 'Today' highlights wrong day (timezone)" \
  "--label severity/S3 --label area:schedule --label bug" \
  "$(cat <<'EOF'
**Area:** Schedule
**Severity:** S3

### Repro
At 9:15 AM CT on Friday, the Schedule "today" highlight appears on a different day.

### Expected
Today reflects the tenant / user timezone.

### Acceptance
- [ ] Highlight matches the user's local "today" across timezones.
EOF
)"

create "POC-024" \
  "[POC-024] Profile and Settings nav both route to Settings/Profile tab" \
  "--label severity/S3 --label area:nav --label enhancement" \
  "$(cat <<'EOF'
**Area:** Global navigation
**Severity:** S3

### Repro
User menu → **Profile** and **Settings** both land on \`/dashboard/settings\` (profile tab).

### Expected
Either differentiated routes, or dedupe the menu.

### Acceptance
- [ ] Decision documented (one route or two).
- [ ] Nav updated to reflect the decision.
EOF
)"

create "POC-025" \
  "[POC-025] 'New Work Order' duplicated in header and Quick Actions" \
  "--label severity/S3 --label area:dashboard --label enhancement" \
  "$(cat <<'EOF'
**Area:** Dashboard
**Severity:** S3

### Observation
Dashboard has **New Work Order** both in the top header and in Quick Actions.

### Acceptance
- [ ] Design decision documented (keep both deliberately, or dedupe).
- [ ] UI reflects the decision.
EOF
)"

create "POC-026" \
  "[POC-026] Invoice editing not supported" \
  "--label severity/S3 --label area:invoices --label enhancement" \
  "$(cat <<'EOF'
**Area:** Invoices
**Severity:** S3

### Observation
Invoice detail provides no way to edit number, line items, etc.

### Expected
Edit mode (at least for non-finalized drafts).

### Acceptance
- [ ] Draft invoices are editable.
- [ ] Finalized invoices are either locked or versioned (decision documented).
EOF
)"

create "POC-027" \
  "[POC-027] Invoice download missing" \
  "--label severity/S3 --label area:invoices --label enhancement" \
  "$(cat <<'EOF'
**Area:** Invoices
**Severity:** S3

### Observation
Invoice detail shows a screenshot-style preview; no download.

### Expected
PDF download.

### Acceptance
- [ ] Working **Download PDF** button.

> Cross-ref: Phase 2 roadmap item "invoice PDF".
EOF
)"

create "POC-028" \
  "[POC-028] Redundant 'View' button on invoice rows" \
  "--label severity/S3 --label area:invoices --label enhancement" \
  "$(cat <<'EOF'
**Area:** Invoices
**Severity:** S3

### Observation
Invoice list rows already navigate on click but also display a redundant **View** button.

### Acceptance
- [ ] View button removed.
- [ ] Rolls up into the unified table work (#POC-019).
EOF
)"

# ============================================================
# S4 — Verification & decisions
# ============================================================

create "POC-029" \
  "[POC-029] Verify dashboard counts against seed data" \
  "--label severity/S4 --label area:dashboard --label area:seed" \
  "$(cat <<'EOF'
**Area:** Dashboard / Seed data
**Severity:** S4

### Observed numbers
- Active work orders: **7**
- Outstanding: **\$538**
- Overdue: **1**

### Action
Cross-reference against the seed script and confirm.

### Acceptance
- [ ] Numbers verified OR seed adjusted to make them sensible for a demo.
EOF
)"

create "POC-030" \
  "[POC-030] Seed data needs variance in SLA compliance across windows" \
  "--label severity/S4 --label area:seed --label area:analytics" \
  "$(cat <<'EOF'
**Area:** Seed data
**Severity:** S4

### Context
SLA compliance is static across 7 / 30 / 60 / 90 day windows. Even after #POC-013 is fixed, the demo won't show movement because there is no historical variance.

### Acceptance
- [ ] Seed includes historical data with deliberate variance.
- [ ] Date-range filter is visibly meaningful in the analytics view.
EOF
)"

create "POC-031" \
  "[POC-031] Define crew membership uniqueness policy" \
  "--label severity/S4 --label area:crews --label question" \
  "$(cat <<'EOF'
**Area:** Crews
**Severity:** S4 (decision)

### Context
Observed:
- Linda is a **lead** on Charlie crew AND a **member** on another crew.
- Jordan already appears when attempting to add him to Alpha — implying he's already on a crew.

### Question
Can a worker belong to multiple crews? Can someone be a lead on one and a member on another?

### Acceptance
- [ ] Business rule documented.
- [ ] UI prevents invalid states (whatever those end up being).
- [ ] API enforces the rule.
EOF
)"

echo "Done. URL mapping written to $OUT"
