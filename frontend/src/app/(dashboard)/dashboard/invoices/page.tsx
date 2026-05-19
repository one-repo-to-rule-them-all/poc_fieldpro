"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Plus, FileText, AlertCircle } from "lucide-react";
import { invoicesApi } from "@/lib/api";
import { STALE_TIME } from "@/lib/query-config";
import { PageHeader } from "@/components/ui/page-header";
import { DataTable, type Column } from "@/components/ui/data-table";
import { StatusBadge } from "@/components/ui/status-badge";
import { formatCurrency, formatDate, cn } from "@/lib/utils";
import type { Invoice, InvoiceStatus } from "@/types";

const STATUS_TABS: { value: InvoiceStatus | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "draft", label: "Draft" },
  { value: "sent", label: "Sent" },
  { value: "paid", label: "Paid" },
  { value: "overdue", label: "Overdue" },
];

export default function InvoicesPage() {
  const router = useRouter();
  const [statusFilter, setStatusFilter] = useState<InvoiceStatus | "all">("all");
  const [page, setPage] = useState(1);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["invoices", "list", statusFilter, page],
    queryFn: () =>
      invoicesApi.list({
        status: statusFilter === "all" ? undefined : statusFilter,
        page,
        page_size: 20,
      }),
    staleTime: STALE_TIME.LIST,
    placeholderData: (prev) => prev,
  });

  // Summary stats derived from current full list (all statuses)
  const { data: allInvoices } = useQuery({
    queryKey: ["invoices", "summary"],
    queryFn: () => invoicesApi.list({ page: 1, page_size: 100 }),
    staleTime: STALE_TIME.SUMMARY,
  });

  const summary = allInvoices?.items.reduce(
    (acc, inv) => {
      if (inv.status === "paid") acc.paid += inv.total;
      else if (inv.status !== "void") acc.outstanding += inv.total;
      if (inv.status === "overdue") acc.overdueCount++;
      return acc;
    },
    { outstanding: 0, paid: 0, overdueCount: 0 }
  ) ?? { outstanding: 0, paid: 0, overdueCount: 0 };

  const columns: Column<Invoice>[] = [
    {
      key: "invoice_number",
      header: "Invoice #",
      accessor: (row) => (
        <span className="font-mono text-sm font-medium text-neutral-900">
          {row.invoice_number}
        </span>
      ),
      sortable: true,
    },
    {
      key: "client_id",
      header: "Client",
      accessor: (row) => (
        <span className="text-neutral-700">{row.client_name ?? row.client_id}</span>
      ),
    },
    {
      key: "total",
      header: "Amount",
      accessor: (row) => (
        <span className="font-medium text-neutral-900">
          {formatCurrency(row.total)}
        </span>
      ),
      sortable: true,
    },
    {
      key: "status",
      header: "Status",
      accessor: (row) => <StatusBadge status={row.status} />,
    },
    {
      key: "due_date",
      header: "Due Date",
      accessor: (row) => (
        <span
          className={cn(
            "text-sm",
            row.status === "overdue" ? "font-medium text-danger-600" : "text-neutral-600"
          )}
        >
          {formatDate(row.due_date)}
        </span>
      ),
      sortable: true,
    },
    {
      key: "actions",
      header: "",
      accessor: (row) => (
        <button
          onClick={(e) => {
            e.stopPropagation();
            router.push(`/dashboard/invoices/${row.id}`);
          }}
          className="text-xs font-medium text-primary-600 hover:text-primary-700"
        >
          View
        </button>
      ),
      className: "text-right",
    },
  ];

  return (
    <div className="flex flex-col">
      <PageHeader
        title="Invoices"
        subtitle={data ? `${data.total} invoices` : undefined}
        breadcrumbs={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Invoices" },
        ]}
        actions={
          <button
            onClick={() => router.push("/dashboard/invoices/new")}
            className="btn-primary"
          >
            <Plus className="h-4 w-4" />
            New Invoice
          </button>
        }
      />

      <div className="p-6 space-y-5">
        {/* Summary bar */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="card flex items-center gap-4 p-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-warning-50">
              <FileText className="h-5 w-5 text-warning-600" />
            </div>
            <div>
              <p className="text-xs font-medium text-neutral-500">Total Outstanding</p>
              <p className="text-lg font-bold text-neutral-900">
                {formatCurrency(summary.outstanding)}
              </p>
            </div>
          </div>
          <div className="card flex items-center gap-4 p-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-success-50">
              <FileText className="h-5 w-5 text-success-600" />
            </div>
            <div>
              <p className="text-xs font-medium text-neutral-500">Total Paid</p>
              <p className="text-lg font-bold text-neutral-900">
                {formatCurrency(summary.paid)}
              </p>
            </div>
          </div>
          <div className="card flex items-center gap-4 p-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-danger-50">
              <AlertCircle className="h-5 w-5 text-danger-600" />
            </div>
            <div>
              <p className="text-xs font-medium text-neutral-500">Overdue</p>
              <p className="text-lg font-bold text-neutral-900">
                {summary.overdueCount} invoice{summary.overdueCount !== 1 ? "s" : ""}
              </p>
            </div>
          </div>
        </div>

        {/* Status filter tabs */}
        <div className="flex rounded-lg border border-neutral-200 bg-white w-fit">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => {
                setStatusFilter(tab.value);
                setPage(1);
              }}
              className={cn(
                "px-4 py-2 text-sm font-medium transition-colors first:rounded-l-lg last:rounded-r-lg",
                statusFilter === tab.value
                  ? "bg-primary-600 text-white"
                  : "text-neutral-600 hover:bg-neutral-50"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {isError ? (
          <div className="rounded-xl border border-danger-200 bg-danger-50 px-5 py-4 text-sm text-danger-700">
            Failed to load invoices. Please try again.
          </div>
        ) : (
          <DataTable
            columns={columns}
            data={data?.items ?? []}
            isLoading={isLoading}
            keyExtractor={(row) => row.id}
            emptyMessage="No invoices found."
            emptyIcon={<FileText className="h-8 w-8" />}
            onRowClick={(row) => router.push(`/dashboard/invoices/${row.id}`)}
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
