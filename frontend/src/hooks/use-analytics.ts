"use client";

import { useQuery, UseQueryResult } from "@tanstack/react-query";
import { analyticsApi } from "@/lib/api";
import { STALE_TIME } from "@/lib/query-config";
import type {
  KPIData,
  WorkOrderTrend,
  RevenueByClient,
  CrewProductivity,
  AnalyticsDateRange,
} from "@/types";

// ─── Query Keys ───────────────────────────────────────────────────────────────

export const analyticsKeys = {
  all: ["analytics"] as const,
  kpis: (params?: AnalyticsDateRange) =>
    [...analyticsKeys.all, "kpis", params ?? "default"] as const,
  workOrderTrends: (params: AnalyticsDateRange) =>
    [...analyticsKeys.all, "work-order-trends", params] as const,
  revenueByClient: (params: AnalyticsDateRange) =>
    [...analyticsKeys.all, "revenue-by-client", params] as const,
  crewProductivity: (params: AnalyticsDateRange) =>
    [...analyticsKeys.all, "crew-productivity", params] as const,
};

// ─── KPIs ─────────────────────────────────────────────────────────────────────

export function useKPIs(
  params?: AnalyticsDateRange
): UseQueryResult<KPIData> {
  return useQuery({
    queryKey: analyticsKeys.kpis(params),
    queryFn: () => analyticsApi.getKPIs(params),
    staleTime: STALE_TIME.ANALYTICS,
    placeholderData: (prev) => prev,
  });
}

// ─── Work Order Trends ────────────────────────────────────────────────────────

export function useWorkOrderTrends(
  params: AnalyticsDateRange
): UseQueryResult<WorkOrderTrend[]> {
  return useQuery({
    queryKey: analyticsKeys.workOrderTrends(params),
    queryFn: () => analyticsApi.getWorkOrderTrends(params),
    staleTime: STALE_TIME.ANALYTICS,
    enabled: Boolean(params.from && params.to),
    placeholderData: (prev) => prev,
  });
}

// ─── Revenue by Client ────────────────────────────────────────────────────────

export function useRevenueByClient(
  params: AnalyticsDateRange
): UseQueryResult<RevenueByClient[]> {
  return useQuery({
    queryKey: analyticsKeys.revenueByClient(params),
    queryFn: () => analyticsApi.getRevenueByClient(params),
    staleTime: STALE_TIME.ANALYTICS,
    enabled: Boolean(params.from && params.to),
    placeholderData: (prev) => prev,
  });
}

// ─── Crew Productivity ────────────────────────────────────────────────────────

export function useCrewProductivity(
  params: AnalyticsDateRange
): UseQueryResult<CrewProductivity[]> {
  return useQuery({
    queryKey: analyticsKeys.crewProductivity(params),
    queryFn: () => analyticsApi.getCrewProductivity(params),
    staleTime: STALE_TIME.ANALYTICS,
    enabled: Boolean(params.from && params.to),
    placeholderData: (prev) => prev,
  });
}
