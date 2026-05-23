import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "@/test/mocks/server";
import { workOrdersApi } from "./api";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// These tests pin the contract that the axios response interceptor in api.ts
// normalizes errors into a flat shape:
//   { message: string, status: number, code?: string, details?: ... }
// where `message` carries the FastAPI `detail` field. Consumers (e.g. the
// Mark Complete toast on the work order detail page) depend on reading
// `err.message`, NOT `err.response.data.detail` — the latter is gone by the
// time the promise rejects. See #37 / #65.

describe("workOrdersApi.completeWorkOrder — error normalization", () => {
  it("surfaces a 422 detail on err.message and preserves status", async () => {
    const detail = "Cannot complete: 2 required task(s) not done: 'Restock TP', 'Empty trash'";
    server.use(
      http.post(`${API}/api/v1/work-orders/:id/complete`, () =>
        HttpResponse.json({ detail }, { status: 422 })
      )
    );

    await expect(workOrdersApi.completeWorkOrder("wo-1")).rejects.toMatchObject({
      message: detail,
      status: 422,
    });
  });

  it("falls back to a useful message when the backend omits detail", async () => {
    server.use(
      http.post(`${API}/api/v1/work-orders/:id/complete`, () =>
        HttpResponse.json({}, { status: 500 })
      )
    );

    await expect(workOrdersApi.completeWorkOrder("wo-1")).rejects.toMatchObject({
      status: 500,
    });
    // .message is the fallback string from the interceptor — non-empty and stable.
    await expect(workOrdersApi.completeWorkOrder("wo-1")).rejects.toSatisfy(
      (err: unknown) =>
        typeof (err as { message?: string }).message === "string" &&
        ((err as { message: string }).message.length > 0)
    );
  });
});
