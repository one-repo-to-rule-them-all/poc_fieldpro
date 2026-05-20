import Link from "next/link";
import type { Route } from "next";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

export interface Breadcrumb {
  label: string;
  href?: Route;
}

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  breadcrumbs?: Breadcrumb[];
  actions?: React.ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  subtitle,
  breadcrumbs,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div
      data-testid="page-header"
      className={cn(
        "flex flex-col gap-1 border-b border-neutral-200 bg-white px-6 py-4 sm:flex-row sm:items-center sm:justify-between",
        className
      )}
    >
      <div className="min-w-0 flex-1">
        {/* Breadcrumbs */}
        {breadcrumbs && breadcrumbs.length > 0 && (
          <nav className="mb-1 flex items-center gap-1 text-xs text-neutral-500">
            {breadcrumbs.map((crumb, i) => (
              <span key={i} className="flex items-center gap-1">
                {i > 0 && <ChevronRight className="h-3 w-3 text-neutral-400" />}
                {crumb.href ? (
                  <Link
                    href={crumb.href}
                    className="hover:text-neutral-700 hover:underline"
                  >
                    {crumb.label}
                  </Link>
                ) : (
                  <span className="text-neutral-600">{crumb.label}</span>
                )}
              </span>
            ))}
          </nav>
        )}

        {/* Title */}
        <h1
          data-testid="page-header-title"
          className="truncate text-xl font-bold text-neutral-900"
        >
          {title}
        </h1>

        {/* Subtitle */}
        {subtitle && (
          <p
            data-testid="page-header-subtitle"
            className="mt-0.5 truncate text-sm text-neutral-500"
          >
            {subtitle}
          </p>
        )}
      </div>

      {/* Actions */}
      {actions && (
        <div className="flex shrink-0 items-center gap-2">{actions}</div>
      )}
    </div>
  );
}
