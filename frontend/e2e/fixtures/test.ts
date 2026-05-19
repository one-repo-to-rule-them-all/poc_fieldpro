import { test as base, expect } from "@playwright/test";
import { LoginPage } from "../pages/login.page";
import { WorkOrdersListPage } from "../pages/work-orders-list.page";
import { WorkOrderDetailPage } from "../pages/work-order-detail.page";
import { WorkOrderForm } from "../pages/work-order-form.page";
import { ApiClient } from "../support/api-client";

/**
 * Extended `test` with POMs + an authenticated API client injected as fixtures.
 *
 * Specs import `test, expect` from here (not from @playwright/test directly).
 *
 * Default role is `admin` — the storageState comes from playwright.config.ts.
 * To run a spec as a different role, override at file/describe scope:
 *
 *   import { AUTH_FILE } from "../support/roles";
 *   test.use({ storageState: AUTH_FILE.employee });
 */
type Fixtures = {
  loginPage: LoginPage;
  workOrdersListPage: WorkOrdersListPage;
  workOrderDetailPage: WorkOrderDetailPage;
  workOrderForm: WorkOrderForm;
  apiAsAdmin: ApiClient;
};

export const test = base.extend<Fixtures>({
  loginPage: async ({ page }, use) => {
    await use(new LoginPage(page));
  },

  workOrdersListPage: async ({ page }, use) => {
    await use(new WorkOrdersListPage(page));
  },

  workOrderDetailPage: async ({ page }, use) => {
    await use(new WorkOrderDetailPage(page));
  },

  workOrderForm: async ({ page }, use) => {
    await use(new WorkOrderForm(page));
  },

  apiAsAdmin: async ({}, use) => {
    const client = await ApiClient.loginAs("admin");
    await use(client);
    await client.dispose();
  },
});

export { expect };
