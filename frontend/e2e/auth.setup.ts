import { test as setup, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { ROLES, AUTH_FILE, type Role } from "./support/roles";
import { LoginPage } from "./pages/login.page";

/**
 * Setup project — runs once before any spec.
 *
 * Logs in as each demo role via the LoginPage POM and persists the
 * resulting storage state (cookies + localStorage) to e2e/.auth/{role}.json.
 * Specs reuse the persisted state via `test.use({ storageState })`,
 * skipping the login flow on every test.
 *
 * The exception: a dedicated `login.spec.ts` should NOT reuse state — it
 * exercises the login UI from a clean session.
 */

const ROLES_TO_AUTH: Role[] = ["admin", "manager", "employee"];

// Ensure the .auth directory exists before any role setup tries to write to it.
setup.beforeAll(() => {
  const authDir = path.dirname(AUTH_FILE.admin);
  fs.mkdirSync(authDir, { recursive: true });
});

for (const role of ROLES_TO_AUTH) {
  setup(`authenticate as ${role}`, async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login(ROLES[role].email, ROLES[role].password);

    // Wait for /dashboard redirect — confirms login actually succeeded.
    await page.waitForURL((url) => url.pathname.startsWith("/dashboard"), {
      timeout: 15_000,
    });

    // Sanity check that the app rehydrated the user in zustand-persisted state.
    await expect(page.locator("body")).toBeVisible();

    await page.context().storageState({ path: AUTH_FILE[role] });
  });
}
