"use client";

import { useState } from "react";
import {
  ChevronUp,
  ChevronDown,
  ChevronsUpDown,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ─── Column Definition ────────────────────────────────────────────────────────

export interface Column<T> {
  key: string;
  header: string;
  accessor: (row: T) => React.ReactNode;
  sortable?: boolean;
  className?: string;
  headerClassName?: string;
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  isLoading?: boolean;
  emptyMessage?: string;
  emptyIcon?: React.ReactNode;
  onRowClick?: (row: T) => void;
  keyExtractor: (row: T) => string;
  // Pagination
  page?: number;
  pageSize?: number;
  totalItems?: number;
  onPageChange?: (page: number) => void;
  // Selection
  selectable?: boolean;
  selectedIds?: Set<string>;
  onSelectionChange?: (ids: Set<string>) => void;
  // Sort
  sortKey?: string;
  sortDirection?: "asc" | "desc";
  onSort?: (key: string, direction: "asc" | "desc") => void;
}

// ─── Skeleton Row ─────────────────────────────────────────────────────────────

function SkeletonRow({ cols }: { cols: number }) {
  return (
    <tr className="animate-pulse border-b border-neutral-100">
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 rounded bg-neutral-200" />
        </td>
      ))}
    </tr>
  );
}

// ─── Component ────────────────────────────────────────────────────────────────

