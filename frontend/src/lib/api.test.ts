import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "@/test/mocks/server";
import { workOrdersApi } from "./api";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// These tests pin the contract that the axios response interceptor in api.ts
// normalizes errors into a flat shape:
//   { message: string, status: number, code?: string, details?: ... }
//
// The backend (backend/app/main.py) wraps every error in:
//   { error: { code, message, details?, request_id } }
// so `apiError.message` is sourced from `data.error.message`. The legacy
// FastAPI shape (`{ detail }`) is kept as a fallback for tests or any
// non-wrapped endpoint.

describe("workOrdersApi.completeWorkOrder — error normalization", () => {
  it("surfaces error.message from the wrapped backend envelope", async () => {
    const message = "Cannot complete: 1 required task(s) not done: 'fa'";
    server.use(
      http.post(`${API}/api/v1/work-orders/:id/complete`, () =>
        HttpResponse.json(
          {
            error: {
              code: "UNPROCESSABLE_ENTITY",
              message,
              request_id: "req-123",
            },
          },
          { status: 422 }
        )
      )
    );

    await expect(workOrdersApi.completeWorkOrder("wo-1")).rejects.toMatchObject({
      message,
      status: 422,
      code: "UNPROCESSABLE_ENTITY",
    });
  });

  it("preserves validation details from the wrapped envelope", async () => {
    server.use(
      http.post(`${API}/api/v1/work-orders/:id/complete`, () =>
        HttpResponse.json(
          {
            error: {
              code: "VALIDATION_ERROR",
              message: "Request validation failed.",
              details: { title: ["field required"] },
              request_id: "req-456",
            },
          },
          { status: 422 }
        )
      )
    );

    await expect(workOrdersApi.completeWorkOrder("wo-1")).rejects.toMatchObject({
      status: 422,
      code: "VALIDATION_ERROR",
      details: { title: ["field required"] },
    });
  });

  it("falls back to the legacy {detail} shape when error wrapper is absent", async () => {
    const detail = "Legacy unwrapped FastAPI error";
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

  it("falls back to a useful message when the backend omits both shapes", async () => {
    server.use(
      http.post(`${API}/api/v1/work-orders/:id/complete`, () =>
        HttpResponse.json({}, { status: 500 })
      )
    );

    await expect(workOrdersApi.completeWorkOrder("wo-1")).rejects.toSatisfy(
      (err: unknown) =>
        typeof (err as { message?: string }).message === "string" &&
        (err as { message: string }).message.length > 0 &&
        (err as { status?: number }).status === 500
    );
  });
});
