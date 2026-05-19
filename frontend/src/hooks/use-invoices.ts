"use client";

import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryResult,
  UseMutationResult,
} from "@tanstack/react-query";
import { invoicesApi } from "@/lib/api";
import { STALE_TIME } from "@/lib/query-config";
import api from "@/lib/api";
import type { Invoice, InvoiceFilters, PaginatedResponse } from "@/types";

// ─── Query Keys ───────────────────────────────────────────────────────────────

export const invoiceKeys = {
  all: ["invoices"] as const,
  lists: () => [...invoiceKeys.all, "list"] as const,
  list: (filters: InvoiceFilters) => [...invoiceKeys.lists(), filters] as const,
  details: () => [...invoiceKeys.all, "detail"] as const,
  detail: (id: string) => [...invoiceKeys.details(), id] as const,
};

// ─── Record Payment payload ───────────────────────────────────────────────────

export interface RecordPaymentPayload {
  amount: number;
  payment_date: string;
  payment_method?: string;
  reference?: string;
}

// ─── List ─────────────────────────────────────────────────────────────────────

export function useInvoices(
  params: InvoiceFilters = {}
): UseQueryResult<PaginatedResponse<Invoice>> {
  return useQuery({
    queryKey: invoiceKeys.list(params),
    queryFn: () => invoicesApi.list(params),
    staleTime: STALE_TIME.LIST,
    placeholderData: (prev) => prev,
  });
}

// ─── Single ───────────────────────────────────────────────────────────────────

export function useInvoice(id: string): UseQueryResult<Invoice> {
  return useQuery({
    queryKey: invoiceKeys.detail(id),
    queryFn: () => invoicesApi.get(id),
    enabled: Boolean(id),
    staleTime: STALE_TIME.DETAIL,
  });
}

// ─── Create ───────────────────────────────────────────────────────────────────

export function useCreateInvoice(): UseMutationResult<
  Invoice,
  unknown,
  Omit<Invoice, "id" | "invoice_number" | "line_items">
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data) => invoicesApi.create(data),
    onSuccess: (newInvoice) => {
      queryClient.setQueryData<PaginatedResponse<Invoice>>(
        invoiceKeys.lists(),
        (old) => {
          if (!old) return old;
          return { ...old, items: [newInvoice, ...old.items], total: old.total + 1 };
        }
      );
      queryClient.invalidateQueries({ queryKey: invoiceKeys.lists() });
    },
  });
}

// ─── Update ───────────────────────────────────────────────────────────────────

export function useUpdateInvoice(): UseMutationResult<
  Invoice,
  unknown,
  { id: string; data: Partial<Omit<Invoice, "id" | "invoice_number">> }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }) => invoicesApi.update(id, data),
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({ queryKey: invoiceKeys.detail(id) });
      const previous = queryClient.getQueryData<Invoice>(invoiceKeys.detail(id));
      if (previous) {
        queryClient.setQueryData<Invoice>(invoiceKeys.detail(id), {
          ...previous,
          ...data,
        });
      }
      return { previous };
    },
    onError: (_err, { id }, context) => {
      if (context?.previous) {
        queryClient.setQueryData(invoiceKeys.detail(id), context.previous);
      }
    },
    onSettled: (_data, _err, { id }) => {
      queryClient.invalidateQueries({ queryKey: invoiceKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: invoiceKeys.lists() });
    },
  });
}

// ─── Record Payment ───────────────────────────────────────────────────────────

export function useRecordPayment(
  invoiceId: string
): UseMutationResult<Invoice, unknown, RecordPaymentPayload> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data) =>
      api
        .post<Invoice>(`/api/v1/invoices/${invoiceId}/record-payment`, data)
        .then((r) => r.data),
    onSuccess: (updated) => {
      queryClient.setQueryData(invoiceKeys.detail(invoiceId), updated);
      queryClient.invalidateQueries({ queryKey: invoiceKeys.lists() });
    },
  });
}
