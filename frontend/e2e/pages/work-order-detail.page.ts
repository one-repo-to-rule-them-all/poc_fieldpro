import type { Locator } from "@playwright/test";
import { TID } from "../support/selectors";
import { BasePage } from "./base.page";

/**
 * WorkOrderDetailPage — covers /dashboard/work-orders/{id}.
 */
export class WorkOrderDetailPage extends BasePage {
  // ─── Locators ────────────────────────────────────────────────────────────

  get editButton(): Locator {
    return this.page.getByTestId(TID.workOrderDetail.editButton);
  }

  get completeButton(): Locator {
    return this.page.getByTestId(TID.workOrderDetail.completeButton);
  }

  get statusBadge(): Locator {
    return this.page.getByTestId(TID.workOrderDetail.statusBadge);
  }

  // Check-in widget
  get checkInWidget(): Locator {
    return this.page.getByTestId(TID.checkIn.root);
  }

  get checkInButton(): Locator {
    return this.page.getByTestId(TID.checkIn.checkInButton);
  }

  get checkOutButton(): Locator {
    return this.page.getByTestId(TID.checkIn.checkOutButton);
  }

  get checkInStatus(): Locator {
    return this.page.getByTestId(TID.checkIn.statusText);
  }

  // Tasks
  get taskList(): Locator {
    return this.page.getByTestId(TID.taskList.root);
  }

  taskToggle(taskId: string): Locator {
    return this.page.getByTestId(TID.taskList.toggleButton(taskId));
  }

  // ─── Actions ─────────────────────────────────────────────────────────────

  async goto(id: string): Promise<void> {
    await this.page.goto(`/dashboard/work-orders/${id}`);
    await this.pageTitle.waitFor({ state: "visible" });
  }

  /**
   * Wait until the URL settles on /dashboard/work-orders/{uuid} and return the id.
   * Useful after submitting the create form, which redirects to the new WO's detail.
   */
  async waitForUrlAndExtractId(): Promise<string> {
    await this.page.waitForURL(
      /\/dashboard\/work-orders\/[0-9a-f-]{36}$/i,
      { timeout: 15_000 },
    );
    const url = new URL(this.page.url());
    const segments = url.pathname.split("/");
    return segments[segments.length - 1] ?? "";
  }

  async clickComplete(): Promise<void> {
    await this.completeButton.click();
  }

  async clickCheckIn(): Promise<void> {
    // Wait for the geolocation gate to resolve and the button to become enabled.
    await this.checkInButton.waitFor({ state: "visible" });
    await this.page.waitForFunction(
      (sel) => {
        const btn = document.querySelector(`[data-testid="${sel}"]`);
        return btn instanceof HTMLButtonElement && !btn.disabled;
      },
      TID.checkIn.checkInButton,
      { timeout: 15_000 },
    );
    await this.checkInButton.click();
  }
}
