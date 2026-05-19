import { test, expect } from "../fixtures/test";

/**
 * Critical flow #1 from docs/proposals/testing-infrastructure-overhaul.md §4.6:
 *
 *   login → create work order → navigate to detail → mark complete
 *
 * Role: admin (default storageState).
 * Setup: uses API client to pick the first seeded client/location, so the spec
 * doesn't depend on remembering specific seed IDs.
 *
 * Geolocation: this spec does NOT exercise check-in (covered in a follow-up
 * spec for the field-worker flow). It only verifies the manager-side path.
 */

test.describe("work order — create and complete", () => {
  test("creates a new work order and marks it complete", async ({
    page,
    workOrdersListPage,
    workOrderDetailPage,
    workOrderForm,
    apiAsAdmin,
  }) => {
    // ─── Arrange: pick a seeded client + one of its locations ───────────────
    const clients = await apiAsAdmin.listClients();
    expect(clients.length, "seed must include at least one client").toBeGreaterThan(0);

    // Try clients in order until we find one that has at least one location.
    let chosenClient: { id: string; name: string } | null = null;
    let chosenLocation: { id: string; name: string } | null = null;
    for (const c of clients) {
      const locations = await apiAsAdmin.listLocations(c.id);
      const first = locations[0];
      if (first) {
        chosenClient = c;
        chosenLocation = first;
        break;
      }
    }
    expect(chosenClient, "no seeded client has a location").not.toBeNull();
    expect(chosenLocation).not.toBeNull();

    const uniqueTitle = `E2E WO ${Date.now()}`;
    const today = new Date().toISOString().slice(0, 10);

    // ─── Act: navigate, open modal, fill, submit ────────────────────────────
    await workOrdersListPage.goto();
    await expect(workOrdersListPage.pageTitle).toHaveText("Work Orders");

    await workOrdersListPage.openNewWorkOrderModal();
    await expect(workOrdersListPage.modal).toBeVisible();

    await workOrderForm.fillAndSubmit({
      title: uniqueTitle,
      clientId: chosenClient!.id,
      locationId: chosenLocation!.id,
      priority: "normal",
      scheduledDate: today,
      description: "Created by Playwright E2E smoke test",
    });

    // ─── Assert: redirected to detail page, status is Draft ────────────────
    const newWoId = await workOrderDetailPage.waitForUrlAndExtractId();
    await expect(workOrderDetailPage.pageTitle).toHaveText(uniqueTitle);
    await expect(workOrderDetailPage.statusBadge).toContainText("Draft");

    // ─── Act: mark complete ─────────────────────────────────────────────────
    await workOrderDetailPage.clickComplete();

    // ─── Assert: status flips to Completed ──────────────────────────────────
    await expect(workOrderDetailPage.statusBadge).toContainText("Completed", {
      timeout: 10_000,
    });

    // ─── Assert: appears in the list with the new status ────────────────────
    await workOrdersListPage.goto();
    const newRow = workOrdersListPage.rowByWorkOrderId(newWoId);
    await expect(newRow).toBeVisible();
    await expect(newRow).toContainText(uniqueTitle);
    await expect(newRow).toContainText("Completed");

    // ─── Cleanup: best-effort, ignore failures ──────────────────────────────
    await apiAsAdmin.delete(`/api/v1/work-orders/${newWoId}`).catch(() => {
      /* not fatal if endpoint disallows hard delete */
    });
  });
});
