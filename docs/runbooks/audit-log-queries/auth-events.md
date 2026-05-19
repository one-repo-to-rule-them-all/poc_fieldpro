# Auth event queries

Queries against the 5 auth events captured by Phase 2 of the audit log work:
`login`, `login_failed`, `logout`, `tenant_registered`, `password_reset`.

See [README.md](README.md) for how to run any of these.

---

## 1. Recent auth activity

> Use case: smoke-check — "is auth logging actually working right now?"

```sql
SELECT
  action,
  resource_type,
  COALESCE(user_id::text, '<null>') AS user_id,
  ip_address,
  LEFT(user_agent, 40) AS ua,
  created_at
FROM audit_logs
WHERE action IN ('login', 'login_failed', 'logout', 'tenant_registered', 'password_reset')
  AND created_at > NOW() - INTERVAL '15 minutes'
ORDER BY created_at;
```

PowerShell:

```powershell
docker exec fieldpro_postgres psql -U fieldpro -d fieldpro -c "SELECT action, resource_type, COALESCE(user_id::text,'<null>') AS user_id, ip_address, LEFT(user_agent,40) AS ua, created_at FROM audit_logs WHERE action IN ('login','login_failed','logout','tenant_registered','password_reset') AND created_at > NOW() - INTERVAL '15 minutes' ORDER BY created_at;"
```

Expected when working: at least one row per recent auth interaction. Empty result = no recent activity (not a bug).

---

## 2. Failed login attempts in the last 24 hours

> Use case: daily security review — "any brute-force activity overnight?"

```sql
SELECT
  COALESCE(user_id::text, '<unknown email>') AS targeted_user,
  ip_address,
  COUNT(*) AS attempts,
  MIN(created_at) AS first_attempt,
  MAX(created_at) AS last_attempt
FROM audit_logs
WHERE action = 'login_failed'
  AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY user_id, ip_address
ORDER BY attempts DESC, last_attempt DESC;
```

PowerShell:

```powershell
docker exec fieldpro_postgres psql -U fieldpro -d fieldpro -c "SELECT COALESCE(user_id::text,'<unknown email>') AS targeted_user, ip_address, COUNT(*) AS attempts, MIN(created_at) AS first_attempt, MAX(created_at) AS last_attempt FROM audit_logs WHERE action='login_failed' AND created_at > NOW() - INTERVAL '24 hours' GROUP BY user_id, ip_address ORDER BY attempts DESC, last_attempt DESC;"
```

What to look for:
- `<unknown email>` rows with high `attempts` from a single IP → email scanner
- A specific `user_id` with high `attempts` from one IP → targeted credential stuffing
- High `attempts` from one IP across multiple `targeted_user` values → spray attack

---

## 3. Login attempt timeline for one user

> Use case: incident response — "user X says someone got into their account; what did we see?"

Replace `<user-uuid>` with the user's UUID.

```sql
SELECT
  action,
  ip_address,
  LEFT(user_agent, 60) AS ua,
  created_at
FROM audit_logs
WHERE user_id = '<user-uuid>'
  AND action IN ('login', 'login_failed', 'logout', 'password_reset')
ORDER BY created_at DESC
LIMIT 100;
```

PowerShell (with admin user as example):

```powershell
$userId = "95b8337a-3fe9-415d-ac8f-8d2017c3d59c"
docker exec fieldpro_postgres psql -U fieldpro -d fieldpro -c "SELECT action, ip_address, LEFT(user_agent,60) AS ua, created_at FROM audit_logs WHERE user_id='$userId' AND action IN ('login','login_failed','logout','password_reset') ORDER BY created_at DESC LIMIT 100;"
```

What to look for:
- `login` from a new `ip_address` you don't recognize
- `password_reset` followed shortly by a `login` from a different IP than usual
- `login` events between user-reported "I wasn't using the app" times

---

## 4. Top 10 IPs by failed login activity (last 7 days)

> Use case: identify abusive sources to potentially rate-limit or block at the edge.

```sql
SELECT
  ip_address,
  COUNT(*) AS failed_attempts,
  COUNT(DISTINCT user_id) AS unique_targets,
  MIN(created_at) AS first_seen,
  MAX(created_at) AS last_seen
FROM audit_logs
WHERE action = 'login_failed'
  AND created_at > NOW() - INTERVAL '7 days'
GROUP BY ip_address
ORDER BY failed_attempts DESC
LIMIT 10;
```

