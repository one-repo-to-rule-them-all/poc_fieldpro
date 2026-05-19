import { describe, it, expect, beforeEach } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "@/test/mocks/server";
import { useAuthStore } from "./auth-store";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

describe("authStore.login (MSW integration)", () => {
  beforeEach(() => {
    useAuthStore.getState().clearAuth();
  });

  it("populates user + tenant + accessToken on successful login", async () => {
    await useAuthStore
      .getState()
      .login("admin@demo.fieldpro.app", "Admin123!");

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.user?.email).toBe("admin@demo.fieldpro.app");
    expect(state.tenant?.slug).toBe("demo");
    expect(state.accessToken).toBe("fake-access-token");
  });

  it("does not authenticate when the API returns 401", async () => {
    await expect(
      useAuthStore.getState().login("admin@demo.fieldpro.app", "wrong")
    ).rejects.toMatchObject({ status: 401 });

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
    expect(state.accessToken).toBeNull();
  });

  it("propagates a network error without leaving isLoading=true", async () => {
    server.use(
      http.post(`${API}/api/v1/auth/login`, () => HttpResponse.error())
    );

    await expect(
      useAuthStore.getState().login("admin@demo.fieldpro.app", "Admin123!")
    ).rejects.toBeTruthy();

    expect(useAuthStore.getState().isLoading).toBe(false);
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });
});
