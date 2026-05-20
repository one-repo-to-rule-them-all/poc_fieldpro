# Demo Smoke Test Runbook

**Purpose:** verify the public demo (`fieldpro-poc.fly.dev` + `fieldpro-poc-backend.fly.dev`) is healthy after every deploy, nightly reset, or unexpected outage. Designed to be run start-to-finish in **~5 minutes** with no prior context.

**Last verified:** 2026-05-20

---

## 0. Pre-flight

You need:
- A terminal at any working directory (commands are dir-agnostic)
- `flyctl` installed and authenticated (`flyctl auth whoami` should return your email)
- Network access to `*.fly.dev`
- ~5 minutes

You do **not** need a checked-out repo for this runbook. Everything works against the live URLs.

If you'd rather run a single automated script that does the equivalent of sections 1–5, see [Section 9](#9-automated-equivalent) — the repo ships a `scripts/smoke_test.py` you can run with no dependencies beyond Python stdlib.

---

## 1. Backend liveness (30 sec)

### 1.1 Health endpoint returns ok

**Command (PowerShell):**

```powershell
Invoke-RestMethod https://fieldpro-poc-backend.fly.dev/health
```

**Expected response:**

```
status      : ok
db          : ok
redis       : ok
version     : 1.0.0
environment : production
```

**If it fails:**
- `db: error` → Postgres is down or asleep. Run `flyctl status --app fieldpro-poc-db`. If state is `stopped`, run `flyctl machine start --app fieldpro-poc-db`. Wait 30 sec, retry.
- `redis: error` → Upstash redis is unreachable. Check the Upstash dashboard via Fly: `flyctl redis list`. Rare — usually an Upstash incident, not us.
- No response / timeout → Fly app is down. Run `flyctl status --app fieldpro-poc-backend`. If machine is `stopped`, start it.

### 1.2 First-byte latency under 1.5 sec

**Command:**

```powershell
Measure-Command { Invoke-RestMethod https://fieldpro-poc-backend.fly.dev/health }
```

Expected `TotalSeconds`: < 1.5 (cold-start may be ~3 sec — re-run once if so).

---

## 2. Auth + role personas (60 sec)

### 2.1 Admin login returns tokens

**Command:**

```powershell
$login = Invoke-RestMethod -Method Post `
  -Uri https://fieldpro-poc-backend.fly.dev/api/v1/auth/login `
  -ContentType 'application/json' `
  -Body '{"email":"admin@demo.fieldpro.app","password":"Admin123!"}'
$login | Format-List
```

**Expected:** A response with `access_token`, `refresh_token`, `token_type: bearer`, a `user` object (Alex Rivera, tenant_admin role), and a `tenant` object (Demo Janitorial Co).

### 2.2 All three personas authenticate

```powershell
@(
  @{e='admin@demo.fieldpro.app';   p='Admin123!'   },
  @{e='manager@demo.fieldpro.app'; p='Manager123!' },
  @{e='carlos@demo.fieldpro.app';  p='Employee123!'}
) | ForEach-Object {
  try {
    $r = Invoke-RestMethod -Method Post `
      -Uri https://fieldpro-poc-backend.fly.dev/api/v1/auth/login `
      -ContentType 'application/json' `
      -Body (@{email=$_.e; password=$_.p} | ConvertTo-Json)
    "OK  $($_.e)  role=$($r.user.role)"
  } catch {
    "FAIL $($_.e)  $($_.Exception.Message)"
  }
}
```

**Expected:** Three `OK` lines with roles `tenant_admin`, `manager`, `employee`.

### 2.3 Wrong password is rejected

```powershell
try {
  Invoke-RestMethod -Method Post `
    -Uri https://fieldpro-poc-backend.fly.dev/api/v1/auth/login `
    -ContentType 'application/json' `
    -Body '{"email":"admin@demo.fieldpro.app","password":"WRONG"}'
  "FAIL — wrong password was accepted!"
} catch {
  if ($_.Exception.Response.StatusCode -eq 401) { "OK 401 returned for wrong password" }
  else { "FAIL got $($_.Exception.Response.StatusCode)" }
}
```

**Expected:** `OK 401 returned for wrong password`.

---

## 3. Data integrity (60 sec)

Use the admin token from step 2.1.

```powershell
$h = @{ Authorization = "Bearer $($login.access_token)" }
```

### 3.1 All seeded collections present with expected counts

