import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { format, formatDistanceToNow, parseISO } from "date-fns";
import type { WorkOrderStatus, InvoiceStatus, Priority } from "@/types";

/**
 * Merge Tailwind CSS classes safely.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/**
 * Format a number as currency string.
 */
export function formatCurrency(
  amount: number,
  currency: string = "USD"
): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

/**
 * Format a date string or Date object to a human-readable string.
 */
export function formatDate(
  date: string | Date,
  formatStr: string = "MMM d, yyyy"
): string {
  try {
    const d = typeof date === "string" ? parseISO(date) : date;
    return format(d, formatStr);
  } catch {
    return "Invalid date";
  }
}

/**
 * Format a date with time.
 */
export function formatDateTime(date: string | Date): string {
  return formatDate(date, "MMM d, yyyy h:mm a");
}

/**
 * Format a date as relative time ("2 hours ago").
 */
export function formatRelativeTime(date: string | Date): string {
  try {
    const d = typeof date === "string" ? parseISO(date) : date;
    return formatDistanceToNow(d, { addSuffix: true });
  } catch {
    return "some time ago";
  }
}

/**
 * Get initials from first and last name.
 */
export function getInitials(firstName: string, lastName: string): string {
  const f = firstName.trim().charAt(0).toUpperCase();
  const l = lastName.trim().charAt(0).toUpperCase();
  return `${f}${l}`;
}

/**
 * Map WorkOrderStatus or InvoiceStatus to Tailwind color classes.
 */
export function getStatusColor(
  status: WorkOrderStatus | InvoiceStatus
): string {
  const map: Record<string, string> = {
    // Work Order statuses
    draft: "bg-neutral-100 text-neutral-700",
    scheduled: "bg-primary-100 text-primary-700",
    in_progress: "bg-warning-100 text-warning-700",
    completed: "bg-success-100 text-success-700",
    cancelled: "bg-danger-100 text-danger-700",
    on_hold: "bg-neutral-200 text-neutral-600",
    // Invoice statuses
    sent: "bg-primary-100 text-primary-700",
    viewed: "bg-warning-100 text-warning-600",
    partial: "bg-warning-100 text-warning-700",
    paid: "bg-success-100 text-success-700",
    overdue: "bg-danger-100 text-danger-700",
    void: "bg-neutral-200 text-neutral-500",
  };
  return map[status] ?? "bg-neutral-100 text-neutral-700";
}

/**
 * Map Priority to Tailwind color classes.
 */
export function getPriorityColor(priority: Priority): string {
  const map: Record<Priority, string> = {
    low: "bg-neutral-100 text-neutral-600",
    normal: "bg-primary-100 text-primary-700",
    high: "bg-warning-100 text-warning-700",
    urgent: "bg-danger-100 text-danger-700",
  };
  return map[priority] ?? "bg-neutral-100 text-neutral-600";
}

/**
 * Truncate a string to a given length.
 */
export function truncate(str: string, length: number): string {
  if (str.length <= length) return str;
  return `${str.slice(0, length)}…`;
}

/**
 * Format distance from location in human-readable form.
 */
export function getDistanceLabel(meters: number): string {
  if (meters < 1000) {
    return `${Math.round(meters)}m away`;
  }
  return `${(meters / 1000).toFixed(1)}km away`;
}

/**
 * Capitalize the first letter of a string.
 */
export function capitalize(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1).replace(/_/g, " ");
}

/**
 * Build query string from params object (omitting undefined/null).
 */
export function buildQueryString(
  params: Record<string, string | number | boolean | undefined | null>
): string {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      searchParams.append(key, String(value));
    }
  });
  const qs = searchParams.toString();
  return qs ? `?${qs}` : "";
}

/**
 * Sleep for a given number of milliseconds.
 */
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
