"use client";

import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryResult,
  UseMutationResult,
} from "@tanstack/react-query";
import { locationsApi } from "@/lib/api";
import { STALE_TIME } from "@/lib/query-config";
import type { Location, PaginatedResponse } from "@/types";

// ─── Filters type ─────────────────────────────────────────────────────────────

export interface LocationFilters {
  client_id?: string;
  is_active?: boolean;
  page?: number;
  page_size?: number;
}

// ─── Query Keys ───────────────────────────────────────────────────────────────

export const locationKeys = {
  all: ["locations"] as const,
  lists: () => [...locationKeys.all, "list"] as const,
  list: (filters: LocationFilters) =>
    [...locationKeys.lists(), filters] as const,
  details: () => [...locationKeys.all, "detail"] as const,
  detail: (id: string) => [...locationKeys.details(), id] as const,
};

// ─── List ─────────────────────────────────────────────────────────────────────

export function useLocations(
  params: LocationFilters = {}
): UseQueryResult<PaginatedResponse<Location>> {
  return useQuery({
    queryKey: locationKeys.list(params),
    queryFn: () => locationsApi.list(params),
    staleTime: STALE_TIME.LIST,
    placeholderData: (prev) => prev,
  });
}

// ─── Single ───────────────────────────────────────────────────────────────────

export function useLocation(id: string): UseQueryResult<Location> {
  return useQuery({
    queryKey: locationKeys.detail(id),
    queryFn: () => locationsApi.get(id),
    enabled: Boolean(id),
    staleTime: STALE_TIME.DETAIL,
  });
}

// ─── Create ───────────────────────────────────────────────────────────────────

export function useCreateLocation(): UseMutationResult<
  Location,
  unknown,
  Omit<Location, "id" | "qr_code_token">
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data) => locationsApi.create(data),
    onSuccess: (newLocation) => {
      queryClient.setQueryData<PaginatedResponse<Location>>(
        locationKeys.lists(),
        (old) => {
          if (!old) return old;
          return {
            ...old,
            items: [newLocation, ...old.items],
            total: old.total + 1,
          };
        }
      );
      queryClient.invalidateQueries({ queryKey: locationKeys.lists() });
    },
  });
}

// ─── Update ───────────────────────────────────────────────────────────────────

export function useUpdateLocation(): UseMutationResult<
  Location,
  unknown,
  { id: string; data: Partial<Omit<Location, "id" | "qr_code_token">> }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }) => locationsApi.update(id, data),
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({ queryKey: locationKeys.detail(id) });
      const previous = queryClient.getQueryData<Location>(
        locationKeys.detail(id)
      );
      if (previous) {
        queryClient.setQueryData<Location>(locationKeys.detail(id), {
          ...previous,
          ...data,
        });
      }
      return { previous };
    },
    onError: (_err, { id }, context) => {
      if (context?.previous) {
        queryClient.setQueryData(locationKeys.detail(id), context.previous);
      }
    },
    onSettled: (_data, _err, { id }) => {
      queryClient.invalidateQueries({ queryKey: locationKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: locationKeys.lists() });
    },
  });
}

// ─── Delete ───────────────────────────────────────────────────────────────────

export function useDeleteLocation(): UseMutationResult<void, unknown, string> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id) => locationsApi.delete(id),
    onSuccess: (_data, id) => {
      queryClient.removeQueries({ queryKey: locationKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: locationKeys.lists() });
    },
  });
}
