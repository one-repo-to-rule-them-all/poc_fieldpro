"use client";

import { useState } from "react";
import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryResult,
  UseMutationResult,
} from "@tanstack/react-query";
import { workOrdersApi } from "@/lib/api";
import { STALE_TIME } from "@/lib/query-config";
import type {
  WorkOrder,
  WorkOrderFilters,
  PaginatedResponse,
  CheckInPayload,
  CompleteTaskPayload,
} from "@/types";

// ─── Query Keys ───────────────────────────────────────────────────────────────

export const workOrderKeys = {
  all: ["work-orders"] as const,
  lists: () => [...workOrderKeys.all, "list"] as const,
  list: (filters: WorkOrderFilters) =>
    [...workOrderKeys.lists(), filters] as const,
  details: () => [...workOrderKeys.all, "detail"] as const,
  detail: (id: string) => [...workOrderKeys.details(), id] as const,
};

// ─── Paginated List ───────────────────────────────────────────────────────────

export function useWorkOrders(
  params: WorkOrderFilters = {}
): UseQueryResult<PaginatedResponse<WorkOrder>> {
  return useQuery({
    queryKey: workOrderKeys.list(params),
    queryFn: () => workOrdersApi.list(params),
    staleTime: STALE_TIME.LIST,
    placeholderData: (previousData) => previousData,
  });
}

// ─── Single Work Order ────────────────────────────────────────────────────────

export function useWorkOrder(id: string): UseQueryResult<WorkOrder> {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: workOrderKeys.detail(id),
    queryFn: () => workOrdersApi.get(id),
    enabled: Boolean(id),
    staleTime: STALE_TIME.DETAIL,
    placeholderData: () => {
      // Seed from any cached list so navigation from the list is instant
      const lists = queryClient.getQueriesData<PaginatedResponse<WorkOrder>>({
        queryKey: workOrderKeys.lists(),
      });
      for (const [, page] of lists) {
        const found = page?.items.find((wo) => wo.id === id);
        if (found) return found;
      }
    },
  });
}

// ─── Create ───────────────────────────────────────────────────────────────────

export function useCreateWorkOrder(): UseMutationResult<
  WorkOrder,
  unknown,
  Omit<WorkOrder, "id" | "tasks" | "check_ins" | "sla_met" | "actual_hours">
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data) => workOrdersApi.create(data),
    onSuccess: (newWorkOrder) => {
      // Add to cache optimistically
      queryClient.setQueryData<PaginatedResponse<WorkOrder>>(
        workOrderKeys.lists(),
        (old) => {
          if (!old) return old;
          return {
            ...old,
            items: [newWorkOrder, ...old.items],
            total: old.total + 1,
          };
        }
      );
      // Invalidate all list queries to refetch with correct filters/pagination
      queryClient.invalidateQueries({ queryKey: workOrderKeys.lists() });
    },
  });
}

// ─── Update ───────────────────────────────────────────────────────────────────

export function useUpdateWorkOrder(): UseMutationResult<
  WorkOrder,
  unknown,
  { id: string; data: Partial<Omit<WorkOrder, "id" | "check_ins">> }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }) => workOrdersApi.update(id, data),
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({ queryKey: workOrderKeys.detail(id) });
      const previous = queryClient.getQueryData<WorkOrder>(
        workOrderKeys.detail(id)
      );
      if (previous) {
        queryClient.setQueryData<WorkOrder>(workOrderKeys.detail(id), {
          ...previous,
          ...data,
        });
      }
      return { previous };
    },
    onError: (_err, { id }, context) => {
      if (context?.previous) {
        queryClient.setQueryData(workOrderKeys.detail(id), context.previous);
      }
    },
    onSettled: (_data, _err, { id }) => {
      queryClient.invalidateQueries({ queryKey: workOrderKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: workOrderKeys.lists() });
    },
  });
}

// ─── Check In ─────────────────────────────────────────────────────────────────

export function useCheckIn(workOrderId: string): UseMutationResult<
  WorkOrder,
  unknown,
  CheckInPayload
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload) => workOrdersApi.checkIn(workOrderId, payload),
    onSuccess: (updatedWO) => {
      queryClient.setQueryData(workOrderKeys.detail(workOrderId), updatedWO);
      queryClient.invalidateQueries({ queryKey: workOrderKeys.lists() });
    },
  });
}

// ─── Check Out ────────────────────────────────────────────────────────────────

export function useCheckOut(workOrderId: string): UseMutationResult<
  WorkOrder,
  unknown,
  { latitude: number; longitude: number }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload) => workOrdersApi.checkOut(workOrderId, payload),
    onSuccess: (updatedWO) => {
      queryClient.setQueryData(workOrderKeys.detail(workOrderId), updatedWO);
      queryClient.invalidateQueries({ queryKey: workOrderKeys.lists() });
    },
  });
}

// ─── Add Task ─────────────────────────────────────────────────────────────────

export function useAddTask(workOrderId: string): UseMutationResult<
  WorkOrder,
  unknown,
  { title: string; description?: string; is_required?: boolean }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data) => workOrdersApi.addTask(workOrderId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workOrderKeys.detail(workOrderId) });
    },
  });
}

// ─── Complete Task ────────────────────────────────────────────────────────────

export function useCompleteTask(workOrderId: string): UseMutationResult<
  WorkOrder,
  unknown,
  { taskId: string; data: CompleteTaskPayload }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ taskId, data }) =>
      workOrdersApi.completeTask(workOrderId, taskId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workOrderKeys.detail(workOrderId) });
      queryClient.invalidateQueries({ queryKey: workOrderKeys.lists() });
    },
  });
}

// ─── Complete Work Order ──────────────────────────────────────────────────────

export function useCompleteWorkOrder(workOrderId: string): UseMutationResult<
  WorkOrder,
  unknown,
  { notes?: string }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ notes }) => workOrdersApi.completeWorkOrder(workOrderId, notes),
    onSuccess: (updatedWO) => {
      queryClient.setQueryData(workOrderKeys.detail(workOrderId), updatedWO);
      queryClient.invalidateQueries({ queryKey: workOrderKeys.lists() });
    },
  });
}

// ─── Upload Attachment ────────────────────────────────────────────────────────

export function useUploadAttachment(workOrderId: string): {
  uploadFile: (file: File) => Promise<{ url: string; filename: string }>;
  progress: number;
  isUploading: boolean;
  error: unknown;
} {
  const queryClient = useQueryClient();
  const [progress, setProgress] = useState(0);

  const mutation = useMutation({
    mutationFn: (file: File) =>
      workOrdersApi.uploadAttachment(workOrderId, file, setProgress),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: workOrderKeys.detail(workOrderId),
      });
      setProgress(0);
    },
    onError: () => {
      setProgress(0);
    },
  });

  return {
    uploadFile: mutation.mutateAsync,
    progress,
    isUploading: mutation.isPending,
    error: mutation.error,
  };
}
