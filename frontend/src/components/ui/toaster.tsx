"use client";

import * as Toast from "@radix-ui/react-toast";
import { X, CheckCircle, AlertCircle, AlertTriangle, Info } from "lucide-react";
import { useNotifications } from "@/stores/ui-store";
import { cn } from "@/lib/utils";

const iconMap = {
  success: CheckCircle,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

const colorMap = {
  success: "border-success-200 bg-success-50 text-success-800",
  error: "border-danger-200 bg-danger-50 text-danger-800",
  warning: "border-warning-200 bg-warning-50 text-warning-800",
  info: "border-primary-200 bg-primary-50 text-primary-800",
};

const iconColorMap = {
  success: "text-success-500",
  error: "text-danger-500",
  warning: "text-warning-500",
  info: "text-primary-500",
};

export function Toaster() {
  const { items, dismiss } = useNotifications();

  return (
    <Toast.Provider swipeDirection="right">
      {items.slice(0, 5).map((notification) => {
        const Icon = iconMap[notification.type];
        return (
          <Toast.Root
            key={notification.id}
            className={cn(
              "pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl border p-4 shadow-lg data-[state=open]:animate-in data-[state=closed]:animate-out data-[swipe=end]:animate-out data-[state=closed]:fade-out-80 data-[state=closed]:slide-out-to-right-full data-[state=open]:slide-in-from-top-full",
              colorMap[notification.type]
            )}
            onOpenChange={(open) => {
              if (!open) dismiss(notification.id);
            }}
            duration={5000}
          >
            <Icon
              className={cn("mt-0.5 h-5 w-5 shrink-0", iconColorMap[notification.type])}
            />
            <div className="flex-1 space-y-1">
              <Toast.Title className="text-sm font-semibold">
                {notification.title}
              </Toast.Title>
              {notification.message && (
                <Toast.Description className="text-xs opacity-90">
                  {notification.message}
                </Toast.Description>
              )}
            </div>
            <Toast.Close
              className="mt-0.5 shrink-0 rounded p-0.5 opacity-60 transition-opacity hover:opacity-100"
              aria-label="Dismiss"
            >
              <X className="h-4 w-4" />
            </Toast.Close>
          </Toast.Root>
        );
      })}
      <Toast.Viewport className="fixed bottom-4 right-4 z-50 flex max-h-screen w-full max-w-sm flex-col gap-2 outline-none" />
    </Toast.Provider>
  );
}
