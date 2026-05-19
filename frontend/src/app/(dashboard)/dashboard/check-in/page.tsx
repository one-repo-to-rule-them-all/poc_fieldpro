"use client";

import { useRouter } from "next/navigation";
import { MapPin, ClipboardList, ChevronRight, Loader2, AlertTriangle } from "lucide-react";
import { useWorkOrders } from "@/hooks/use-work-orders";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge, PriorityBadge } from "@/components/ui/status-badge";
import { formatDate } from "@/lib/utils";

export default function CheckInPage() {
  const router = useRouter();

  const { data, isLoading } = useWorkOrders({
    status: "in_progress",
    page_size: 20,
  });

  const { data: scheduledData, isLoading: scheduledLoading } = useWorkOrders({
    status: "scheduled",
    page_size: 20,
  });

  const activeOrders = data?.items ?? [];
  const scheduledOrders = scheduledData?.items ?? [];
  const allOrders = [...activeOrders, ...scheduledOrders];
  const loading = isLoading || scheduledLoading;

  return (
    <div className="flex flex-col">
      <PageHeader
        title="Check In"
        subtitle="Tap a work order to check in at the site"
        breadcrumbs={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Check In" },
        ]}
      />

      <div className="p-6 space-y-4 max-w-2xl">
        {/* Instructions card */}
        <div className="rounded-xl border border-primary-200 bg-primary-50 px-5 py-4">
          <div className="flex items-start gap-3">
            <MapPin className="mt-0.5 h-5 w-5 shrink-0 text-primary-600" />
            <div>
              <p className="text-sm font-medium text-primary-900">GPS Check-In</p>
              <p className="mt-0.5 text-sm text-primary-700">
                Select your active work order below. Your location will be recorded when you check in.
                Stay within the site geofence for a valid check-in.
              </p>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="flex h-40 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-primary-500" />
          </div>
        ) : allOrders.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-neutral-200 bg-white py-12 text-center">
            <AlertTriangle className="h-10 w-10 text-neutral-300" />
            <div>
              <p className="font-medium text-neutral-700">No active work orders</p>
              <p className="mt-1 text-sm text-neutral-400">
                You have no in-progress or scheduled work orders right now.
              </p>
            </div>
            <button
              onClick={() => router.push("/dashboard/work-orders")}
              className="btn-secondary mt-2 text-sm"
            >
              View all work orders
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            {activeOrders.length > 0 && (
              <p className="text-xs font-semibold uppercase tracking-wide text-neutral-400 px-1">
                In Progress
              </p>
            )}
            {activeOrders.map((wo) => (
              <button
                key={wo.id}
                onClick={() => router.push(`/dashboard/work-orders/${wo.id}`)}
                className="flex w-full items-center gap-4 rounded-xl border border-neutral-200 bg-white px-5 py-4 text-left transition-colors hover:border-primary-300 hover:bg-primary-50"
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary-100">
                  <ClipboardList className="h-5 w-5 text-primary-600" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-neutral-900 truncate">{wo.title}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <StatusBadge status={wo.status} />
                    <PriorityBadge priority={wo.priority} />
                    {wo.location_name && (
                      <span className="flex items-center gap-1 text-xs text-neutral-500">
                        <MapPin className="h-3 w-3" />
                        {wo.location_name}
                      </span>
                    )}
                  </div>
                </div>
                <ChevronRight className="h-5 w-5 shrink-0 text-neutral-300" />
              </button>
            ))}

            {scheduledOrders.length > 0 && (
              <>
                <p className="pt-2 text-xs font-semibold uppercase tracking-wide text-neutral-400 px-1">
                  Scheduled Today
                </p>
                {scheduledOrders.map((wo) => (
                  <button
                    key={wo.id}
                    onClick={() => router.push(`/dashboard/work-orders/${wo.id}`)}
                    className="flex w-full items-center gap-4 rounded-xl border border-neutral-200 bg-white px-5 py-4 text-left transition-colors hover:border-primary-300 hover:bg-primary-50"
                  >
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-neutral-100">
                      <ClipboardList className="h-5 w-5 text-neutral-500" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-neutral-900 truncate">{wo.title}</p>
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        <StatusBadge status={wo.status} />
                        <span className="text-xs text-neutral-500">
                          {formatDate(wo.scheduled_date)}
                        </span>
                        {wo.location_name && (
                          <span className="flex items-center gap-1 text-xs text-neutral-500">
                            <MapPin className="h-3 w-3" />
                            {wo.location_name}
                          </span>
                        )}
                      </div>
                    </div>
                    <ChevronRight className="h-5 w-5 shrink-0 text-neutral-300" />
                  </button>
                ))}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
