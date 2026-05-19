import type { Locator, Page } from "@playwright/test";
import { TID } from "../support/selectors";

/**
 * LoginPage — covers the /login route.
 *
 * Used by:
 *   - auth.setup.ts (storageState bootstrap, all 3 roles)
 *   - any future spec that explicitly tests the login UI
 *
 * Does NOT extend BasePage because the login route has no sidebar/header.
 */
export class LoginPage {
  readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  // ─── Locators ────────────────────────────────────────────────────────────

  get emailInput(): Locator {
    return this.page.getByTestId(TID.login.emailInput);
  }

  get passwordInput(): Locator {
    return this.page.getByTestId(TID.login.passwordInput);
  }

  get submitButton(): Locator {
    return this.page.getByTestId(TID.login.submitButton);
  }

  get errorBanner(): Locator {
    return this.page.getByTestId(TID.login.errorBanner);
  }

  // ─── Actions ─────────────────────────────────────────────────────────────

  async goto(): Promise<void> {
    await this.page.goto("/login");
  }

  async login(email: string, password: string): Promise<void> {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }
}
