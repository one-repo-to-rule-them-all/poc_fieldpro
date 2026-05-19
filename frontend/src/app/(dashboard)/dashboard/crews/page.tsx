"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Plus, Users, ChevronRight } from "lucide-react";
import { crewsApi } from "@/lib/api";
import { STALE_TIME } from "@/lib/query-config";
import { PageHeader } from "@/components/ui/page-header";
import { cn } from "@/lib/utils";
import type { Crew } from "@/types";

function CrewCard({ crew, onClick }: { crew: Crew; onClick: () => void }) {
  // Prefer aggregate fields from the list endpoint; fall back to nested
  // members[] only if a caller passes a fully loaded crew.
  const memberCount =
    typeof crew.member_count === "number"
      ? crew.member_count
      : crew.members?.length ?? 0;
  const leadName =
    crew.lead_name ??
    (() => {
      const lead = crew.members?.find((m) => m.role === "lead");
      return lead?.user
        ? `${lead.user.first_name} ${lead.user.last_name}`
        : null;
    })();
  const isActive = crew.is_active;

  return (
    <button
      onClick={onClick}
      className="card group flex flex-col gap-4 p-5 text-left transition-all hover:shadow-md hover:border-primary-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-100">
          <Users className="h-5 w-5 text-primary-600" />
        </div>
        <span
          className={cn(
            "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
            isActive
              ? "bg-success-100 text-success-700"
              : "bg-neutral-100 text-neutral-500"
          )}
        >
          {isActive ? "Active" : "Inactive"}
        </span>
      </div>

      {/* Crew info */}
      <div className="flex-1">
        <h3 className="font-semibold text-neutral-900 group-hover:text-primary-700 transition-colors">
          {crew.name}
        </h3>
        <p className="mt-0.5 text-xs font-mono text-neutral-400">{crew.code}</p>
      </div>

      {/* Meta row */}
      <div className="flex items-center justify-between border-t border-neutral-100 pt-3 text-sm text-neutral-600">
        <div>
          <span className="font-medium text-neutral-900">{memberCount}</span>{" "}
          member{memberCount !== 1 ? "s" : ""}
        </div>
        {leadName ? (
          <div className="flex items-center gap-1.5 text-xs text-neutral-500">
            <div className="flex h-5 w-5 items-center justify-center rounded-full bg-neutral-200 text-xs font-bold text-neutral-600">
              {leadName.charAt(0)}
            </div>
            <span>{leadName}</span>
          </div>
        ) : (
          <span className="text-xs text-neutral-400">No lead assigned</span>
        )}
      </div>

      {/* Arrow indicator */}
      <ChevronRight className="absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-300 opacity-0 transition-opacity group-hover:opacity-100" />
    </button>
  );
}

function CrewCardSkeleton() {
  return (
    <div className="card animate-pulse p-5 space-y-4">
      <div className="flex justify-between">
        <div className="h-10 w-10 rounded-xl bg-neutral-200" />
        <div className="h-5 w-16 rounded-full bg-neutral-200" />
      </div>
      <div className="space-y-1.5">
        <div className="h-4 w-32 rounded bg-neutral-200" />
        <div className="h-3 w-16 rounded bg-neutral-200" />
      </div>
      <div className="flex justify-between border-t border-neutral-100 pt-3">
        <div className="h-4 w-20 rounded bg-neutral-200" />
        <div className="h-4 w-24 rounded bg-neutral-200" />
      </div>
    </div>
  );
}

export default function CrewsPage() {
  const router = useRouter();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["crews", "list"],
    queryFn: () => crewsApi.list({ page_size: 50 }),
    staleTime: STALE_TIME.LIST,
  });

  const crews: Crew[] = data?.items ?? [];

  return (
    <div className="flex flex-col">
      <PageHeader
        title="Crews"
        subtitle={data ? `${data.total} crew${data.total !== 1 ? "s" : ""}` : undefined}
        breadcrumbs={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Crews" },
        ]}
        actions={
          <button
            onClick={() => router.push("/dashboard/crews")}
            className="btn-primary"
          >
            <Plus className="h-4 w-4" />
            Create Crew
          </button>
        }
      />

      <div className="p-6">
        {isError ? (
          <div className="rounded-xl border border-danger-200 bg-danger-50 px-5 py-4 text-sm text-danger-700">
            Failed to load crews. Please try again.
          </div>
        ) : isLoading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <CrewCardSkeleton key={i} />
            ))}
          </div>
        ) : crews.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 py-20 text-neutral-400">
            <Users className="h-12 w-12" />
            <p className="text-sm">No crews yet. Create your first crew to get started.</p>
            <button
              onClick={() => router.push("/dashboard/crews")}
              className="btn-primary mt-2"
            >
              <Plus className="h-4 w-4" />
              Create Crew
            </button>
          </div>
        ) : (
          <div className="relative grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {crews.map((crew) => (
              <CrewCard
                key={crew.id}
                crew={crew}
                onClick={() =>
                  router.push(`/dashboard/crews/${crew.id}` as any)
                }
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