export function DataTable<T>({
  columns,
  data,
  isLoading = false,
  emptyMessage = "No results found.",
  emptyIcon,
  onRowClick,
  keyExtractor,
  page = 1,
  pageSize = 20,
  totalItems = 0,
  onPageChange,
  selectable = false,
  selectedIds = new Set(),
  onSelectionChange,
  sortKey,
  sortDirection,
  onSort,
}: DataTableProps<T>) {
  const [internalSort, setInternalSort] = useState<{
    key: string;
    direction: "asc" | "desc";
  } | null>(null);

  const activeSortKey = sortKey ?? internalSort?.key;
  const activeSortDir = sortDirection ?? internalSort?.direction;

  const handleSort = (key: string) => {
    const newDir: "asc" | "desc" =
      activeSortKey === key && activeSortDir === "asc" ? "desc" : "asc";
    if (onSort) {
      onSort(key, newDir);
    } else {
      setInternalSort({ key, direction: newDir });
    }
  };

  const toggleSelect = (id: string) => {
    if (!onSelectionChange) return;
    const next = new Set(selectedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    onSelectionChange(next);
  };

  const toggleSelectAll = () => {
    if (!onSelectionChange) return;
    if (selectedIds.size === data.length) {
      onSelectionChange(new Set());
    } else {
      onSelectionChange(new Set(data.map(keyExtractor)));
    }
  };

  const totalPages = Math.ceil(totalItems / pageSize);

  // Client-side sort (only when no server sort)
  const displayData =
    !onSort && internalSort
      ? [...data].sort((a, b) => {
          const col = columns.find((c) => c.key === internalSort.key);
          if (!col) return 0;
          const aVal = col.accessor(a);
          const bVal = col.accessor(b);
          const aStr = String(aVal);
          const bStr = String(bVal);
          const cmp = aStr.localeCompare(bStr, undefined, { numeric: true });
          return internalSort.direction === "asc" ? cmp : -cmp;
        })
      : data;

  return (
    <div className="flex flex-col">
      {/* Table wrapper */}
      <div className="overflow-x-auto rounded-xl border border-neutral-200">
        <table className="min-w-full divide-y divide-neutral-200 bg-white text-sm">
          {/* Header */}
          <thead className="bg-neutral-50">
            <tr>
              {selectable && (
                <th className="w-10 px-4 py-3">
                  <input
                    type="checkbox"
                    checked={
                      data.length > 0 && selectedIds.size === data.length
                    }
                    onChange={toggleSelectAll}
                    className="h-4 w-4 rounded border-neutral-300 text-primary-600 focus:ring-primary-500"
                    aria-label="Select all"
                  />
                </th>
              )}
              {columns.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  className={cn(
                    "px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-neutral-500",
                    col.sortable && "cursor-pointer select-none hover:text-neutral-700",
                    col.headerClassName
                  )}
                  onClick={col.sortable ? () => handleSort(col.key) : undefined}
                >
                  <span className="flex items-center gap-1">
                    {col.header}
                    {col.sortable && (
                      <span className="text-neutral-400">
                        {activeSortKey === col.key ? (
                          activeSortDir === "asc" ? (
                            <ChevronUp className="h-3 w-3" />
                          ) : (
                            <ChevronDown className="h-3 w-3" />
                          )
                        ) : (
                          <ChevronsUpDown className="h-3 w-3" />
                        )}
                      </span>
                    )}
                  </span>
                </th>
              ))}
            </tr>
          </thead>

          {/* Body */}
          <tbody className="divide-y divide-neutral-100">
            {isLoading ? (
              Array.from({ length: pageSize > 5 ? 5 : pageSize }).map(
                (_, i) => (
                  <SkeletonRow
                    key={i}
                    cols={columns.length + (selectable ? 1 : 0)}
                  />
                )
              )
            ) : displayData.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length + (selectable ? 1 : 0)}
                  className="px-4 py-12 text-center"
                >
                  <div className="flex flex-col items-center gap-2 text-neutral-400">
                    {emptyIcon && <div className="mb-1">{emptyIcon}</div>}
                    <span className="text-sm">{emptyMessage}</span>
                  </div>
                </td>
              </tr>
            ) : (
              displayData.map((row) => {
                const id = keyExtractor(row);
                const isSelected = selectedIds.has(id);
                return (
                  <tr
                    key={id}
                    data-testid={`data-row-${id}`}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                    className={cn(
                      "transition-colors",
                      onRowClick && "cursor-pointer hover:bg-neutral-50",
                      isSelected && "bg-primary-50"
                    )}
                  >
                    {selectable && (
                      <td className="w-10 px-4 py-3">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelect(id)}
                          onClick={(e) => e.stopPropagation()}
                          className="h-4 w-4 rounded border-neutral-300 text-primary-600 focus:ring-primary-500"
                        />
                      </td>
                    )}
                    {columns.map((col) => (
                      <td
                        key={col.key}
                        className={cn(
                          "px-4 py-3 text-neutral-700",
                          col.className
                        )}
                      >
                        {col.accessor(row)}
                      </td>
                    ))}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && onPageChange && (
        <div className="mt-4 flex items-center justify-between px-1 text-sm text-neutral-600">
          <span>
            Showing {(page - 1) * pageSize + 1}–
            {Math.min(page * pageSize, totalItems)} of {totalItems}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-neutral-200 bg-white text-neutral-600 transition-colors hover:bg-neutral-50 disabled:pointer-events-none disabled:opacity-40"
              aria-label="Previous page"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>

            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              let pageNum: number;
              if (totalPages <= 7) {
                pageNum = i + 1;
              } else if (page <= 4) {
                pageNum = i + 1;
              } else if (page >= totalPages - 3) {
                pageNum = totalPages - 6 + i;
              } else {
                pageNum = page - 3 + i;
              }
              return (
                <button
                  key={pageNum}
                  onClick={() => onPageChange(pageNum)}
                  className={cn(
                    "inline-flex h-8 min-w-[2rem] items-center justify-center rounded-lg border px-2 text-sm transition-colors",
                    pageNum === page
                      ? "border-primary-600 bg-primary-600 text-white"
                      : "border-neutral-200 bg-white text-neutral-600 hover:bg-neutral-50"
                  )}
                >
                  {pageNum}
                </button>
              );
            })}

            <button
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-neutral-200 bg-white text-neutral-600 transition-colors hover:bg-neutral-50 disabled:pointer-events-none disabled:opacity-40"
              aria-label="Next page"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
