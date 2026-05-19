import { http, HttpResponse } from "msw";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const fixtures = {
  user: {
    id: "user-1",
    email: "admin@demo.fieldpro.app",
    first_name: "Demo",
    last_name: "Admin",
    role: "admin",
    is_active: true,
  },
  tenant: {
    id: "tenant-1",
    name: "Demo Tenant",
    slug: "demo",
    is_active: true,
  },
  client: {
    id: "client-1",
    tenant_id: "tenant-1",
    name: "City of Corpus Christi",
    code: "CITY-CC",
    industry: "Government",
    is_active: true,
  },
  workOrder: {
    id: "wo-1",
    tenant_id: "tenant-1",
    title: "Park sweep",
    status: "pending",
    priority: "normal",
    client_id: "client-1",
    client_name: "City of Corpus Christi",
    location_id: "loc-1",
    location_name: "Bayfront Park",
    scheduled_date: "2026-05-20",
  },
};

function paginated<T>(items: T[]) {
  return {
    items,
    total: items.length,
    page: 1,
    page_size: 25,
    pages: 1,
  };
}

export const handlers = [
  // ── Auth ───────────────────────────────────────────────────────────────
  http.post(`${API}/api/v1/auth/login`, async ({ request }) => {
    const body = (await request.json()) as { email: string; password: string };
    if (body.password === "wrong") {
      return HttpResponse.json(
        { detail: "Invalid email or password" },
        { status: 401 }
      );
    }
    return HttpResponse.json({
      access_token: "fake-access-token",
      refresh_token: "fake-refresh-token",
      user: fixtures.user,
      tenant: fixtures.tenant,
    });
  }),

  http.post(`${API}/api/v1/auth/logout`, () => HttpResponse.json({})),

  http.get(`${API}/api/v1/auth/me`, () =>
    HttpResponse.json({ user: fixtures.user, tenant: fixtures.tenant })
  ),

  // ── Work orders ────────────────────────────────────────────────────────
  http.get(`${API}/api/v1/work-orders`, () =>
    HttpResponse.json(paginated([fixtures.workOrder]))
  ),
  http.get(`${API}/api/v1/work-orders/:id`, ({ params }) =>
    HttpResponse.json({ ...fixtures.workOrder, id: params.id })
  ),

  // ── Clients ────────────────────────────────────────────────────────────
  http.get(`${API}/api/v1/clients`, () =>
    HttpResponse.json(paginated([fixtures.client]))
  ),
  http.get(`${API}/api/v1/clients/:id`, ({ params }) =>
    HttpResponse.json({ ...fixtures.client, id: params.id })
  ),

  // ── Crews ──────────────────────────────────────────────────────────────
  http.get(`${API}/api/v1/crews`, () => HttpResponse.json(paginated([]))),

  // ── Users ──────────────────────────────────────────────────────────────
  http.get(`${API}/api/v1/users`, () =>
    HttpResponse.json({
      data: [fixtures.user],
      meta: { total: 1, page: 1, limit: 25, pages: 1 },
    })
  ),
];