PowerShell:

```powershell
docker exec fieldpro_postgres psql -U fieldpro -d fieldpro -c "SELECT ip_address, COUNT(*) AS failed_attempts, COUNT(DISTINCT user_id) AS unique_targets, MIN(created_at) AS first_seen, MAX(created_at) AS last_seen FROM audit_logs WHERE action='login_failed' AND created_at > NOW() - INTERVAL '7 days' GROUP BY ip_address ORDER BY failed_attempts DESC LIMIT 10;"
```

What to look for:
- `unique_targets` > 5 from a single IP with high `failed_attempts` → credential stuffing
- `failed_attempts` > 100 from one IP regardless of unique_targets → brute force on known accounts

---

## 5. Hourly failed-login rate

> Use case: anomaly detection — is the failure rate spiking compared to baseline?

```sql
SELECT
  DATE_TRUNC('hour', created_at) AS hour,
  COUNT(*) AS failed_logins,
  COUNT(DISTINCT ip_address) AS unique_ips,
  COUNT(DISTINCT user_id) AS unique_targeted_users
FROM audit_logs
WHERE action = 'login_failed'
  AND created_at > NOW() - INTERVAL '48 hours'
GROUP BY DATE_TRUNC('hour', created_at)
ORDER BY hour DESC;
```

PowerShell:

```powershell
docker exec fieldpro_postgres psql -U fieldpro -d fieldpro -c "SELECT DATE_TRUNC('hour', created_at) AS hour, COUNT(*) AS failed_logins, COUNT(DISTINCT ip_address) AS unique_ips, COUNT(DISTINCT user_id) AS unique_targeted_users FROM audit_logs WHERE action='login_failed' AND created_at > NOW() - INTERVAL '48 hours' GROUP BY DATE_TRUNC('hour',created_at) ORDER BY hour DESC;"
```

What to look for:
- A specific hour with `failed_logins` >> the typical baseline → attack window
- `unique_ips` and `failed_logins` rising together → distributed brute force

---

## 6. Login → logout session pairs for one user

> Use case: reconstruct when a user was actually using the app (session-equivalent), useful for billing disputes or "was X logged in at the time of Y" questions.

```sql
WITH events AS (
  SELECT
    created_at,
    action,
    ip_address,
    ROW_NUMBER() OVER (ORDER BY created_at) AS rn
  FROM audit_logs
  WHERE user_id = '<user-uuid>'
    AND action IN ('login', 'logout')
    AND created_at > NOW() - INTERVAL '30 days'
)
SELECT
  l.created_at AS logged_in_at,
  o.created_at AS logged_out_at,
  o.created_at - l.created_at AS session_duration,
  l.ip_address
FROM events l
LEFT JOIN events o ON o.rn = l.rn + 1 AND o.action = 'logout'
WHERE l.action = 'login'
ORDER BY l.created_at DESC;
```

Sessions where `logged_out_at` is NULL mean the user never explicitly logged out (token timeout or browser close). PowerShell:

```powershell
$userId = "95b8337a-3fe9-415d-ac8f-8d2017c3d59c"
$sql = @"
WITH events AS (
  SELECT created_at, action, ip_address,
         ROW_NUMBER() OVER (ORDER BY created_at) AS rn
  FROM audit_logs
  WHERE user_id='$userId' AND action IN ('login','logout')
    AND created_at > NOW() - INTERVAL '30 days'
)
SELECT l.created_at AS logged_in_at, o.created_at AS logged_out_at,
       o.created_at - l.created_at AS session_duration, l.ip_address
FROM events l
LEFT JOIN events o ON o.rn = l.rn + 1 AND o.action='logout'
WHERE l.action='login'
ORDER BY l.created_at DESC;
"@
$sql | docker exec -i fieldpro_postgres psql -U fieldpro -d fieldpro
```

---

## 7. Did a specific user log in from an unusual IP?

> Use case: incident response — "user X's account was compromised, what IPs has it touched?"

```sql
SELECT
  ip_address,
  COUNT(*) AS login_count,
  MIN(created_at) AS first_seen,
  MAX(created_at) AS last_seen
FROM audit_logs
WHERE user_id = '<user-uuid>'
  AND action = 'login'
  AND created_at > NOW() - INTERVAL '90 days'
GROUP BY ip_address
ORDER BY login_count DESC;
```