```powershell
$expected = @{
  'work-orders' = 14   # Note: may show 14-20 if smoke tests created extras
  'clients'     = 3
  'locations'   = 7
  'crews'       = 3
  'invoices'    = 5
}
foreach ($k in $expected.Keys) {
  $r = Invoke-RestMethod -Uri "https://fieldpro-poc-backend.fly.dev/api/v1/$k" -Headers $h
  $count = if ($r.items) { $r.items.Count } else { $r.Count }
  $min = $expected[$k]
  if ($count -ge $min) { "OK  $k = $count (expected >= $min)" }
  else { "FAIL $k = $count (expected >= $min)" }
}
```

**Expected:** Five `OK` lines. If a count is too low → seed didn't run or DB was reset and not re-seeded. Run `flyctl ssh console --app fieldpro-poc-backend -C "python scripts/seed_data.py"` to reseed.

### 3.2 Work order status mix matches seed

```powershell
foreach ($status in 'scheduled','in_progress','completed','draft','on_hold','cancelled') {
  $r = Invoke-RestMethod -Uri "https://fieldpro-poc-backend.fly.dev/api/v1/work-orders?status=$status" -Headers $h
  "  $status = $($r.items.Count)"
}
```

**Expected** (from seed):
```
  scheduled = 5
  in_progress = 2
  completed = 5 (or 6 if you've manually completed any during smoke tests)
  draft = 2
  on_hold = 1
  cancelled = 1
```

### 3.3 Detail endpoints render with related data

```powershell
$wos = (Invoke-RestMethod -Uri "https://fieldpro-poc-backend.fly.dev/api/v1/work-orders" -Headers $h).items
$detail = Invoke-RestMethod -Uri "https://fieldpro-poc-backend.fly.dev/api/v1/work-orders/$($wos[0].id)" -Headers $h
if ($detail.client_name -and $detail.location_name) { "OK  WO detail has client + location" }
else { "FAIL WO detail missing related data" }
```

**Expected:** `OK  WO detail has client + location`.

---

## 4. Write paths (60 sec)

### 4.1 Admin can create a client with a valid industry enum

```powershell
$payload = @{
  name='Smoke Test Co'; code='SMK'; industry='janitorial'
  billing_email='billing@smoke.test'; is_active=$true
} | ConvertTo-Json
$created = Invoke-RestMethod -Method Post `
  -Uri https://fieldpro-poc-backend.fly.dev/api/v1/clients `
  -Headers $h -ContentType 'application/json' -Body $payload
"OK created client id=$($created.id)"
```

**Expected:** `OK created client id=<uuid>`.

### 4.2 Bad industry value is rejected

```powershell
$badPayload = @{
  name='Bad'; code='BAD'; industry='Commercial Real Estate'
  billing_email='a@b.c'; is_active=$true
} | ConvertTo-Json
try {
  Invoke-RestMethod -Method Post `
    -Uri https://fieldpro-poc-backend.fly.dev/api/v1/clients `
    -Headers $h -ContentType 'application/json' -Body $badPayload
  "FAIL — invalid industry accepted!"
} catch {
  if ($_.Exception.Response.StatusCode -eq 422) { "OK 422 returned for invalid enum" }
}
```

**Expected:** `OK 422 returned for invalid enum`.

### 4.3 Cleanup — delete the test client

```powershell
Invoke-RestMethod -Method Delete `
  -Uri "https://fieldpro-poc-backend.fly.dev/api/v1/clients/$($created.id)" `
  -Headers $h
"OK cleanup done"
```

---

## 5. Role-based access control (30 sec)

### 5.1 Field worker is blocked from creating clients

```powershell
$emp = Invoke-RestMethod -Method Post `
  -Uri https://fieldpro-poc-backend.fly.dev/api/v1/auth/login `
  -ContentType 'application/json' `
  -Body '{"email":"carlos@demo.fieldpro.app","password":"Employee123!"}'
$empH = @{ Authorization = "Bearer $($emp.access_token)" }
try {
  Invoke-RestMethod -Method Post `
    -Uri https://fieldpro-poc-backend.fly.dev/api/v1/clients `
    -Headers $empH -ContentType 'application/json' `
    -Body '{"name":"X","code":"X","industry":"janitorial","billing_email":"a@b.c","is_active":true}'
  "FAIL — employee was allowed to create client!"
} catch {
  if ($_.Exception.Response.StatusCode -eq 403) { "OK 403 returned for employee write" }
}
```

