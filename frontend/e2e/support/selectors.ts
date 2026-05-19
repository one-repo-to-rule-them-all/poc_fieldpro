/**
 * Centralized data-testid constants.
 *
 * Every E2E selector should reference this file — never hard-code a testid
 * in a POM or spec. When a UI element's identifier changes, this is the
 * only place that needs to update.
 */

export const TID = {
  // Login page
  login: {
    emailInput: "login-email",
    passwordInput: "login-password",
    submitButton: "login-submit",
    errorBanner: "login-error",
  },

  // App chrome (sidebar / header)
  nav: {
    workOrders: "nav-work-orders",
    schedule: "nav-schedule",
    clients: "nav-clients",
    crews: "nav-crews",
    invoices: "nav-invoices",
    analytics: "nav-analytics",
    settings: "nav-settings",
    dashboard: "nav-dashboard",
    checkIn: "nav-check-in",
  },

  pageHeader: {
    root: "page-header",
    title: "page-header-title",
    subtitle: "page-header-subtitle",
  },

  // Modal system
  modal: {
    root: "modal-root",
    title: "modal-title",
    closeButton: "modal-close",
  },

  // Generic data table — row testid is `data-row-${id}` (set by DataTable)
  table: {
    row: (id: string) => `data-row-${id}`,
  },

  // Work orders list
  workOrdersList: {
    newButton: "wo-new-button",
    searchInput: "wo-search-input",
  },

  // Work order create / edit form
  workOrderForm: {
    titleInput: "wo-form-title",
    descriptionInput: "wo-form-description",
    clientSelect: "wo-form-client",
    locationSelect: "wo-form-location",
    crewSelect: "wo-form-crew",
    prioritySelect: "wo-form-priority",
    scheduledDateInput: "wo-form-scheduled-date",
    startTimeInput: "wo-form-start-time",
    endTimeInput: "wo-form-end-time",
    submitButton: "wo-form-submit",
    cancelButton: "wo-form-cancel",
  },

  // Work order detail
  workOrderDetail: {
    editButton: "wo-edit-button",
    completeButton: "wo-complete-button",
    statusBadge: "wo-status-badge",
    priorityBadge: "wo-priority-badge",
  },

  // Check-in widget
  checkIn: {
    root: "checkin-widget",
    checkInButton: "checkin-button",
    checkOutButton: "checkout-button",
    statusText: "checkin-status",
  },

  // Task list
  taskList: {
    root: "task-list",
    taskRow: (id: string) => `task-row-${id}`,
    toggleButton: (id: string) => `task-toggle-${id}`,
  },

  // Status badge (generic)
  statusBadge: "status-badge",
} as const;
