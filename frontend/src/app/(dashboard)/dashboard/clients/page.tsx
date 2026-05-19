"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Search, Plus, Building2, X } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useClients, useCreateClient } from "@/hooks/use-clients";
import { useDebounce } from "@/hooks/use-debounce";
import { DataTable, type Column } from "@/components/ui/data-table";
import { PageHeader } from "@/components/ui/page-header";
import { cn } from "@/lib/utils";
import type { Client } from "@/types";

const clientSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters"),
  code: z.string().min(2, "Code required").max(20).toUpperCase(),
  industry: z.string().min(1, "Industry required"),
  billing_email: z.string().email("Valid email required").optional().or(z.literal("")),
  is_active: z.boolean().default(true),
});

type ClientFormValues = z.infer<typeof clientSchema>;

const INDUSTRIES = [
  "Commercial Real Estate",
  "Healthcare",
  "Education",
  "Retail",
  "Manufacturing",
  "Hospitality",
  "Government",
  "Technology",
  "Other",
];

export default function ClientsPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [isActiveFilter, setIsActiveFilter] = useState<"all" | "active" | "inactive">("all");
  const [page, setPage] = useState(1);
  const [showCreatePanel, setShowCreatePanel] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const debouncedSearch = useDebounce(search);

  const { data, isLoading } = useClients({
    search: debouncedSearch || undefined,
    is_active: isActiveFilter === "all" ? undefined : isActiveFilter === "active",
    page,
    page_size: 20,
  });

  const createMutation = useCreateClient();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ClientFormValues>({
    resolver: zodResolver(clientSchema),
    defaultValues: { is_active: true },
  });

  const onCreateSubmit = async (values: ClientFormValues) => {
    setCreateError(null);
    try {
      await createMutation.mutateAsync({
        name: values.name,
        code: values.code,
        industry: values.industry,
        billing_email: values.billing_email || undefined,
        is_active: values.is_active,
      });
      reset();
      setShowCreatePanel(false);
    } catch (err: unknown) {
      setCreateError(
        (err as { message?: string })?.message ?? "Failed to create client."
      );
    }
  };

  const columns: Column<Client>[] = [
    {
      key: "name",
      header: "Client",
      accessor: (row) => (
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary-100 text-xs font-bold text-primary-700">
            {row.name.charAt(0)}
          </div>
          <div>
            <p className="font-medium text-neutral-900">{row.name}</p>
            <p className="text-xs text-neutral-500">{row.code}</p>
          </div>
        </div>
      ),
      sortable: true,
    },
    {
      key: "industry",
      header: "Industry",
      accessor: (row) => (
        <span className="text-neutral-600">{row.industry}</span>
      ),
    },
    {
      key: "billing_email",
      header: "Billing Email",
      accessor: (row) => (
        <span className="text-neutral-600">
          {row.billing_email ?? "—"}
        </span>
      ),
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
  ];

  return (
    <div className="flex h-full">
      {/* Main content */}
      <div className="flex-1 overflow-auto">
        <PageHeader
          title="Clients"
          subtitle={data ? `${data.total} clients` : undefined}
          breadcrumbs={[
            { label: "Dashboard", href: "/dashboard" },
            { label: "Clients" },
          ]}
          actions={
            <button
              onClick={() => setShowCreatePanel(true)}
              className="btn-primary"
            >
              <Plus className="h-4 w-4" />
              New Client
            </button>
          }
        />

        <div className="p-6">
          {/* Filters */}
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-48">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-400" />
              <input
                type="search"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
                placeholder="Search clients…"
                className="input-field pl-9"
              />
            </div>

            <div className="flex rounded-lg border border-neutral-200 bg-white">
              {(
                [
                  { value: "all", label: "All" },
                  { value: "active", label: "Active" },
                  { value: "inactive", label: "Inactive" },
                ] as const
              ).map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => {
                    setIsActiveFilter(opt.value);
                    setPage(1);
                  }}
                  className={cn(
                    "px-3 py-2 text-sm font-medium transition-colors first:rounded-l-lg last:rounded-r-lg",
                    isActiveFilter === opt.value
                      ? "bg-primary-600 text-white"
                      : "text-neutral-600 hover:bg-neutral-50"
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <DataTable
            columns={columns}
            data={data?.items ?? []}
            isLoading={isLoading}
            keyExtractor={(row) => row.id}
            emptyMessage="No clients found."
            emptyIcon={<Building2 className="h-8 w-8" />}
            page={page}
            pageSize={20}
            totalItems={data?.total ?? 0}
            onPageChange={setPage}
            onRowClick={(row) => router.push(`/dashboard/clients/${row.id}`)}
          />
        </div>
      </div>

      {/* Create Client Slide-over */}
      {showCreatePanel && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/20"
            onClick={() => setShowCreatePanel(false)}
          />
          <aside className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-neutral-200 bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-neutral-200 px-6 py-4">
              <h2 className="text-lg font-semibold text-neutral-900">
                New Client
              </h2>
              <button
                onClick={() => setShowCreatePanel(false)}
                className="rounded-lg p-2 text-neutral-400 hover:bg-neutral-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6">
              {createError && (
                <div className="mb-4 rounded-lg border border-danger-200 bg-danger-50 px-4 py-3 text-sm text-danger-700">
                  {createError}
                </div>
              )}

              <form
                id="create-client-form"
                onSubmit={handleSubmit(onCreateSubmit)}
                noValidate
              >
                <div className="space-y-4">
                  <div>
                    <label className="label">Company Name *</label>
                    <input
                      type="text"
                      {...register("name")}
                      className={cn(
                        "input-field",
                        errors.name && "border-danger-500"
                      )}
                      placeholder="Acme Corp"
                    />
                    {errors.name && (
                      <p className="error-message">{errors.name.message}</p>
                    )}
                  </div>

                  <div>
                    <label className="label">Client Code *</label>
                    <input
                      type="text"
                      {...register("code")}
                      className={cn(
                        "input-field uppercase",
                        errors.code && "border-danger-500"
                      )}
                      placeholder="ACME"
                    />
                    {errors.code && (
                      <p className="error-message">{errors.code.message}</p>
                    )}
                  </div>

                  <div>
                    <label className="label">Industry *</label>
                    <select
                      {...register("industry")}
                      className={cn(
                        "input-field",
                        errors.industry && "border-danger-500"
                      )}
                    >
                      <option value="">Select industry…</option>
                      {INDUSTRIES.map((i) => (
                        <option key={i} value={i}>
                          {i}
                        </option>
                      ))}
                    </select>
                    {errors.industry && (
                      <p className="error-message">
                        {errors.industry.message}
                      </p>
                    )}
                  </div>

                  <div>
                    <label className="label">Billing Email</label>
                    <input
                      type="email"
                      {...register("billing_email")}
                      className={cn(
                        "input-field",
                        errors.billing_email && "border-danger-500"
                      )}
                      placeholder="billing@acme.com"
                    />
                    {errors.billing_email && (
                      <p className="error-message">
                        {errors.billing_email.message}
                      </p>
                    )}
                  </div>

                  <label className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      {...register("is_active")}
                      className="h-4 w-4 rounded border-neutral-300 text-primary-600"
                    />
                    <span className="text-sm text-neutral-700">
                      Active client
                    </span>
                  </label>
                </div>
              </form>
            </div>

            <div className="flex items-center justify-end gap-3 border-t border-neutral-200 px-6 py-4">
              <button
                type="button"
                onClick={() => setShowCreatePanel(false)}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                type="submit"
                form="create-client-form"
                disabled={isSubmitting}
                className="btn-primary"
              >
                {isSubmitting ? "Creating…" : "Create Client"}
              </button>
            </div>
          </aside>
        </>
      )}
    </div>
  );
}
