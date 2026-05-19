"use client";

import { useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import {
  Plus,
  UserPlus,
  FileText,
  ArrowRight,
  ClipboardList,
  CheckCircle2,
  ShieldCheck,
  Receipt,
  DollarSign,
  Users,
  Timer,
  TrendingUp,
  Activity,
} from "lucide-react";
import { workOrdersApi } from "@/lib/api";
import { useKPIs } from "@/hooks/use-analytics";
import { useCrewProductivity } from "@/hooks/use-analytics";
import { KPICard } from "@/components/ui/kpi-card";
import { StatusBadge, PriorityBadge } from "@/components/ui/status-badge";
import { useModals } from "@/stores/ui-store";
import { useAuth } from "@/hooks/use-auth";
import { formatDate, formatCurrency, truncate } from "@/lib/utils";
import type { WorkOrder } from "@/types";

export default function DashboardPage() {
  const router = useRouter();
  const { open } = useModals();
  const { user } = useAuth();

  // Employees don't have access to dashboard KPIs (analytics 403s). Send them
  // to their canonical landing. Defense-in-depth: also enforced at login.
  useEffect(() => {
    if (user?.role === "employee") {
      router.replace("/dashboard/check-in");
    }
  }, [user?.role, router]);

  const crewRange = useMemo(() => ({
    from: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split("T")[0]!,
    to: new Date().toISOString().split("T")[0]!,
  }), []);

  const { data: kpis, isLoading: kpisLoading } = useKPIs();

  const { data: recentWorkOrders, isLoading: woLoading } = useQuery({
    queryKey: ["work-orders", "recent"],
    queryFn: () => workOrdersApi.list({ page: 1, page_size: 8 }),
    staleTime: 30_000,
  });

  const { data: utilizationData, isLoading: utilLoading } = useCrewProductivity(crewRange);

  return (
    <div className="p-6 lg:p-8 max-w-[1400px] mx-auto">
      {/* Page header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-neutral-900">
            Operations Overview
          </h1>
          <p className="mt-0.5 text-sm text-neutral-500">
            {new Date().toLocaleDateString("en-US", {
              weekday: "long",
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </p>
        </div>
        <button
          onClick={() => open("create-work-order")}
          className="btn-primary hidden sm:flex"
        >
          <Plus className="h-4 w-4" />
          New Work Order
        </button>
      </div>

      {/* KPI Grid — row 1 */}
      <div className="mb-4 grid grid-cols-2 gap-4 xl:grid-cols-4">
        <KPICard
          title="Active Work Orders"
          value={kpis?.active_work_orders ?? 0}
          icon={ClipboardList}
          isLoading={kpisLoading}
          color="default"
          trend={
            kpis
              ? { direction: "up", percent: 5, label: "vs last week" }
              : undefined
          }
        />
        <KPICard
          title="Completed Today"
          value={kpis?.completed_today ?? 0}
          icon={CheckCircle2}
          isLoading={kpisLoading}
          color="success"
        />
        <KPICard
          title="SLA Compliance"
          value={kpis ? `${Math.round(kpis.sla_compliance * 100)}%` : "—"}
          icon={ShieldCheck}
          isLoading={kpisLoading}
          color={
            !kpis
              ? "default"
              : kpis.sla_compliance >= 0.95
              ? "success"
              : kpis.sla_compliance >= 0.8
              ? "warning"
              : "danger"
          }
        />
        <KPICard
          title="Outstanding Invoices"
          value={kpis ? formatCurrency(kpis.outstanding_invoices) : "—"}
          icon={Receipt}
          isLoading={kpisLoading}
          color="warning"
        />
      </div>

      {/* KPI Grid — row 2 */}
      <div className="mb-8 grid grid-cols-2 gap-4 xl:grid-cols-4">
        <KPICard
          title="Revenue MTD"
          value={kpis ? formatCurrency(kpis.total_revenue_mtd) : "—"}
          icon={DollarSign}
          isLoading={kpisLoading}
          color="success"
          trend={
            kpis
              ? { direction: "up", percent: 12, label: "vs last month" }
              : undefined
          }
        />
        <KPICard
          title="Crew Utilization"
          value={kpis ? `${Math.round(kpis.crew_utilization * 100)}%` : "—"}
          icon={Users}
          isLoading={kpisLoading}
          color="default"
        />
        <KPICard
          title="Avg Time On-Site"
          value={kpis ? `${kpis.avg_time_on_site_minutes}` : "—"}
          unit="min"
          icon={Timer}
          isLoading={kpisLoading}
          color="default"
        />
        <KPICard
          title="Completion Rate"
          value={
            kpis ? `${Math.round(kpis.completion_rate * 100)}%` : "—"
          }
          icon={TrendingUp}
          isLoading={kpisLoading}
          color="success"
        />
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Recent Work Orders */}
        <div className="lg:col-span-2">
          <div className="card overflow-hidden">
            <div className="flex items-center justify-between border-b border-neutral-100 px-5 py-4">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-neutral-400" />
                <h3 className="font-semibold text-neutral-900">
                  Recent Work Orders
                </h3>
              </div>
              <button
                onClick={() => router.push("/dashboard/work-orders")}
                className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-primary-600 hover:bg-primary-50 transition-colors"
              >
                View all
                <ArrowRight className="h-3 w-3" />
              </button>
            </div>

            {woLoading ? (
              <div className="divide-y divide-neutral-50">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div
                    key={i}
                    className="flex animate-pulse items-center gap-3 px-5 py-3.5"
                  >
                    <div className="h-3.5 w-20 rounded bg-neutral-100" />
                    <div className="h-3.5 flex-1 rounded bg-neutral-100" />
                    <div className="h-5 w-14 rounded-full bg-neutral-100" />
                    <div className="h-5 w-16 rounded-full bg-neutral-100" />
                  </div>
                ))}
              </div>
            ) : (
              <div className="divide-y divide-neutral-50">
                {recentWorkOrders?.items.map((wo: WorkOrder) => (
                  <div
                    key={wo.id}
                    onClick={() =>
                      router.push(`/dashboard/work-orders/${wo.id}`)
                    }
                    className="flex cursor-pointer items-center gap-4 px-5 py-3.5 transition-colors hover:bg-neutral-50/80 group"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-neutral-900 group-hover:text-primary-700 transition-colors">
                        {truncate(wo.title, 50)}
                      </p>
                      <p className="mt-0.5 text-xs text-neutral-400">
                        {formatDate(wo.scheduled_date)}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <PriorityBadge priority={wo.priority} />
                      <StatusBadge status={wo.status} />
                    </div>
                  </div>
                ))}
                {(!recentWorkOrders?.items ||
                  recentWorkOrders.items.length === 0) && (
                  <div className="px-5 py-12 text-center">
                    <ClipboardList className="mx-auto h-8 w-8 text-neutral-300 mb-2" />
                    <p className="text-sm text-neutral-400">
                      No work orders yet
                    </p>
                    <button
                      onClick={() => open("create-work-order")}
                      className="mt-3 text-xs font-medium text-primary-600 hover:text-primary-700"
                    >
                      Create your first →
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right column */}
        <div className="flex flex-col gap-5">
          {/* Quick Actions */}
          <div className="card p-5">
            <h3 className="mb-3.5 text-sm font-semibold text-neutral-900">
              Quick Actions
            </h3>
            <div className="space-y-2">
              <button
                onClick={() => open("create-work-order")}
                className="btn-primary w-full justify-start text-sm"
              >
                <Plus className="h-4 w-4" />
                Create Work Order
              </button>
              <button
                onClick={() => open("assign-crew")}
                className="btn-secondary w-full justify-start text-sm"
              >
                <UserPlus className="h-4 w-4" />
                Assign Crew
              </button>
              <button
                onClick={() => router.push("/dashboard/invoices")}
                className="btn-secondary w-full justify-start text-sm"
              >
                <FileText className="h-4 w-4" />
                Generate Invoice
              </button>
            </div>
          </div>

          {/* Crew Utilization Chart */}
          <div className="card p-5 flex-1">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-neutral-900">
                Crew Output (7d)
              </h3>
              <span className="text-xs text-neutral-400">Work orders</span>
            </div>
            {utilLoading ? (
              <div className="h-36 animate-pulse rounded-lg bg-neutral-100" />
            ) : utilizationData && utilizationData.length > 0 ? (
              <ResponsiveContainer width="100%" height={160}>
                <BarChart
                  data={utilizationData}
                  margin={{ top: 4, right: 0, bottom: 0, left: -20 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="#f1f5f9"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="crew_name"
                    tick={{ fontSize: 10, fill: "#94a3b8" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: "#94a3b8" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      fontSize: "12px",
                      border: "1px solid #e2e8f0",
                      borderRadius: "8px",
                      boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                    }}
                    formatter={(value: number) => [value, "WOs completed"]}
                  />
                  <Bar
                    dataKey="work_orders_completed"
                    fill="#3b82f6"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-36 flex-col items-center justify-center gap-2">
                <Users className="h-7 w-7 text-neutral-300" />
                <p className="text-xs text-neutral-400">No crew data yet</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
