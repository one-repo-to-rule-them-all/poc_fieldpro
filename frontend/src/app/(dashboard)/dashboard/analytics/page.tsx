"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { analyticsApi } from "@/lib/api";
import { KPICard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import { formatCurrency, formatDate } from "@/lib/utils";

type DateRangeOption = "7d" | "30d" | "90d";

function getDateRange(option: DateRangeOption): { from: string; to: string } {
  const to = new Date().toISOString().split("T")[0]!;
  const days = option === "7d" ? 7 : option === "30d" ? 30 : 90;
  const from = new Date(Date.now() - days * 86_400_000).toISOString().split("T")[0]!;
  return { from, to };
}

const DATE_RANGE_OPTIONS: { value: DateRangeOption; label: string }[] = [
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
];

export default function AnalyticsPage() {
  const [range, setRange] = useState<DateRangeOption>("30d");
  const dateRange = getDateRange(range);

  const { data: kpis, isLoading: kpisLoading } = useQuery({
    queryKey: ["analytics", "kpis", range],
    queryFn: () => analyticsApi.getKPIs(dateRange),
    staleTime: 60_000,
  });

  const { data: trends, isLoading: trendsLoading } = useQuery({
    queryKey: ["analytics", "trends", range],
    queryFn: () => analyticsApi.getWorkOrderTrends(dateRange),
    staleTime: 60_000,
  });

  const { data: revenueByClient, isLoading: revenueLoading } = useQuery({
    queryKey: ["analytics", "revenue-by-client", range],
    queryFn: () => analyticsApi.getRevenueByClient(dateRange),
    staleTime: 60_000,
    select: (data) => data.slice(0, 5),
  });

  const { data: crewProductivity, isLoading: crewLoading } = useQuery({
    queryKey: ["analytics", "crew-productivity", range],
    queryFn: () => analyticsApi.getCrewProductivity(dateRange),
    staleTime: 60_000,
  });

  return (
    <div className="flex flex-col">
      <PageHeader
        title="Analytics"
        subtitle="Performance metrics and trends"
        breadcrumbs={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Analytics" },
        ]}
        actions={
          <select
            value={range}
            onChange={(e) => setRange(e.target.value as DateRangeOption)}
            className="input-field w-40 py-1.5 text-sm"
          >
            {DATE_RANGE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        }
      />

      <div className="p-6 space-y-6">
        {/* KPI Cards */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KPICard
            title="Total Revenue"
            value={kpis ? formatCurrency(kpis.total_revenue_mtd) : "—"}
            isLoading={kpisLoading}
            color="success"
          />
          <KPICard
            title="Active Work Orders"
            value={kpis?.active_work_orders ?? 0}
            isLoading={kpisLoading}
            color="default"
          />
          <KPICard
            title="Completion Rate"
            value={kpis ? `${Math.round(kpis.completion_rate * 100)}%` : "—"}
            isLoading={kpisLoading}
            color={
              kpis
                ? kpis.completion_rate >= 0.9
                  ? "success"
                  : kpis.completion_rate >= 0.7
                  ? "warning"
                  : "danger"
                : "default"
            }
          />
          <KPICard
            title="SLA Compliance"
            value={kpis ? `${Math.round(kpis.sla_compliance * 100)}%` : "—"}
            isLoading={kpisLoading}
            color={
              kpis
                ? kpis.sla_compliance >= 0.95
                  ? "success"
                  : kpis.sla_compliance >= 0.8
                  ? "warning"
                  : "danger"
                : "default"
            }
          />
        </div>

        {/* Charts grid */}
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          {/* Work Order Trends */}
          <div className="card p-5">
            <h3 className="mb-4 font-semibold text-neutral-900">
              Work Order Trends
            </h3>
            {trendsLoading ? (
              <div className="h-64 animate-pulse rounded-lg bg-neutral-100" />
            ) : trends && trends.length > 0 ? (
              <ResponsiveContainer width="100%" height={256}>
                <LineChart
                  data={trends}
                  margin={{ top: 4, right: 16, bottom: 0, left: -16 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11, fill: "#94a3b8" }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v: string) => formatDate(v, "MMM d")}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "#94a3b8" }}
                    axisLine={false}
                    tickLine={false}
                    allowDecimals={false}
                  />
                  <Tooltip
                    contentStyle={{ fontSize: "12px", border: "1px solid #e2e8f0", borderRadius: "8px" }}
                    labelFormatter={(v: string) => formatDate(v, "MMM d, yyyy")}
                  />
                  <Legend wrapperStyle={{ fontSize: "12px" }} />
                  <Line
                    type="monotone"
                    dataKey="created"
                    name="Created"
                    stroke="#2563eb"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="completed"
                    name="Completed"
                    stroke="#16a34a"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-64 items-center justify-center text-sm text-neutral-400">
                No trend data available for this period.
              </div>
            )}
          </div>

          {/* Revenue by Client */}
          <div className="card p-5">
            <h3 className="mb-4 font-semibold text-neutral-900">
              Revenue by Client (Top 5)
            </h3>
            {revenueLoading ? (
              <div className="h-64 animate-pulse rounded-lg bg-neutral-100" />
            ) : revenueByClient && revenueByClient.length > 0 ? (
              <ResponsiveContainer width="100%" height={256}>
                <BarChart
                  data={revenueByClient}
                  layout="vertical"
                  margin={{ top: 4, right: 24, bottom: 0, left: 8 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                  <XAxis
                    type="number"
                    tick={{ fontSize: 11, fill: "#94a3b8" }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`}
                  />
                  <YAxis
                    type="category"
                    dataKey="client_name"
                    tick={{ fontSize: 11, fill: "#64748b" }}
                    axisLine={false}
                    tickLine={false}
                    width={100}
                  />
                  <Tooltip
                    contentStyle={{ fontSize: "12px", border: "1px solid #e2e8f0", borderRadius: "8px" }}
                    formatter={(v: number) => [formatCurrency(v), "Revenue"]}
                  />
                  <Bar dataKey="revenue" fill="#2563eb" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-64 items-center justify-center text-sm text-neutral-400">
                No revenue data available for this period.
              </div>
            )}
          </div>

          {/* Crew Productivity */}
          <div className="card p-5 xl:col-span-2">
            <h3 className="mb-4 font-semibold text-neutral-900">
              Crew Productivity
            </h3>
            {crewLoading ? (
              <div className="h-64 animate-pulse rounded-lg bg-neutral-100" />
            ) : crewProductivity && crewProductivity.length > 0 ? (
              <ResponsiveContainer width="100%" height={256}>
                <BarChart
                  data={crewProductivity}
                  margin={{ top: 4, right: 24, bottom: 0, left: -16 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                  <XAxis
                    dataKey="crew_name"
                    tick={{ fontSize: 11, fill: "#64748b" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    yAxisId="left"
                    tick={{ fontSize: 11, fill: "#94a3b8" }}
                    axisLine={false}
                    tickLine={false}
                    allowDecimals={false}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    tick={{ fontSize: 11, fill: "#94a3b8" }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
                    domain={[0, 1]}
                  />
                  <Tooltip
                    contentStyle={{ fontSize: "12px", border: "1px solid #e2e8f0", borderRadius: "8px" }}
                    formatter={(v: number, name: string) => {
                      if (name === "SLA Compliance") return [`${Math.round(v * 100)}%`, name];
                      if (name === "Avg Hours") return [`${v.toFixed(1)}h`, name];
                      return [v, name];
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: "12px" }} />
                  <Bar
                    yAxisId="left"
                    dataKey="work_orders_completed"
                    name="WOs Completed"
                    fill="#2563eb"
                    radius={[4, 4, 0, 0]}
                  />
                  <Bar
                    yAxisId="left"
                    dataKey="avg_hours"
                    name="Avg Hours"
                    fill="#7c3aed"
                    radius={[4, 4, 0, 0]}
                  />
                  <Bar
                    yAxisId="right"
                    dataKey="sla_compliance"
                    name="SLA Compliance"
                    fill="#16a34a"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-64 items-center justify-center text-sm text-neutral-400">
                No crew data available for this period.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
