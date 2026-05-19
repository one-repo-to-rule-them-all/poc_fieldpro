import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";
const API_URL = process.env.API_URL ?? "http://localhost:8000";

const ADMIN_STORAGE = path.join(__dirname, "e2e/.auth/admin.json");

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ["html", { outputFolder: "playwright-report", open: "never" }],
    process.env.CI ? ["github"] : ["list"],
  ],
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    extraHTTPHeaders: {
      Accept: "application/json",
    },
  },
  projects: [
    {
      name: "setup",
      testMatch: /auth\.setup\.ts/,
    },
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        storageState: ADMIN_STORAGE,
      },
      dependencies: ["setup"],
      testIgnore: /auth\.setup\.ts/,
    },
  ],
  webServer: process.env.CI
    ? undefined
    : {
        command: "npm run dev",
        url: BASE_URL,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
  // Test-level timeout is generous to absorb Next.js dev-server's lazy
  // route compilation on first navigation (production builds in CI are fast).
  // Per-locator/expect timeout stays tight so real UI hangs fail quickly.
  timeout: 90_000,
  expect: {
    timeout: 10_000,
  },
  metadata: {
    apiUrl: API_URL,
  },
});
