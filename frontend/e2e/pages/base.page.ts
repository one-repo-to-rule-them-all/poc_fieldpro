import type { Locator, Page } from "@playwright/test";
import { TID } from "../support/selectors";

/**
 * Base Page Object.
 *
 * Owns elements that appear on every authenticated page:
 *   - Sidebar navigation
 *   - Page header (title, subtitle, breadcrumbs)
 *
 * Concrete pages extend this and add their own unique elements.
 * Keep BasePage thin — only put something here when 2+ pages need it.
 */
export abstract class BasePage {
  readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  // ─── Page header ─────────────────────────────────────────────────────────

  get pageTitle(): Locator {
    return this.page.getByTestId(TID.pageHeader.title);
  }

  get pageSubtitle(): Locator {
    return this.page.getByTestId(TID.pageHeader.subtitle);
  }

  // ─── Sidebar navigation ──────────────────────────────────────────────────

  navLink(target: keyof typeof TID.nav): Locator {
    return this.page.getByTestId(TID.nav[target]);
  }

  async navigateTo(target: keyof typeof TID.nav): Promise<void> {
    await this.navLink(target).first().click();
  }

  // ─── Modal helpers (apply on any page that opens a modal) ────────────────

  get modal(): Locator {
    return this.page.getByTestId(TID.modal.root);
  }

  async closeModal(): Promise<void> {
    await this.page.getByTestId(TID.modal.closeButton).click();
  }
}
