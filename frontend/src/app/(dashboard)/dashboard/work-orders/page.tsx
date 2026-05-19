"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Search, Plus, SlidersHorizontal, X, RefreshCw } from "lucide-react";
import { useWorkOrders } from "@/hooks/use-work-orders";
import { useCrews } from "@/hooks/use-crews";
import { useDebounce } from "@/hooks/use-debounce";
import { DataTable, type Column } from "@/components/ui/data-table";
import { StatusBadge, PriorityBadge } from "@/components/ui/status-badge";
import { PageHeader } from "@/components/ui/page-header";
import { formatDate, cn } from "@/lib/utils";
import { useModals } from "@/stores/ui-store";
import type {
  WorkOrder,
  WorkOrderStatus,
  Priority,
} from "@/types";

const STATUS_OPTIONS: { value: WorkOrderStatus | "all"; label: string }[] = [
  { value: "all", label: "All Statuses" },
  { value: "draft", label: "Draft" },
  { value: "scheduled", label: "Scheduled" },
  { value: "in_progress", label: "In Progress" },
  { value: "completed", label: "Completed" },
  { value: "on_hold", label: "On Hold" },
  { value: "cancelled", label: "Cancelled" },
];

const PRIORITY_OPTIONS: { value: Priority | "all"; label: string }[] = [
  { value: "all", label: "All Priorities" },
  { value: "urgent", label: "Urgent" },
  { value: "high", label: "High" },
  { value: "normal", label: "Normal" },
  { value: "low", label: "Low" },
];

export default function WorkOrdersPage() {
  const router = useRouter();
  const { open } = useModals();

  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<WorkOrderStatus | "all">("all");
  const [priority, setPriority] = useState<Priority | "all">("all");
  const [crewId, setCrewId] = useState<string | "all">("all");
  const [page, setPage] = useState(1);
  const [showFilters, setShowFilters] = useState(false);

  const debouncedSearch = useDebounce(search);

  const { data: crewsData } = useCrews({ page_size: 100 });

  const { data, isLoading } = useWorkOrders({
    search: debouncedSearch || undefined,
    status: status === "all" ? undefined : status,
    priority: priority === "all" ? undefined : priority,
    crew_id: crewId === "all" ? undefined : crewId,
    page,
    page_size: 20,
  });

  const hasActiveFilters =
    search !== "" || status !== "all" || priority !== "all" || crewId !== "all";

  const clearFilters = () => {
    setSearch("");
    setStatus("all");
    setPriority("all");
    setCrewId("all");
    setPage(1);
  };

  const columns: Column<WorkOrder>[] = [
    {
      key: "id",
      header: "WO #",
      accessor: (row) => (
        <span className="font-mono text-xs text-neutral-500">
          {row.id.slice(0, 8).toUpperCase()}
        </span>
      ),
      className: "w-28",
    },
    {
      key: "title",
      header: "Title",
      accessor: (row) => (
        <span className="flex items-center gap-1.5 font-medium text-neutral-900">
          {row.work_type === "recurring" && (
            <span title="Recurring" className="inline-flex">
              <RefreshCw className="h-3.5 w-3.5 shrink-0 text-primary-500" />
            </span>
          )}
          {row.title}
        </span>
      ),
      sortable: true,
    },
    {
      key: "client",
      header: "Client",
      accessor: (row) => (
        <span className="text-neutral-600">{row.client_name ?? row.client_id}</span>
      ),
    },
    {
      key: "scheduled_date",
      header: "Scheduled",
      accessor: (row) => (
        <span className="whitespace-nowrap text-neutral-600">
          {formatDate(row.scheduled_date)}
        </span>
      ),
      sortable: true,
    },
    {
      key: "crew",
      header: "Crew",
      accessor: (row) =>
        row.crew_name ? (
          <span className="text-neutral-600">{row.crew_name}</span>
        ) : (
          <span className="text-neutral-400">—</span>
        ),
    },
    {
      key: "priority",
      header: "Priority",
      accessor: (row) => <PriorityBadge priority={row.priority} />,
    },
    {
      key: "status",
      header: "Status",
      accessor: (row) => <StatusBadge status={row.status} />,
    },
    {
      key: "sla",
      header: "SLA",
      accessor: (row) => {
        if (row.sla_met === undefined) return <span className="text-neutral-400">—</span>;
        return (
          <span
            className={cn(
              "text-xs font-medium",
              row.sla_met ? "text-success-600" : "text-danger-600"
            )}
          >
            {row.sla_met ? "Met" : "Missed"}
          </span>
        );
      },
    },
  ];

  return (
    <div>
      <PageHeader
        title="Work Orders"
        subtitle={data ? `${data.total} total work orders` : undefined}
        breadcrumbs={[{ label: "Dashboard", href: "/dashboard" }, { label: "Work Orders" }]}
        actions={
          <button
            onClick={() => open("create-work-order")}
            data-testid="wo-new-button"
            className="btn-primary"
          >
            <Plus className="h-4 w-4" />
            New Work Order
          </button>
        }
      />

      <div className="p-6">
        {/* Search + Filter bar */}
        <div className="mb-4 flex flex-wrap items-center gap-3">
          {/* Search */}
          <div className="relative flex-1 min-w-48">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-400" />
            <input
              type="search"
              data-testid="wo-search-input"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Search work orders…"
              className="input-field pl-9"
            />
          </div>

          {/* Filter toggle */}
          <button
            onClick={() => setShowFilters((v) => !v)}
            className={cn(
              "btn-secondary gap-2",
              showFilters && "border-primary-300 bg-primary-50 text-primary-700"
            )}
          >
            <SlidersHorizontal className="h-4 w-4" />
            Filters
            {hasActiveFilters && (
              <span className="flex h-4 w-4 items-center justify-center rounded-full bg-primary-600 text-[10px] font-bold text-white">
                !
              </span>
            )}
          </button>

          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-700"
            >
              <X className="h-3.5 w-3.5" />
              Clear filters
            </button>
          )}
        </div>

        {/* Filter panel */}
        {showFilters && (
          <div className="mb-4 flex flex-wrap gap-3 rounded-lg border border-neutral-200 bg-neutral-50 p-4">
            <div className="min-w-40">
              <label className="label text-xs">Status</label>
              <select
                value={status}
                onChange={(e) => {
                  setStatus(e.target.value as WorkOrderStatus | "all");
                  setPage(1);
                }}
                className="input-field text-sm"
              >
                {STATUS_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="min-w-40">
              <label className="label text-xs">Priority</label>
              <select
                value={priority}
                onChange={(e) => {
                  setPriority(e.target.value as Priority | "all");
                  setPage(1);
                }}
                className="input-field text-sm"
              >
                {PRIORITY_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="min-w-48">
              <label className="label text-xs">Crew</label>
              <select
                value={crewId}
                onChange={(e) => {
                  setCrewId(e.target.value);
                  setPage(1);
                }}
                className="input-field text-sm"
              >
                <option value="all">All Crews</option>
                {crewsData?.items.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}

        {/* Table */}
        <DataTable
          columns={columns}
          data={data?.items ?? []}
          isLoading={isLoading}
          keyExtractor={(row) => row.id}
          onRowClick={(row) => router.push(`/dashboard/work-orders/${row.id}`)}
          emptyMessage="No work orders found. Create your first one!"
          page={page}
          pageSize={20}
          totalItems={data?.total ?? 0}
          onPageChange={(p) => setPage(p)}
        />
      </div>
    </div>
  );
}
