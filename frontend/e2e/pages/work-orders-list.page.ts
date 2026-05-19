import type { Locator } from "@playwright/test";
import { TID } from "../support/selectors";
import { BasePage } from "./base.page";

/**
 * WorkOrdersListPage — covers /dashboard/work-orders.
 *
 * Responsibilities:
 *   - Navigate to the list
 *   - Open the create-work-order modal
 *   - Search / filter
 *   - Locate and click rows
 */
export class WorkOrdersListPage extends BasePage {
  // ─── Locators ────────────────────────────────────────────────────────────

  get newButton(): Locator {
    return this.page.getByTestId(TID.workOrdersList.newButton);
  }

  get searchInput(): Locator {
    return this.page.getByTestId(TID.workOrdersList.searchInput);
  }

  rowByWorkOrderId(id: string): Locator {
    return this.page.getByTestId(TID.table.row(id));
  }

  rowByTitle(title: string): Locator {
    // Fallback when caller doesn't have the ID — match by title cell text.
    return this.page.locator("tr", { hasText: title }).first();
  }

  // ─── Actions ─────────────────────────────────────────────────────────────

  async goto(): Promise<void> {
    await this.page.goto("/dashboard/work-orders");
    // Wait until the page header has rendered before returning control.
    await this.pageTitle.waitFor({ state: "visible" });
  }

  async openNewWorkOrderModal(): Promise<void> {
    await this.newButton.click();
    await this.modal.waitFor({ state: "visible" });
  }

  async search(query: string): Promise<void> {
    await this.searchInput.fill(query);
  }

  async clickRowById(id: string): Promise<void> {
    await this.rowByWorkOrderId(id).click();
  }

  async clickRowByTitle(title: string): Promise<void> {
    await this.rowByTitle(title).click();
  }
}
