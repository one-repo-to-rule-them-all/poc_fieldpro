import type { Locator, Page } from "@playwright/test";
import { TID } from "../support/selectors";

/**
 * WorkOrderForm POM — wraps the WorkOrderForm component (used in both
 * the create-work-order modal and the inline edit modal on the detail page).
 *
 * Not a route page, so it doesn't extend BasePage. Constructed from any
 * page that opens the modal.
 */
export class WorkOrderForm {
  readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  get titleInput(): Locator {
    return this.page.getByTestId(TID.workOrderForm.titleInput);
  }
  get descriptionInput(): Locator {
    return this.page.getByTestId(TID.workOrderForm.descriptionInput);
  }
  get clientSelect(): Locator {
    return this.page.getByTestId(TID.workOrderForm.clientSelect);
  }
  get locationSelect(): Locator {
    return this.page.getByTestId(TID.workOrderForm.locationSelect);
  }
  get crewSelect(): Locator {
    return this.page.getByTestId(TID.workOrderForm.crewSelect);
  }
  get prioritySelect(): Locator {
    return this.page.getByTestId(TID.workOrderForm.prioritySelect);
  }
  get scheduledDateInput(): Locator {
    return this.page.getByTestId(TID.workOrderForm.scheduledDateInput);
  }
  get submitButton(): Locator {
    return this.page.getByTestId(TID.workOrderForm.submitButton);
  }

  // ─── High-level helper ───────────────────────────────────────────────────

  /**
   * Fills the minimum required fields and submits the form.
   *
   * Note: client_id must be set BEFORE location_id (the location select
   * is disabled until a client is chosen). We wait for the location option
   * to appear before selecting it.
   */
  async fillAndSubmit(input: {
    title: string;
    clientId: string;
    locationId: string;
    crewId?: string;
    priority?: "low" | "normal" | "high" | "urgent";
    scheduledDate?: string; // YYYY-MM-DD
    description?: string;
  }): Promise<void> {
    await this.titleInput.fill(input.title);
    if (input.description) {
      await this.descriptionInput.fill(input.description);
    }

    await this.clientSelect.selectOption(input.clientId);

    // Location select repopulates after client changes via a useQuery —
    // wait until our target option exists before selecting it.
    await this.locationSelect.locator(`option[value="${input.locationId}"]`).waitFor({
      state: "attached",
      timeout: 10_000,
    });
    await this.locationSelect.selectOption(input.locationId);

    if (input.crewId) {
      await this.crewSelect.selectOption(input.crewId);
    }
    if (input.priority) {
      await this.prioritySelect.selectOption(input.priority);
    }
    if (input.scheduledDate) {
      await this.scheduledDateInput.fill(input.scheduledDate);
    }

    await this.submitButton.click();
  }
}
