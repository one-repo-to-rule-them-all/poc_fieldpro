# Audit log query cookbook

Operational SQL recipes for the `audit_logs` table. Use these to answer real questions during incidents, customer disputes, or security reviews — copy, paste, adapt.

## Files in this directory

| File | Covers |
|---|---|
| [auth-events.md](auth-events.md) | Login, logout, failed login attempts, password reset, tenant registration |

As more audit phases land, additional files follow the same pattern:

- `work-orders.md` — work order creates / updates / status transitions (Phase 3)
- `invoices.md` — invoice + line item + payment events (Phase 3)
- `clients.md` — client + location mutations (Phase 3)
- `crews.md` — crew + member assignment changes (Phase 3)
- `users.md` — user + role + activation changes (Phase 3)
- `cross-cutting.md` — anomaly detection, top-N reports, retention checks (Phase 4+)

## How to run these queries

Every query in this cookbook is structured to run via `psql` inside the `fieldpro_postgres` container. From PowerShell:

```powershell
docker exec fieldpro_postgres psql -U fieldpro -d fieldpro -c "<SQL HERE>"
```

For pivoted (column-per-line) output on a single row:

```powershell
docker exec fieldpro_postgres psql -U fieldpro -d fieldpro -c "<SQL HERE>" -x
```

For multi-line SQL, write it to a file and pipe:

```powershell
Get-Content my-query.sql | docker exec -i fieldpro_postgres psql -U fieldpro -d fieldpro
```

## How to read an audit row

| Column | Meaning |
|---|---|
| `id` | Stable UUID for this audit event — quote in incident reports |
| `tenant_id` | The tenant whose data was affected (NULL for cross-tenant or pre-auth events) |
| `user_id` | The actor — who did the thing. NULL if unauthenticated or unidentifiable (e.g. failed login with unknown email) |
| `action` | Domain verb: `created`, `updated`, `deleted`, `login`, `login_failed`, `logout`, `tenant_registered`, `password_reset`, etc. |
| `resource_type` | Model name (`WorkOrder`, `Invoice`, `User`, `Tenant`) or `auth` for non-resource auth events |
| `resource_id` | UUID of the affected row, stringified |
| `old_values` | JSONB diff of changed fields BEFORE the mutation. NULL for creates and auth events (no diff to capture). Sensitive fields (`hashed_password`, `mfa_secret`) are stripped by the listener — see scoping doc Section 4 |
| `new_values` | JSONB diff of changed fields AFTER. NULL for deletes and auth events |
| `ip_address` | Request origin IP (string, IPv4 or IPv6) |
| `user_agent` | Truncated to 500 chars |
| `request_id` | The per-request UUID set by `RequestIDMiddleware`. **All audit rows produced by a single HTTP request share this value** — group by it to reconstruct what one user-action did. NULL for rows created before migration `002_audit_request_id_and_view`. |
| `created_at` | UTC timestamp with timezone |

## The `v_audit_events` view — readable JOIN to users

For day-to-day operational queries, prefer the pre-JOINed view over the raw table. It adds `actor_email` and `actor_name` so you don't have to JOIN to `users` yourself:

```sql
SELECT created_at, actor_email, action, resource_type, resource_id
FROM v_audit_events
ORDER BY created_at DESC
LIMIT 50;
```

Same shape as `audit_logs` plus the two actor fields. Use the raw table when you need to bulk-insert, write a migration, or scope to indexes that aren't reachable through the view.

## Common patterns these queries use

### Recency filter
```sql
WHERE created_at > NOW() - INTERVAL '15 minutes'
```

### Pretty user_agent
```sql
LEFT(user_agent, 40) AS ua
```

### NULL-safe display
```sql
COALESCE(user_id::text, '<null>') AS user_id
```

### Tenant scoping (always add this in multi-tenant analysis)
```sql
WHERE tenant_id = '<tenant uuid>'
```

## Performance notes

The table has these indexes:

- `idx_audit_logs_tenant_id`, `idx_audit_logs_user_id`, `idx_audit_logs_action` — single-column lookups (`001_initial_schema.py:1477-1479`)
- `ix_audit_logs_tenant_resource_date` — composite `(tenant_id, resource_type, created_at)` (`001_initial_schema.py:1480`)
- `idx_audit_logs_tenant_date` — composite `(tenant_id, created_at)` (added later in same migration)
- `ix_audit_logs_request_id` — single-column lookup on `request_id` (`002_audit_request_id_and_view.py`)

Filter by **`tenant_id` first**, then by date or action — the composite indexes give you O(log n) seeks. Avoid `LIKE 'login%'` on the `action` column when an `IN (...)` works; ranges defeat the index.

## When to use these vs. the Phase 4 read API

- **psql** — incident response, ad-hoc digging, full SQL power
- **`GET /api/v1/audit-logs`** (Phase 4, not shipped yet) — admin UI, paginated browse, filtered by query params

The runbook stays useful even after the read API ships — anything more complex than filter + paginate (aggregates, joins, hourly histograms) lives here.

## Contributing

When a new audit-emitting feature ships, add a corresponding file in this directory or a section in an existing one. Match the structure of `auth-events.md` — one section per real-world question, with the SQL, the PowerShell wrapper, and an example of what the answer looks like.