**Expected:** `OK 403 returned for employee write`.

### 5.2 Field worker can still read work orders

```powershell
$r = Invoke-RestMethod -Uri "https://fieldpro-poc-backend.fly.dev/api/v1/work-orders" -Headers $empH
"OK employee read $($r.items.Count) WOs"
```

**Expected:** `OK employee read N WOs` where N ≥ 14.

---

## 6. Frontend smoke (90 sec, browser)

### 6.1 Login page loads and renders

Open https://fieldpro-poc.fly.dev/login in a browser. Verify:

- [ ] Page loads in < 3 sec (Network tab → no requests pending after 3s)
- [ ] No console errors in DevTools (F12 → Console)
- [ ] Three demo quick-login buttons visible under the form: **Admin**, **Manager**, **Field worker**

### 6.2 Quick-login works

Click **Admin** quick-login. Verify:

- [ ] Redirected to `/dashboard`
- [ ] Amber demo banner is visible at the top
- [ ] Top-right shows "Alex Rivera" (admin user)
- [ ] Dashboard renders (some KPI cards may be blank — see Known Issues)

### 6.3 Work-orders + clients render with data

Navigate to:

- [ ] `/dashboard/work-orders` — shows ≥ 14 work orders, mixed statuses visible
- [ ] `/dashboard/clients` — shows ≥ 3 clients (Bay Area Medical Center, City of CC, Harbor View)
- [ ] `/dashboard/crews` — shows 3 crews (Alpha, Bravo, Charlie)
- [ ] `/dashboard/invoices` — shows 5 invoices, statuses include PAID and OVERDUE

### 6.4 Sign-up is disabled

Navigate to https://fieldpro-poc.fly.dev/register. Verify:

- [ ] Page shows "Sign-up disabled" message, NOT a real registration form

---

## 7. Pass / fail criteria

**The demo is healthy if:**

- All of sections 1–5 return `OK` (zero `FAIL` lines)
- All of section 6's checkboxes pass

**The demo is degraded but usable if:**

- Section 1.1 returns `status: degraded` but with a `200` HTTP status — usually means one of db/redis is briefly unreachable. Re-run after 30 sec.
- The dashboard KPI endpoint (`/api/v1/analytics/dashboard`) returns 500 — this is a known issue. Other analytics endpoints work, and the rest of the demo is unaffected.

**The demo is broken if:**

- Section 1.1 doesn't return any response (Fly app down)
- Section 2.1 (admin login) returns anything other than 200 with tokens
- Sections 3.1 shows wildly wrong counts (likely DB schema drift or seed never ran)

---

## 8. When you suspect a real outage

1. **First check Fly status:** `flyctl status --app fieldpro-poc-backend` and `flyctl status --app fieldpro-poc-db` — anything `stopped` is the lead suspect.
2. **Then logs:** `flyctl logs --app fieldpro-poc-backend` (Ctrl+C after ~10 lines of output).
3. **Then restart, in this order:**
   1. Postgres: `flyctl machine start --app fieldpro-poc-db`
   2. Backend: `flyctl machine restart <id> --app fieldpro-poc-backend`
   3. Frontend: `flyctl machine restart <id> --app fieldpro-poc`
4. **If still broken:** check the Fly status page at https://status.flyctl.io.

---

## 9. Automated equivalent

The Python equivalent of sections 1–5 lives at [`scripts/smoke_test.py`](../../scripts/smoke_test.py) in this repo. Run with:

```powershell
python scripts/smoke_test.py
```

It uses only Python stdlib. Targets the deployed demo by default; override with `--base http://localhost:8000` to test a local stack, or with `--admin-email`/`--admin-password` for other environments. Exit code 0 = all pass, 1 = at least one failure.

Example:

```
$ python scripts/smoke_test.py
FieldPro smoke test against https://fieldpro-poc-backend.fly.dev

=== Auth ===
  [PASS] 200  Login as admin
  [PASS] 200  Login as manager
  [PASS] 200  Login as field worker
  [PASS] 401  Wrong password -> 401
  [PASS] 401  Unauth GET -> 401

=== Health ===
  [PASS] 200  GET /health (db=ok redis=ok)

=== Collection endpoints ===
  [PASS] 200  GET /api/v1/work-orders            (16 items)
  ...

Result: 28 passed, 1 failed
Failures:
  - GET /api/v1/analytics/dashboard
```
