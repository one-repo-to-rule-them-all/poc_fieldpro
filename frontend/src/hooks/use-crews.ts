"use client";

import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryResult,
  UseMutationResult,
} from "@tanstack/react-query";
import { crewsApi } from "@/lib/api";
import { STALE_TIME } from "@/lib/query-config";
import type { Crew, CrewMember, PaginatedResponse } from "@/types";

// ─── Filters type ─────────────────────────────────────────────────────────────

export interface CrewFilters {
  search?: string;
  page?: number;
  page_size?: number;
}

// ─── Query Keys ───────────────────────────────────────────────────────────────

export const crewKeys = {
  all: ["crews"] as const,
  lists: () => [...crewKeys.all, "list"] as const,
  list: (filters: CrewFilters) => [...crewKeys.lists(), filters] as const,
  details: () => [...crewKeys.all, "detail"] as const,
  detail: (id: string) => [...crewKeys.details(), id] as const,
};

// ─── List ─────────────────────────────────────────────────────────────────────

export function useCrews(
  params: CrewFilters = {}
): UseQueryResult<PaginatedResponse<Crew>> {
  return useQuery({
    queryKey: crewKeys.list(params),
    queryFn: () => crewsApi.list(params),
    staleTime: STALE_TIME.LIST,
    placeholderData: (prev) => prev,
  });
}

// ─── Single ───────────────────────────────────────────────────────────────────

export function useCrew(id: string): UseQueryResult<Crew> {
  return useQuery({
    queryKey: crewKeys.detail(id),
    queryFn: () => crewsApi.get(id),
    enabled: Boolean(id),
    staleTime: STALE_TIME.DETAIL,
  });
}

// ─── Create ───────────────────────────────────────────────────────────────────

export function useCreateCrew(): UseMutationResult<
  Crew,
  unknown,
  Omit<Crew, "id" | "members">
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data) => crewsApi.create(data),
    onSuccess: (newCrew) => {
      queryClient.setQueryData<PaginatedResponse<Crew>>(
        crewKeys.lists(),
        (old) => {
          if (!old) return old;
          return { ...old, items: [newCrew, ...old.items], total: old.total + 1 };
        }
      );
      queryClient.invalidateQueries({ queryKey: crewKeys.lists() });
    },
  });
}

// ─── Update ───────────────────────────────────────────────────────────────────

export function useUpdateCrew(): UseMutationResult<
  Crew,
  unknown,
  { id: string; data: Partial<Omit<Crew, "id">> }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }) => crewsApi.update(id, data),
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({ queryKey: crewKeys.detail(id) });
      const previous = queryClient.getQueryData<Crew>(crewKeys.detail(id));
      if (previous) {
        queryClient.setQueryData<Crew>(crewKeys.detail(id), {
          ...previous,
          ...data,
        });
      }
      return { previous };
    },
    onError: (_err, { id }, context) => {
      if (context?.previous) {
        queryClient.setQueryData(crewKeys.detail(id), context.previous);
      }
    },
    onSettled: (_data, _err, { id }) => {
      queryClient.invalidateQueries({ queryKey: crewKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: crewKeys.lists() });
    },
  });
}

// ─── Delete ───────────────────────────────────────────────────────────────────

export function useDeleteCrew(): UseMutationResult<void, unknown, string> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id) => crewsApi.delete(id),
    onSuccess: (_data, id) => {
      queryClient.removeQueries({ queryKey: crewKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: crewKeys.lists() });
    },
  });
}

// ─── Add member ───────────────────────────────────────────────────────────────

export function useAddCrewMember(): UseMutationResult<
  CrewMember,
  unknown,
  { crewId: string; user_id: string; role?: "lead" | "member" }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ crewId, user_id, role }) =>
      crewsApi.addMember(crewId, { user_id, role }),
    onSuccess: (_data, { crewId }) => {
      queryClient.invalidateQueries({ queryKey: crewKeys.detail(crewId) });
      queryClient.invalidateQueries({ queryKey: crewKeys.lists() });
    },
  });
}

// ─── Remove member ────────────────────────────────────────────────────────────

export function useRemoveCrewMember(): UseMutationResult<
  CrewMember,
  unknown,
  { crewId: string; userId: string }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ crewId, userId }) => crewsApi.removeMember(crewId, userId),
    onSuccess: (_data, { crewId }) => {
      queryClient.invalidateQueries({ queryKey: crewKeys.detail(crewId) });
      queryClient.invalidateQueries({ queryKey: crewKeys.lists() });
    },
  });
}
