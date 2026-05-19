"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { workOrdersApi } from "@/lib/api";
import type { WorkOrder, WorkOrderStatus } from "@/types";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function startOfWeek(date: Date): Date {
  const d = new Date(date);
  const day = d.getDay(); // 0=Sun
  const diff = day === 0 ? -6 : 1 - day; // Monday-based
  d.setDate(d.getDate() + diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

function addDays(date: Date, n: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + n);
  return d;
}

function toISO(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function formatWeekLabel(start: Date): string {
  const end = addDays(start, 6);
  const opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" };
  return `${start.toLocaleDateString("en-US", opts)} – ${end.toLocaleDateString("en-US", opts)}, ${end.getFullYear()}`;
}

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const STATUS_STYLES: Record<WorkOrderStatus, string> = {
  draft: "bg-neutral-100 text-neutral-700 border-neutral-300",
  scheduled: "bg-neutral-100 text-neutral-700 border-neutral-300",
  in_progress: "bg-primary-100 text-primary-800 border-primary-300",
  completed: "bg-success-100 text-success-800 border-success-300",
  cancelled: "bg-danger-100 text-danger-800 border-danger-300",
  on_hold: "bg-warning-100 text-warning-800 border-warning-300",
};

// ─── Work Order Chip ──────────────────────────────────────────────────────────

function WOChip({ wo }: { wo: WorkOrder }) {
  const style = STATUS_STYLES[wo.status] ?? STATUS_STYLES.scheduled;
  const time = wo.scheduled_start_time
    ? wo.scheduled_start_time.slice(0, 5)
    : "";

  return (
    <div
      className={`mb-1 rounded border px-2 py-1 text-xs leading-tight cursor-default ${style}`}
      title={wo.title}
    >
      <p className="font-medium truncate">{wo.title}</p>
      {time && <p className="opacity-75">{time}</p>}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function SchedulePage() {
  const [weekStart, setWeekStart] = useState<Date>(() =>
    startOfWeek(new Date())
  );

  const weekEnd = addDays(weekStart, 6);
  const after = toISO(weekStart);
  const before = toISO(weekEnd);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["work-orders", "schedule", after, before],
    queryFn: () =>
      workOrdersApi.list({
        scheduled_date_from: after,
        scheduled_date_to: before,
        page_size: 100,
      }),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });

  // Group WOs by scheduled_date
  const byDay = useMemo(() => {
    const map: Record<string, WorkOrder[]> = {};
    for (let i = 0; i < 7; i++) {
      map[toISO(addDays(weekStart, i))] = [];
    }
    for (const wo of data?.items ?? []) {
      const key = (wo.scheduled_date ?? "").slice(0, 10);
      if (map[key]) map[key].push(wo);
    }
    return map;
  }, [data, weekStart]);

  const todayStr = toISO(new Date());

  return (
    <div className="flex flex-col h-full p-4 md:p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <h1 className="text-xl font-semibold text-neutral-900 mr-auto">
          Schedule
        </h1>

        <button
          onClick={() => setWeekStart(startOfWeek(new Date()))}
          className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm font-medium text-neutral-700 hover:bg-neutral-50 transition-colors"
        >
          Today
        </button>

        <div className="flex items-center gap-1">
          <button
            onClick={() => setWeekStart((w) => addDays(w, -7))}
            aria-label="Previous week"
            className="rounded-md border border-neutral-300 bg-white p-1.5 text-neutral-600 hover:bg-neutral-50 transition-colors"
          >
            <svg viewBox="0 0 16 16" className="h-4 w-4" fill="currentColor">
              <path d="M10.5 3L5.5 8l5 5" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>

          <span className="min-w-[220px] text-center text-sm font-medium text-neutral-700">
            {formatWeekLabel(weekStart)}
          </span>

          <button
            onClick={() => setWeekStart((w) => addDays(w, 7))}
            aria-label="Next week"
            className="rounded-md border border-neutral-300 bg-white p-1.5 text-neutral-600 hover:bg-neutral-50 transition-colors"
          >
            <svg viewBox="0 0 16 16" className="h-4 w-4" fill="currentColor">
              <path d="M5.5 3l5 5-5 5" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      </div>

      {/* Status legend */}
      <div className="flex flex-wrap gap-3 mb-4 text-xs">
        {(["scheduled", "in_progress", "completed", "cancelled"] as const).map((s) => (
          <span key={s} className={`rounded-full border px-2.5 py-0.5 font-medium ${STATUS_STYLES[s]}`}>
            {s.replace("_", " ")}
          </span>
        ))}
      </div>

      {/* Calendar grid */}
      {isLoading ? (
        <div className="flex flex-1 items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
        </div>
      ) : isError ? (
        <div className="flex flex-1 items-center justify-center text-danger-600 text-sm">
          Failed to load schedule. Please try again.
        </div>
      ) : (
        <div className="grid grid-cols-7 gap-px rounded-lg border border-neutral-200 bg-neutral-200 overflow-hidden flex-1 min-h-0">
          {Array.from({ length: 7 }, (_, i) => {
            const day = addDays(weekStart, i);
            const key = toISO(day);
            const isToday = key === todayStr;
            const wos = byDay[key] ?? [];

            return (
              <div
                key={key}
                className="flex flex-col bg-white min-h-[120px]"
              >
                {/* Day header */}
                <div
                  className={`sticky top-0 px-2 py-2 text-center border-b border-neutral-100 ${
                    isToday
                      ? "bg-primary-50 text-primary-700"
                      : "bg-neutral-50 text-neutral-500"
                  }`}
                >
                  <p className="text-xs font-medium uppercase tracking-wide">
                    {DAY_NAMES[i]}
                  </p>
                  <p
                    className={`text-lg font-semibold leading-tight ${
                      isToday ? "text-primary-600" : "text-neutral-800"
                    }`}
                  >
                    {day.getDate()}
                  </p>
                </div>

                {/* Work order chips */}
                <div className="flex-1 overflow-y-auto p-1.5">
                  {wos.length === 0 ? (
                    <p className="text-center text-xs text-neutral-300 mt-2">—</p>
                  ) : (
                    wos.map((wo) => <WOChip key={wo.id} wo={wo} />)
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