PowerShell:

```powershell
$userId = "95b8337a-3fe9-415d-ac8f-8d2017c3d59c"
docker exec fieldpro_postgres psql -U fieldpro -d fieldpro -c "SELECT ip_address, COUNT(*) AS login_count, MIN(created_at) AS first_seen, MAX(created_at) AS last_seen FROM audit_logs WHERE user_id='$userId' AND action='login' AND created_at > NOW() - INTERVAL '90 days' GROUP BY ip_address ORDER BY login_count DESC;"
```

What to look for:
- IPs with `login_count` = 1 that don't match the user's known location
- A new IP with recent `last_seen` immediately preceding the suspected incident

---

## 8. New tenant signups in the last week

> Use case: business — track tenant growth without polling the tenants table directly. Useful when you want activity timing, not just counts.

```sql
SELECT
  tenant_id,
  resource_id AS new_tenant_id,
  user_id AS first_admin_user_id,
  ip_address,
  created_at
FROM audit_logs
WHERE action = 'tenant_registered'
  AND created_at > NOW() - INTERVAL '7 days'
ORDER BY created_at DESC;
```

PowerShell:

```powershell
docker exec fieldpro_postgres psql -U fieldpro -d fieldpro -c "SELECT resource_id AS new_tenant_id, user_id AS first_admin_user_id, ip_address, created_at FROM audit_logs WHERE action='tenant_registered' AND created_at > NOW() - INTERVAL '7 days' ORDER BY created_at DESC;"
```

Note that `tenant_id == resource_id` for `tenant_registered` rows (the tenant is the affected resource).

---

## 9. Password resets in the last 30 days

> Use case: support — "how many users have reset passwords this month? any patterns?"

```sql
SELECT
  user_id,
  ip_address,
  created_at
FROM audit_logs
WHERE action = 'password_reset'
  AND created_at > NOW() - INTERVAL '30 days'
ORDER BY created_at DESC;
```

PowerShell:

```powershell
docker exec fieldpro_postgres psql -U fieldpro -d fieldpro -c "SELECT user_id, ip_address, created_at FROM audit_logs WHERE action='password_reset' AND created_at > NOW() - INTERVAL '30 days' ORDER BY created_at DESC;"
```

What to look for:
- Same user resetting many times in a short window → account takeover or user confusion
- Reset from an `ip_address` that doesn't match their usual `login` IPs → suspicious

---

## 10. Auth event summary by tenant (last 30 days)

> Use case: per-tenant security posture overview. Skip the tenant filter and add `GROUP BY tenant_id` to compare across tenants.

```sql
SELECT
  action,
  COUNT(*) AS event_count,
  COUNT(DISTINCT user_id) AS unique_actors,
  COUNT(DISTINCT ip_address) AS unique_ips
FROM audit_logs
WHERE tenant_id = '<tenant-uuid>'
  AND action IN ('login', 'login_failed', 'logout', 'password_reset')
  AND created_at > NOW() - INTERVAL '30 days'
GROUP BY action
ORDER BY action;
```

PowerShell:

```powershell
$tenantId = "<tenant-uuid>"
docker exec fieldpro_postgres psql -U fieldpro -d fieldpro -c "SELECT action, COUNT(*) AS event_count, COUNT(DISTINCT user_id) AS unique_actors, COUNT(DISTINCT ip_address) AS unique_ips FROM audit_logs WHERE tenant_id='$tenantId' AND action IN ('login','login_failed','logout','password_reset') AND created_at > NOW() - INTERVAL '30 days' GROUP BY action ORDER BY action;"
```

What to look for:
- `login_failed` count >> `login` count → tenant is under attack
- `unique_ips` >> `unique_actors` for logins → users on the move, OR shared accounts (anti-pattern)

---

## Quick cleanup — purge test rows

After running manual tests with custom user agents, clean up:

```sql
DELETE FROM audit_logs WHERE user_agent LIKE 'manual-test/%' OR user_agent LIKE 'phase2-test/%';
```

PowerShell:

```powershell
docker exec fieldpro_postgres psql -U fieldpro -d fieldpro -c "DELETE FROM audit_logs WHERE user_agent LIKE 'manual-test/%' OR user_agent LIKE 'phase2-test/%';"
```

**Only run this in dev.** Production audit logs are evidence; never bulk-delete them.
