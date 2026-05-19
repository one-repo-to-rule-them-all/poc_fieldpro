"use client";

import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

interface KPICardProps {
  title: string;
  value: string | number;
  unit?: string;
  icon?: React.ElementType;
  trend?: {
    direction: "up" | "down" | "neutral";
    percent: number;
    label?: string;
  };
  color?: "default" | "success" | "warning" | "danger";
  isLoading?: boolean;
  className?: string;
}

const colorConfig = {
  default: {
    iconBg: "bg-primary-50",
    iconText: "text-primary-600",
    accent: "bg-primary-500",
  },
  success: {
    iconBg: "bg-success-50",
    iconText: "text-success-600",
    accent: "bg-success-500",
  },
  warning: {
    iconBg: "bg-warning-50",
    iconText: "text-warning-600",
    accent: "bg-warning-500",
  },
  danger: {
    iconBg: "bg-danger-50",
    iconText: "text-danger-600",
    accent: "bg-danger-500",
  },
};

function LoadingSkeleton() {
  return (
    <div className="card animate-pulse p-5">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="mb-3 h-3 w-20 rounded bg-neutral-200" />
          <div className="mb-2 h-8 w-24 rounded bg-neutral-200" />
          <div className="h-3 w-16 rounded bg-neutral-200" />
        </div>
        <div className="h-10 w-10 rounded-xl bg-neutral-200" />
      </div>
    </div>
  );
}

export function KPICard({
  title,
  value,
  unit,
  icon: Icon,
  trend,
  color = "default",
  isLoading,
  className,
}: KPICardProps) {
  if (isLoading) return <LoadingSkeleton />;

  const colors = colorConfig[color];

  return (
    <div className={cn("card overflow-hidden", className)}>
      {/* Color accent bar */}
      <div className={cn("h-0.5 w-full", colors.accent)} />
      <div className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wider text-neutral-400">
              {title}
            </p>
            <div className="mt-2 flex items-baseline gap-1.5">
              <span className="text-3xl font-bold tracking-tight text-neutral-900">
                {value}
              </span>
              {unit && (
                <span className="text-sm font-medium text-neutral-500">
                  {unit}
                </span>
              )}
            </div>

            {trend && (
              <div
                className={cn(
                  "mt-2 flex items-center gap-1 text-xs font-medium",
                  trend.direction === "up" && "text-success-600",
                  trend.direction === "down" && "text-danger-600",
                  trend.direction === "neutral" && "text-neutral-400"
                )}
              >
                {trend.direction === "up" && <TrendingUp className="h-3 w-3" />}
                {trend.direction === "down" && (
                  <TrendingDown className="h-3 w-3" />
                )}
                {trend.direction === "neutral" && <Minus className="h-3 w-3" />}
                <span>
                  {trend.percent > 0 ? "+" : ""}
                  {trend.percent}% {trend.label ?? "vs last period"}
                </span>
              </div>
            )}
          </div>

          {Icon && (
            <div
              className={cn(
                "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl",
                colors.iconBg
              )}
            >
              <Icon className={cn("h-5 w-5", colors.iconText)} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
