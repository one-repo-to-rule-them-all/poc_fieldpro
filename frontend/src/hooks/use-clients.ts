"use client";

import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryResult,
  UseMutationResult,
} from "@tanstack/react-query";
import { clientsApi } from "@/lib/api";
import { STALE_TIME } from "@/lib/query-config";
import type { Client, ClientFilters, Location, WorkOrder, PaginatedResponse } from "@/types";

// ─── Query Keys ───────────────────────────────────────────────────────────────

export const clientKeys = {
  all: ["clients"] as const,
  lists: () => [...clientKeys.all, "list"] as const,
  list: (filters: ClientFilters) => [...clientKeys.lists(), filters] as const,
  details: () => [...clientKeys.all, "detail"] as const,
  detail: (id: string) => [...clientKeys.details(), id] as const,
};

// ─── List ─────────────────────────────────────────────────────────────────────

export function useClients(
  params: ClientFilters = {}
): UseQueryResult<PaginatedResponse<Client>> {
  return useQuery({
    queryKey: clientKeys.list(params),
    queryFn: () => clientsApi.list(params),
    staleTime: STALE_TIME.LIST,
    placeholderData: (previousData) => previousData,
  });
}

// ─── Single ───────────────────────────────────────────────────────────────────

export function useClient(id: string): UseQueryResult<Client> {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: clientKeys.detail(id),
    queryFn: () => clientsApi.get(id),
    enabled: Boolean(id),
    staleTime: STALE_TIME.DETAIL,
    placeholderData: () => {
      const lists = queryClient.getQueriesData<PaginatedResponse<Client>>({
        queryKey: clientKeys.lists(),
      });
      for (const [, page] of lists) {
        const found = page?.items.find((c) => c.id === id);
        if (found) return found;
      }
    },
  });
}

// ─── Client Locations ─────────────────────────────────────────────────────────

export function useClientLocations(
  clientId: string,
  params: { is_active?: boolean; page?: number; page_size?: number } = {}
): UseQueryResult<PaginatedResponse<Location>> {
  return useQuery({
    queryKey: [...clientKeys.detail(clientId), "locations", params],
    queryFn: () => clientsApi.listLocations(clientId, params),
    enabled: Boolean(clientId),
    staleTime: STALE_TIME.LIST,
    placeholderData: (prev) => prev,
  });
}

// ─── Client Work Orders ───────────────────────────────────────────────────────

export function useClientWorkOrders(
  clientId: string,
  params: { status?: string; page?: number; page_size?: number } = {}
): UseQueryResult<PaginatedResponse<WorkOrder>> {
  return useQuery({
    queryKey: [...clientKeys.detail(clientId), "work-orders", params],
    queryFn: () => clientsApi.listWorkOrders(clientId, params),
    enabled: Boolean(clientId),
    staleTime: STALE_TIME.LIST,
    placeholderData: (prev) => prev,
  });
}

// ─── Create ───────────────────────────────────────────────────────────────────

export function useCreateClient(): UseMutationResult<
  Client,
  unknown,
  Omit<Client, "id" | "tenant_id" | "contacts">
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data) => clientsApi.create(data),
    onSuccess: (newClient) => {
      queryClient.setQueryData<PaginatedResponse<Client>>(
        clientKeys.lists(),
        (old) => {
          if (!old) return old;
          return {
            ...old,
            items: [newClient, ...old.items],
            total: old.total + 1,
          };
        }
      );
      queryClient.invalidateQueries({ queryKey: clientKeys.lists() });
    },
  });
}

// ─── Update ───────────────────────────────────────────────────────────────────

export function useUpdateClient(): UseMutationResult<
  Client,
  unknown,
  { id: string; data: Partial<Omit<Client, "id" | "tenant_id">> }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }) => clientsApi.update(id, data),
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({ queryKey: clientKeys.detail(id) });
      const previous = queryClient.getQueryData<Client>(clientKeys.detail(id));
      if (previous) {
        queryClient.setQueryData<Client>(clientKeys.detail(id), {
          ...previous,
          ...data,
        });
      }
      return { previous };
    },
    onError: (_err, { id }, context) => {
      if (context?.previous) {
        queryClient.setQueryData(clientKeys.detail(id), context.previous);
      }
    },
    onSettled: (_data, _err, { id }) => {
      queryClient.invalidateQueries({ queryKey: clientKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: clientKeys.lists() });
    },
  });
}

// ─── Delete ───────────────────────────────────────────────────────────────────

export function useDeleteClient(): UseMutationResult<void, unknown, string> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id) => clientsApi.delete(id),
    onSuccess: (_data, id) => {
      queryClient.removeQueries({ queryKey: clientKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: clientKeys.lists() });
    },
  });
}
