"use client";

import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Download, Send, CreditCard, AlertCircle } from "lucide-react";
import { invoicesApi } from "@/lib/api";
import { STALE_TIME } from "@/lib/query-config";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { formatCurrency, formatDate, cn } from "@/lib/utils";
import type { Invoice, InvoiceStatus, PaginatedResponse } from "@/types";

interface InvoiceDetailPageProps {
  params: { id: string };
}

function LineItemsTable({
  items,
}: {
  items: { id: string; description: string; quantity: number; unit_price: number; line_total: number }[];
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-neutral-200">
      <table className="min-w-full divide-y divide-neutral-200 bg-white text-sm">
        <thead className="bg-neutral-50">
          <tr>
            {["Description", "Qty", "Unit Price", "Total"].map((h) => (
              <th
                key={h}
                className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-neutral-500"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-100">
          {items.map((item) => (
            <tr key={item.id} className="hover:bg-neutral-50">
              <td className="px-4 py-3 text-neutral-700">{item.description}</td>
              <td className="px-4 py-3 text-neutral-700">{item.quantity}</td>
              <td className="px-4 py-3 text-neutral-700">{formatCurrency(item.unit_price)}</td>
              <td className="px-4 py-3 font-medium text-neutral-900">{formatCurrency(item.line_total)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SkeletonBlock({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded bg-neutral-200", className)} />;
}

const ACTION_STATUSES: InvoiceStatus[] = ["draft", "sent", "overdue"];

export default function InvoiceDetailPage({ params }: InvoiceDetailPageProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { id } = params;

  const { data: invoice, isLoading, isError } = useQuery({
    queryKey: ["invoices", "detail", id],
    queryFn: () => invoicesApi.get(id),
    enabled: Boolean(id),
    staleTime: STALE_TIME.DETAIL,
    placeholderData: () => {
      const lists = queryClient.getQueriesData<PaginatedResponse<Invoice>>({
        queryKey: ["invoices", "list"],
      });
      for (const [, page] of lists) {
        const found = page?.items.find((inv) => inv.id === id);
        if (found) return found;
      }
    },
  });

  const updateMutation = useMutation({
    mutationFn: (status: InvoiceStatus) =>
      invoicesApi.update(id, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invoices", "detail", id] });
      queryClient.invalidateQueries({ queryKey: ["invoices", "list"] });
      queryClient.invalidateQueries({ queryKey: ["invoices", "summary"] });
    },
  });

  if (isError) {
    return (
      <div className="flex flex-col">
        <PageHeader
          title="Invoice"
          breadcrumbs={[
            { label: "Dashboard", href: "/dashboard" },
            { label: "Invoices", href: "/dashboard/invoices" },
            { label: "Not Found" },
          ]}
        />
        <div className="m-6 flex items-center gap-3 rounded-xl border border-danger-200 bg-danger-50 px-5 py-4 text-danger-700">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <p className="text-sm">Invoice not found or failed to load.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      <PageHeader
        title={isLoading ? "Loading…" : `Invoice ${invoice?.invoice_number ?? ""}`}
        breadcrumbs={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Invoices", href: "/dashboard/invoices" },
          { label: invoice?.invoice_number ?? "…" },
        ]}
        actions={
          <button
            onClick={() => router.push("/dashboard/invoices")}
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
            <SkeletonBlock className="h-20 w-full" />
            <SkeletonBlock className="h-32 w-full" />
            <SkeletonBlock className="h-48 w-full" />
          </div>
        ) : invoice ? (
          <>
            {/* Header card */}
            <div className="card p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-3">
                    <h2 className="text-xl font-bold text-neutral-900">
                      {invoice.invoice_number}
                    </h2>
                    <StatusBadge status={invoice.status} />
                  </div>
                  <p className="text-sm text-neutral-500">
                    Issued {formatDate(invoice.issue_date)} · Due {formatDate(invoice.due_date)}
                  </p>
                </div>

                {/* Action buttons */}
                <div className="flex flex-wrap items-center gap-2">
                  {invoice.status === "draft" && (
                    <button
                      onClick={() => updateMutation.mutate("sent")}
                      disabled={updateMutation.isPending}
                      className="btn-primary"
                    >
                      <Send className="h-4 w-4" />
                      Mark Sent
                    </button>
                  )}
                  {ACTION_STATUSES.includes(invoice.status) && invoice.status !== "draft" && (
                    <button
                      onClick={() => updateMutation.mutate("paid")}
                      disabled={updateMutation.isPending}
                      className="btn-primary"
                    >
                      <CreditCard className="h-4 w-4" />
                      Record Payment
                    </button>
                  )}
                  <button className="btn-secondary" onClick={() => window.print()}>
                    <Download className="h-4 w-4" />
                    Download PDF
                  </button>
                </div>
              </div>
            </div>

            {/* Client info */}
            <div className="card p-5">
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-neutral-500">
                Bill To
              </h3>
              <p className="text-sm font-medium text-neutral-900">
                {invoice.client_name ?? invoice.client_id}
              </p>
            </div>

            {/* Line items */}
            <div>
              <h3 className="mb-3 text-sm font-semibold text-neutral-700">Line Items</h3>
              {(invoice.line_items ?? []).length > 0 ? (
                <LineItemsTable items={invoice.line_items ?? []} />
              ) : (
                <p className="text-sm text-neutral-400">No line items.</p>
              )}
            </div>

            {/* Totals */}
            <div className="card ml-auto w-full max-w-xs p-5">
              <div className="space-y-2 text-sm">
                <div className="flex justify-between text-neutral-600">
                  <span>Subtotal</span>
                  <span>{formatCurrency(invoice.subtotal)}</span>
                </div>
                {invoice.discount_amount > 0 && (
                  <div className="flex justify-between text-success-600">
                    <span>Discount</span>
                    <span>-{formatCurrency(invoice.discount_amount)}</span>
                  </div>
                )}
                <div className="flex justify-between text-neutral-600">
                  <span>Tax</span>
                  <span>{formatCurrency(invoice.tax_amount)}</span>
                </div>
                <div className="flex justify-between border-t border-neutral-200 pt-2 text-base font-bold text-neutral-900">
                  <span>Total</span>
                  <span>{formatCurrency(invoice.total)}</span>
                </div>
              </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
