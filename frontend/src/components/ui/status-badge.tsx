import { cn, getStatusColor, getPriorityColor, capitalize } from "@/lib/utils";
import type { WorkOrderStatus, InvoiceStatus, Priority } from "@/types";

interface StatusBadgeProps {
  status: WorkOrderStatus | InvoiceStatus;
  className?: string;
  testid?: string;
}

interface PriorityBadgeProps {
  priority: Priority;
  className?: string;
  testid?: string;
}

export function StatusBadge({ status, className, testid }: StatusBadgeProps) {
  return (
    <span
      data-testid={testid ?? "status-badge"}
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
        getStatusColor(status),
        className
      )}
    >
      {capitalize(status)}
    </span>
  );
}

export function PriorityBadge({ priority, className, testid }: PriorityBadgeProps) {
  return (
    <span
      data-testid={testid ?? "priority-badge"}
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
        getPriorityColor(priority),
        className
      )}
    >
      {capitalize(priority)}
    </span>
  );
}
