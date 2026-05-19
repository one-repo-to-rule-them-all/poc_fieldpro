"use client";

import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Building2,
  MapPin,
  ClipboardList,
  AlertCircle,
  Mail,
  Phone,
  FileText,
} from "lucide-react";
import {
  useClient,
  useClientLocations,
  useClientWorkOrders,
} from "@/hooks/use-clients";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge, PriorityBadge } from "@/components/ui/status-badge";
import { DataTable, type Column } from "@/components/ui/data-table";
import { cn, formatDate } from "@/lib/utils";
import type { Location, WorkOrder } from "@/types";

interface ClientDetailPageProps {
  params: { id: string };
}

function SkeletonBlock({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded bg-neutral-200", className)} />;
}

export default function ClientDetailPage({ params }: ClientDetailPageProps) {
  const router = useRouter();
  const { id } = params;

  const { data: client, isLoading, isError } = useClient(id);
  const { data: locationsData, isLoading: locationsLoading } = useClientLocations(id, {
    page_size: 10,
  });
  const { data: workOrdersData, isLoading: woLoading } = useClientWorkOrders(id, {
    page_size: 5,
  });

  const locationColumns: Column<Location>[] = [
    {
      key: "name",
      header: "Location",
      accessor: (row) => (
        <div className="flex items-center gap-2">
          <MapPin className="h-3.5 w-3.5 shrink-0 text-neutral-400" />
          <span className="font-medium text-neutral-900">{row.name}</span>
        </div>
      ),
    },
    {
      key: "address",
      header: "Address",
      accessor: (row) => {
        const addr = row.address;
        if (!addr) return <span className="text-neutral-400">—</span>;
        return (
          <span className="text-neutral-600">
            {[addr.street, addr.city, addr.state].filter(Boolean).join(", ")}
          </span>
        );
      },
    },
    {
      key: "is_active",
      header: "Status",
      accessor: (row) => (
        <span
          className={cn(
            "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold",
            row.is_active
              ? "bg-success-100 text-success-700"
              : "bg-neutral-100 text-neutral-500"
          )}
        >
          {row.is_active ? "Active" : "Inactive"}
        </span>
      ),
    },
  ];

  const woColumns: Column<WorkOrder>[] = [
    {
      key: "title",
      header: "Work Order",
      accessor: (row) => (
        <span className="font-medium text-neutral-900">{row.title}</span>
      ),
    },
    {
      key: "status",
      header: "Status",
      accessor: (row) => <StatusBadge status={row.status} />,
    },
    {
      key: "priority",
      header: "Priority",
      accessor: (row) => <PriorityBadge priority={row.priority} />,
    },
    {
      key: "scheduled_date",
      header: "Scheduled",
      accessor: (row) => (
        <span className="text-sm text-neutral-600">
          {row.scheduled_date ? formatDate(row.scheduled_date) : "—"}
        </span>
      ),
    },
  ];

  if (isError) {
    return (
      <div className="flex flex-col">
        <PageHeader
          title="Client"
          breadcrumbs={[
            { label: "Dashboard", href: "/dashboard" },
            { label: "Clients", href: "/dashboard/clients" },
            { label: "Not Found" },
          ]}
        />
        <div className="m-6 flex items-center gap-3 rounded-xl border border-danger-200 bg-danger-50 px-5 py-4 text-danger-700">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <p className="text-sm">Client not found or failed to load.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      <PageHeader
        title={isLoading ? "Loading…" : (client?.name ?? "Client")}
        breadcrumbs={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Clients", href: "/dashboard/clients" },
          { label: client?.name ?? "…" },
        ]}
        actions={
          <button
            onClick={() => router.push("/dashboard/clients")}
            className="btn-secondary"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </button>
        }
      />

      <div className="p-6 space-y-6">
        {isLoading ? (
          <div className="space-y-4">
            <SkeletonBlock className="h-28 w-full" />
            <SkeletonBlock className="h-48 w-full" />
            <SkeletonBlock className="h-48 w-full" />
          </div>
        ) : client ? (
          <>
            {/* Header card */}
            <div className="card p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="flex items-center gap-4">
                  <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-primary-100 text-xl font-bold text-primary-700">
                    {client.name.charAt(0)}
                  </div>
                  <div>
                    <div className="flex items-center gap-3">
                      <h2 className="text-xl font-bold text-neutral-900">
                        {client.name}
                      </h2>
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
                          client.is_active
                            ? "bg-success-100 text-success-700"
                            : "bg-neutral-100 text-neutral-500"
                        )}
                      >
                        {client.is_active ? "Active" : "Inactive"}
                      </span>
                    </div>
                    <p className="mt-0.5 text-sm text-neutral-500">
                      {client.code}
                      {client.industry && ` · ${client.industry}`}
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-4 text-sm text-neutral-600">
                  {client.billing_email && (
                    <a
                      href={`mailto:${client.billing_email}`}
                      className="flex items-center gap-1.5 hover:text-primary-600 transition-colors"
                    >
                      <Mail className="h-4 w-4" />
                      {client.billing_email}
                    </a>
                  )}
                  {client.billing_phone && (
                    <a
                      href={`tel:${client.billing_phone}`}
                      className="flex items-center gap-1.5 hover:text-primary-600 transition-colors"
                    >
                      <Phone className="h-4 w-4" />
                      {client.billing_phone}
                    </a>
                  )}
                  {client.location_count !== undefined && (
                    <span className="flex items-center gap-1.5">
                      <MapPin className="h-4 w-4 text-neutral-400" />
                      {client.location_count} location{client.location_count !== 1 ? "s" : ""}
                    </span>
                  )}
                </div>
              </div>

              {client.notes && (
                <div className="mt-4 rounded-lg bg-neutral-50 px-4 py-3">
                  <p className="text-sm text-neutral-600">{client.notes}</p>
                </div>
              )}
            </div>

            {/* Locations */}
            <div className="card overflow-hidden">
              <div className="flex items-center justify-between border-b border-neutral-100 px-5 py-4">
                <div className="flex items-center gap-2">
                  <MapPin className="h-4 w-4 text-neutral-400" />
                  <h3 className="font-semibold text-neutral-900">
                    Service Locations
                  </h3>
                  {locationsData && (
                    <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-xs font-medium text-neutral-600">
                      {locationsData.total}
                    </span>
                  )}
                </div>
              </div>
              <DataTable
                columns={locationColumns}
                data={locationsData?.items ?? []}
                isLoading={locationsLoading}
                keyExtractor={(row) => row.id}
                emptyMessage="No locations yet."
                emptyIcon={<MapPin className="h-7 w-7" />}
                onRowClick={(row) =>
                  router.push(`/dashboard/locations?client_id=${client.id}&highlight=${row.id}`)
                }
              />
            </div>

            {/* Work Orders */}
            <div className="card overflow-hidden">
              <div className="flex items-center justify-between border-b border-neutral-100 px-5 py-4">
                <div className="flex items-center gap-2">
                  <ClipboardList className="h-4 w-4 text-neutral-400" />
                  <h3 className="font-semibold text-neutral-900">
                    Recent Work Orders
                  </h3>
                  {workOrdersData && (
                    <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-xs font-medium text-neutral-600">
                      {workOrdersData.total}
                    </span>
                  )}
                </div>
                <button
                  onClick={() =>
                    router.push(
                      `/dashboard/work-orders?client_id=${client.id}`
                    )
                  }
                  className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-primary-600 hover:bg-primary-50 transition-colors"
                >
                  View all
                  <FileText className="h-3 w-3" />
                </button>
              </div>
              <DataTable
                columns={woColumns}
                data={workOrdersData?.items ?? []}
                isLoading={woLoading}
                keyExtractor={(row) => row.id}
                emptyMessage="No work orders yet."
                emptyIcon={<ClipboardList className="h-7 w-7" />}
                onRowClick={(row) =>
                  router.push(`/dashboard/work-orders/${row.id}`)
                }
              />
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
