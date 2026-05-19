"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Search, Plus, MapPin, QrCode } from "lucide-react";
import { locationsApi } from "@/lib/api";
import { STALE_TIME } from "@/lib/query-config";
import { useClients } from "@/hooks/use-clients";
import { useDebounce } from "@/hooks/use-debounce";
import { PageHeader } from "@/components/ui/page-header";
import { DataTable, type Column } from "@/components/ui/data-table";
import { cn } from "@/lib/utils";
import type { Location } from "@/types";

export default function LocationsPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [clientFilter, setClientFilter] = useState<string>("");
  const [page, setPage] = useState(1);

  const debouncedSearch = useDebounce(search);

  // Load all clients for the filter dropdown
  const { data: clientsData } = useClients({ is_active: true, page_size: 200 });

  const { data, isLoading, isError } = useQuery({
    queryKey: ["locations", "list", debouncedSearch, clientFilter, page],
    queryFn: () =>
      locationsApi.list({
        client_id: clientFilter || undefined,
        page,
        page_size: 20,
      }),
    staleTime: STALE_TIME.LIST,
    placeholderData: (prev) => prev,
  });

  // Client-side search filter (API doesn't expose a search param for locations)
  const filteredItems = (data?.items ?? []).filter((loc) => {
    if (!debouncedSearch) return true;
    const q = debouncedSearch.toLowerCase();
    return (
      loc.name.toLowerCase().includes(q) ||
      loc.address.street.toLowerCase().includes(q) ||
      loc.address.city.toLowerCase().includes(q)
    );
  });

  const columns: Column<Location>[] = [
    {
      key: "name",
      header: "Name",
      accessor: (row) => (
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary-50">
            <MapPin className="h-4 w-4 text-primary-600" />
          </div>
          <span className="font-medium text-neutral-900">{row.name}</span>
        </div>
      ),
      sortable: true,
    },
    {
      key: "address",
      header: "Address",
      accessor: (row) => (
        <span className="text-neutral-600">
          {row.address.street}, {row.address.city}, {row.address.state} {row.address.zip}
        </span>
      ),
    },
    {
      key: "client_id",
      header: "Client",
      accessor: (row) => {
        const client = clientsData?.items.find((c) => c.id === row.client_id);
        return (
          <span className="text-neutral-700">{client?.name ?? row.client_id}</span>
        );
      },
    },
    {
      key: "is_active",
      header: "Status",
      accessor: (row) => (
        <span
          className={cn(
            "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
            row.is_active
              ? "bg-success-100 text-success-700"
              : "bg-neutral-100 text-neutral-500"
          )}
        >
          {row.is_active ? "Active" : "Inactive"}
        </span>
      ),
    },
    {
      key: "qr",
      header: "QR Code",
      accessor: (row) => (
        <button
          onClick={(e) => {
            e.stopPropagation();
            // In production, open a QR modal or download
            alert(`QR Token: ${row.qr_code_token}`);
          }}
          className="inline-flex items-center gap-1 rounded-md border border-neutral-200 bg-white px-2.5 py-1 text-xs font-medium text-neutral-600 hover:bg-neutral-50"
        >
          <QrCode className="h-3.5 w-3.5" />
          View
        </button>
      ),
    },
    {
      key: "actions",
      header: "",
      accessor: (row) => (
        <button
          onClick={(e) => {
            e.stopPropagation();
            router.push(`/locations/${row.id}`);
          }}
          className="text-xs font-medium text-primary-600 hover:text-primary-700"
        >
          Edit
        </button>
      ),
      className: "text-right",
    },
  ];

  return (
    <div className="flex flex-col">
      <PageHeader
        title="Locations"
        subtitle={data ? `${data.total} locations` : undefined}
        breadcrumbs={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Locations" },
        ]}
        actions={
          <button
            onClick={() => router.push("/locations/new")}
            className="btn-primary"
          >
            <Plus className="h-4 w-4" />
            Add Location
          </button>
        }
      />

      <div className="p-6 space-y-4">
        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-48 flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-400" />
            <input
              type="search"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Search locations…"
              className="input-field pl-9"
            />
          </div>

          <select
            value={clientFilter}
            onChange={(e) => {
              setClientFilter(e.target.value);
              setPage(1);
            }}
            className="input-field w-52"
          >
            <option value="">All Clients</option>
            {clientsData?.items.map((client) => (
              <option key={client.id} value={client.id}>
                {client.name}
              </option>
            ))}
          </select>
        </div>

        {isError ? (
          <div className="rounded-xl border border-danger-200 bg-danger-50 px-5 py-4 text-sm text-danger-700">
            Failed to load locations. Please try again.
          </div>
        ) : (
          <DataTable
            columns={columns}
            data={filteredItems}
            isLoading={isLoading}
            keyExtractor={(row) => row.id}
            emptyMessage="No locations found."
            emptyIcon={<MapPin className="h-8 w-8" />}
            page={page}
            pageSize={20}
            totalItems={data?.total ?? 0}
            onPageChange={setPage}
          />
        )}
      </div>
    </div>
  );
}
