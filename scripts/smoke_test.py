#!/usr/bin/env python3
"""
FieldPro — API Smoke Test
=========================

Hits the live (or local) backend over HTTP and verifies end-to-end:
auth flows, list/detail/filter endpoints, write paths with enum validation,
and role-based access control.

Uses only the Python standard library — no pip install required.

Usage:
    python scripts/smoke_test.py                          # default: deployed demo
    python scripts/smoke_test.py --base http://localhost:8000
    python scripts/smoke_test.py --admin-email ...  --admin-password ...

Exit code 0 if all checks pass, 1 if any fail.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field


@dataclass
class Result:
    passed: int = 0
    failed: int = 0
    failures: list[str] = field(default_factory=list)


def req(base: str, method: str, path: str, token: str | None = None,
        body: dict | None = None, expect: int = 200) -> tuple[bool, int, str]:
    url = base + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status == expect, resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code == expect, e.code, e.read().decode()[:600]


def log(result: Result, name: str, ok: bool, status: int, note: str = "") -> None:
    icon = "PASS" if ok else "FAIL"
    line = f"  [{icon}] {status:3d}  {name}"
    if note:
        line += f"  {note}"
    print(line)
    if ok:
        result.passed += 1
    else:
        result.failed += 1
        result.failures.append(name)


def main() -> int:
    parser = argparse.ArgumentParser(description="FieldPro API smoke test")
    parser.add_argument("--base", default="https://fieldpro-poc-backend.fly.dev",
                        help="Backend base URL (default: deployed demo)")
    parser.add_argument("--admin-email", default="admin@demo.fieldpro.app")
    parser.add_argument("--admin-password", default="Admin123!")
    parser.add_argument("--manager-email", default="manager@demo.fieldpro.app")
    parser.add_argument("--manager-password", default="Manager123!")
    parser.add_argument("--employee-email", default="carlos@demo.fieldpro.app")
    parser.add_argument("--employee-password", default="Employee123!")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    r = Result()

    print(f"FieldPro smoke test against {base}")
    print()

    print("=== Auth ===")
    ok, st, raw = req(base, "POST", "/api/v1/auth/login",
                      body={"email": args.admin_email, "password": args.admin_password})
    log(r, "Login as admin", ok, st)
    admin = json.loads(raw)["access_token"] if ok else None

    ok, st, raw = req(base, "POST", "/api/v1/auth/login",
                      body={"email": args.manager_email, "password": args.manager_password})
    log(r, "Login as manager", ok, st)

    ok, st, raw = req(base, "POST", "/api/v1/auth/login",
                      body={"email": args.employee_email, "password": args.employee_password})
    log(r, "Login as field worker", ok, st)
    emp = json.loads(raw)["access_token"] if ok else None

    ok, st, _ = req(base, "POST", "/api/v1/auth/login",
                    body={"email": args.admin_email, "password": "WRONG"}, expect=401)
    log(r, "Wrong password -> 401", ok, st)

    ok, st, _ = req(base, "GET", "/api/v1/work-orders", expect=401)
    log(r, "Unauth GET -> 401", ok, st)

    if not admin or not emp:
        print()
        print("FAIL: could not obtain admin or employee token — aborting")
        return 1

    print()
    print("=== Health ===")
    ok, st, raw = req(base, "GET", "/health")
    health = json.loads(raw)
    log(r, f"GET /health (db={health['db']} redis={health['redis']})",
        ok and health["db"] == "ok" and health["redis"] == "ok", st)

    print()
    print("=== Collection endpoints ===")
    for path in ["/api/v1/work-orders", "/api/v1/clients", "/api/v1/locations",
                 "/api/v1/crews", "/api/v1/invoices", "/api/v1/users"]:
        ok, st, raw = req(base, "GET", path, admin)
        count = ""
        if ok:
            d = json.loads(raw)
            items = d.get("items") if isinstance(d, dict) else d
            if isinstance(items, list):
                count = f"({len(items)} items)"
        log(r, f"GET {path:30s} {count}", ok, st)

    print()
    print("=== Detail endpoints ===")
    wos = json.loads(req(base, "GET", "/api/v1/work-orders", admin)[2])["items"]
    clients = json.loads(req(base, "GET", "/api/v1/clients", admin)[2])["items"]
    invoices = json.loads(req(base, "GET", "/api/v1/invoices", admin)[2])["items"]
    crews = json.loads(req(base, "GET", "/api/v1/crews", admin)[2])["items"]

    ok, st, _ = req(base, "GET", "/api/v1/work-orders/" + wos[0]["id"], admin)
    log(r, f"GET WO detail (status={wos[0]['status']})", ok, st)

    ok, st, _ = req(base, "GET", "/api/v1/clients/" + clients[0]["id"], admin)
    log(r, f"GET client detail ({clients[0]['name']})", ok, st)

    ok, st, _ = req(base, "GET", "/api/v1/invoices/" + invoices[0]["id"], admin)
    log(r, f"GET invoice detail ({invoices[0].get('invoice_number', '?')})", ok, st)

    ok, st, _ = req(base, "GET", "/api/v1/crews/" + crews[0]["id"], admin)
    log(r, f"GET crew detail ({crews[0]['name']})", ok, st)

    print()
    print("=== Analytics ===")
    for path in ["/api/v1/analytics/dashboard", "/api/v1/analytics/kpis",
                 "/api/v1/analytics/revenue", "/api/v1/analytics/work-order-trends",
                 "/api/v1/analytics/crew-productivity"]:
        ok, st, _ = req(base, "GET", path, admin)
        log(r, f"GET {path}", ok, st)

    print()
    print("=== Filters ===")
    for q in ["status=scheduled", "status=completed",
              f"client_id={clients[0]['id']}"]:
        ok, st, raw = req(base, "GET", f"/api/v1/work-orders?{q}", admin)
        n = len(json.loads(raw)["items"]) if ok else 0
        log(r, f"GET /work-orders?{q} -> {n} items", ok, st)

    print()
    print("=== Write paths ===")
    new_client = {"name": "Smoke Test Co", "code": "SMK",
                  "industry": "janitorial", "billing_email": "billing@smoke.test",
                  "is_active": True}
    ok, st, raw = req(base, "POST", "/api/v1/clients", admin, body=new_client, expect=201)
    log(r, "POST /clients (valid enum) -> 201", ok, st)
    new_id = json.loads(raw)["id"] if ok else None

    ok, st, _ = req(base, "POST", "/api/v1/clients", admin,
                    body={"name": "Bad", "code": "BAD",
                          "industry": "Commercial Real Estate",
                          "billing_email": "a@b.c", "is_active": True}, expect=422)
    log(r, "POST /clients (bad enum) -> 422", ok, st)

    if new_id:
        ok, st, _ = req(base, "DELETE", "/api/v1/clients/" + new_id, admin, expect=204)
        log(r, "DELETE created client (cleanup) -> 204", ok, st)

    print()
    print("=== Role-based access ===")
    ok, st, _ = req(base, "POST", "/api/v1/clients", emp,
                    body={"name": "EmpCo", "code": "EMP", "industry": "janitorial",
                          "billing_email": "a@b.c", "is_active": True}, expect=403)
    log(r, "Field worker POST /clients -> 403", ok, st)

    ok, st, _ = req(base, "GET", "/api/v1/work-orders", emp)
    log(r, "Field worker GET /work-orders -> 200", ok, st)

    print()
    print(f"Result: {r.passed} passed, {r.failed} failed")
    if r.failed:
        print()
        print("Failures:")
        for name in r.failures:
            print(f"  - {name}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
