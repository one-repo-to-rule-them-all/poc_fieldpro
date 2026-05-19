import { request, type APIRequestContext, type APIResponse } from "@playwright/test";
import { API_URL, ROLES, type Role } from "./roles";

/**
 * Thin wrapper around Playwright's APIRequestContext.
 *
 * Use for API-level setup/teardown — seeding clients/locations/crews,
 * creating work orders, fetching data for assertions. Keeps specs from
 * driving setup through the UI.
 */
export class ApiClient {
  private constructor(
    private readonly ctx: APIRequestContext,
    public readonly token: string,
    public readonly tenantId: string,
    public readonly userId: string,
  ) {}

  /**
   * Authenticate as the given role and return an ApiClient ready to use.
   * The Authorization header is set automatically on the underlying context.
   */
  static async loginAs(role: Role): Promise<ApiClient> {
    const creds = ROLES[role];
    const tempCtx = await request.newContext({ baseURL: API_URL });

    const resp = await tempCtx.post("/api/v1/auth/login", {
      data: { email: creds.email, password: creds.password },
    });
    if (!resp.ok()) {
      const body = await resp.text();
      throw new Error(
        `Login failed for ${creds.email} (${resp.status()}): ${body}`,
      );
    }
    const body = await resp.json();

    await tempCtx.dispose();

    const ctx = await request.newContext({
      baseURL: API_URL,
      extraHTTPHeaders: {
        Authorization: `Bearer ${body.access_token}`,
        Accept: "application/json",
      },
    });

    return new ApiClient(ctx, body.access_token, body.tenant.id, body.user.id);
  }

  async dispose(): Promise<void> {
    await this.ctx.dispose();
  }

  async get(path: string): Promise<APIResponse> {
    return this.ctx.get(path);
  }

  async post(path: string, data: unknown): Promise<APIResponse> {
    return this.ctx.post(path, { data });
  }

  async patch(path: string, data: unknown): Promise<APIResponse> {
    return this.ctx.patch(path, { data });
  }

  async delete(path: string): Promise<APIResponse> {
    return this.ctx.delete(path);
  }

  // ─── Convenience helpers for spec setup ──────────────────────────────────

  async listClients(): Promise<{ id: string; name: string }[]> {
    const r = await this.get("/api/v1/clients?page_size=100");
    if (!r.ok()) throw new Error(`listClients failed: ${r.status()}`);
    const body = await r.json();
    return body.items ?? [];
  }

  async listLocations(clientId: string): Promise<{ id: string; name: string }[]> {
    const r = await this.get(
      `/api/v1/locations?client_id=${clientId}&page_size=100`,
    );
    if (!r.ok()) throw new Error(`listLocations failed: ${r.status()}`);
    const body = await r.json();
    return body.items ?? [];
  }

  async listCrews(): Promise<{ id: string; name: string }[]> {
    const r = await this.get("/api/v1/crews?page_size=100");
    if (!r.ok()) throw new Error(`listCrews failed: ${r.status()}`);
    const body = await r.json();
    return body.items ?? [];
  }
}
