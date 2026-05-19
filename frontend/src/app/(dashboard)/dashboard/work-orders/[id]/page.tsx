"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  Clock,
  MapPin,
  User,
  Users,
  Calendar,
  AlertTriangle,
  Upload,
  RefreshCw,
  Loader2,
  Pencil,
  Check,
  X,
} from "lucide-react";
import {
  useWorkOrder,
  useCompleteWorkOrder,
  useUpdateWorkOrder,
} from "@/hooks/use-work-orders";
import { useCrews } from "@/hooks/use-crews";
import { Modal } from "@/components/ui/modal";
import { WorkOrderForm } from "@/components/work-orders/work-order-form";
import { TaskList } from "@/components/work-orders/task-list";
import { StatusBadge, PriorityBadge } from "@/components/ui/status-badge";
import { PageHeader } from "@/components/ui/page-header";
import { CheckInButton } from "@/components/work-orders/check-in-button";
import {
  formatDate,
  formatDateTime,
  formatRelativeTime,
  cn,
} from "@/lib/utils";
import type { CheckIn } from "@/types";

function CrewAssignmentCard({
  workOrderId,
  crewId,
  crewName,
}: {
  workOrderId: string;
  crewId?: string;
  crewName?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [pending, setPending] = useState<string>(crewId ?? "");
  const { data: crewsData } = useCrews({ page_size: 100 });
  const updateWorkOrder = useUpdateWorkOrder();

  const onSave = () => {
    const next = pending === "" ? null : pending;
    updateWorkOrder.mutate(
      { id: workOrderId, data: { crew_id: next } as any },
      {
        onSuccess: () => setEditing(false),
      }
    );
  };

  const onCancel = () => {
    setPending(crewId ?? "");
    setEditing(false);
  };

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-neutral-500">
          <Users className="h-3.5 w-3.5" />
          Crew
        </div>
        {!editing && (
          <button
            onClick={() => setEditing(true)}
            className="rounded p-0.5 text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700"
            aria-label="Change crew"
            title="Change crew"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {!editing ? (
        crewId ? (
          <Link
            href={`/dashboard/crews/${crewId}`}
            className="mt-1 block text-sm font-medium text-primary-700 hover:underline"
          >
            {crewName ?? crewId}
          </Link>
        ) : (
          <p className="mt-1 text-sm font-medium text-neutral-400">Unassigned</p>
        )
      ) : (
        <div className="mt-1 flex items-center gap-1.5">
          <select
            value={pending}
            onChange={(e) => setPending(e.target.value)}
            disabled={updateWorkOrder.isPending}
            className="input-field flex-1 py-1 text-sm"
            autoFocus
          >
            <option value="">Unassigned</option>
            {crewsData?.items.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <button
            onClick={onSave}
            disabled={updateWorkOrder.isPending}
            className="rounded p-1 text-success-600 hover:bg-success-50 disabled:opacity-50"
            aria-label="Save"
            title="Save"
          >
            {updateWorkOrder.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Check className="h-4 w-4" />
            )}
          </button>
          <button
            onClick={onCancel}
            disabled={updateWorkOrder.isPending}
            className="rounded p-1 text-neutral-500 hover:bg-neutral-100 disabled:opacity-50"
            aria-label="Cancel"
            title="Cancel"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}
      {updateWorkOrder.isError && (
        <p className="mt-1 text-xs text-danger-600">Failed — try again.</p>
      )}
    </div>
  );
}

export default function WorkOrderDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const { data: workOrder, isLoading } = useWorkOrder(id);
  const completeWorkOrder = useCompleteWorkOrder(id);

  const [activeTab, setActiveTab] = useState<"tasks" | "checkins" | "attachments">("tasks");
  const [showEditModal, setShowEditModal] = useState(false);

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary-500" />
      </div>
    );
  }

  if (!workOrder) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-2 text-neutral-400">
        <AlertTriangle className="h-10 w-10" />
        <p>Work order not found</p>
        <button
          onClick={() => router.back()}
          className="btn-secondary mt-2 text-sm"
        >
          Go back
        </button>
      </div>
    );
  }

  const completedTasks = (workOrder.tasks ?? []).filter(
    (t) => t.status === "completed"
  ).length;
  const totalTasks = (workOrder.tasks ?? []).length;


  return (
    <div>
      <PageHeader
        title={workOrder.title}
        subtitle={`WO-${workOrder.id.slice(0, 8).toUpperCase()}`}
        breadcrumbs={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Work Orders", href: "/dashboard/work-orders" },
          { label: workOrder.title },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <PriorityBadge priority={workOrder.priority} testid="wo-priority-badge" />
            <StatusBadge status={workOrder.status} testid="wo-status-badge" />
            <button
              onClick={() => setShowEditModal(true)}
              data-testid="wo-edit-button"
              className="btn-secondary text-sm"
            >
              Edit
            </button>
            {workOrder.status !== "completed" && workOrder.status !== "cancelled" && (
              <button
                onClick={() => completeWorkOrder.mutate({})}
                disabled={completeWorkOrder.isPending}
                data-testid="wo-complete-button"
                className="btn-primary text-sm disabled:opacity-50"
              >
                {completeWorkOrder.isPending ? "Completing…" : "Mark Complete"}
              </button>
            )}
          </div>
        }
      />

      <div className="p-6">
        {/* Info grid */}
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          <div className="card p-4">
            <div className="flex items-center gap-2 text-xs text-neutral-500">
              <User className="h-3.5 w-3.5" />
              Client
            </div>
            <p className="mt-1 text-sm font-medium text-neutral-900">
              {workOrder.client_name ?? workOrder.client_id}
            </p>
          </div>

          <div className="card p-4">
            <div className="flex items-center gap-2 text-xs text-neutral-500">
              <MapPin className="h-3.5 w-3.5" />
              Location
            </div>
            <p className="mt-1 text-sm font-medium text-neutral-900">
              {workOrder.location_name ?? workOrder.location_id}
            </p>
          </div>

          <CrewAssignmentCard
            workOrderId={workOrder.id}
            crewId={workOrder.crew_id}
            crewName={workOrder.crew_name}
          />

          <div className="card p-4">
            <div className="flex items-center gap-2 text-xs text-neutral-500">
              <Calendar className="h-3.5 w-3.5" />
              Scheduled
            </div>
            <p className="mt-1 text-sm font-medium text-neutral-900">
              {formatDate(workOrder.scheduled_date)}
            </p>
            {workOrder.scheduled_start_time && (
              <p className="text-xs text-neutral-500">
                {workOrder.scheduled_start_time}–
                {workOrder.scheduled_end_time ?? "?"}
              </p>
            )}
          </div>

          <div className="card p-4">
            <div className="flex items-center gap-2 text-xs text-neutral-500">
              <Clock className="h-3.5 w-3.5" />
              Hours
            </div>
            <p className="mt-1 text-sm font-medium text-neutral-900">
              {workOrder.actual_hours ?? 0}h actual /{" "}
              {workOrder.estimated_hours ?? "—"}h est.
            </p>
          </div>

          {workOrder.sla_deadline && (
            <div className="card p-4">
              <div className="flex items-center gap-2 text-xs text-neutral-500">
                <AlertTriangle className="h-3.5 w-3.5" />
                SLA Deadline
              </div>
              <p
                className={cn(
                  "mt-1 text-sm font-medium",
                  workOrder.sla_met === false
                    ? "text-danger-600"
                    : "text-neutral-900"
                )}
              >
                {formatDateTime(workOrder.sla_deadline)}
              </p>
              {workOrder.sla_met !== undefined && (
                <span
                  className={cn(
                    "text-xs font-medium",
                    workOrder.sla_met
                      ? "text-success-600"
                      : "text-danger-600"
                  )}
                >
                  {workOrder.sla_met ? "Met" : "Missed"}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Recurrence info */}
        {(workOrder.recurrence_rule || workOrder.parent_work_order_id) && (
          <div className="mb-6 flex items-start gap-3 rounded-lg border border-primary-100 bg-primary-50 px-4 py-3">
            <RefreshCw className="mt-0.5 h-4 w-4 shrink-0 text-primary-500" />
            <div className="min-w-0 text-sm">
              {workOrder.recurrence_rule && (
                <p className="font-medium text-primary-800">
                  Recurring — {workOrder.recurrence_rule}
                </p>
              )}
              {workOrder.parent_work_order_id && (
                <p className="text-primary-600">
                  Part of a recurring series.{" "}
                  <a
                    href={`/dashboard/work-orders/${workOrder.parent_work_order_id}`}
                    className="underline hover:text-primary-800"
                  >
                    View parent
                  </a>
                </p>
              )}
            </div>
          </div>
        )}

        {/* Check-in button (mobile-optimized for field workers) */}
        {(workOrder.status === "scheduled" ||
          workOrder.status === "in_progress") && (
          <div className="mb-6">
            <CheckInButton
              workOrderId={workOrder.id}
              locationId={workOrder.location_id}
              currentCheckIns={workOrder.check_ins ?? []}
            />
          </div>
        )}

        {/* Description */}
        {workOrder.description && (
          <div className="card mb-6 p-5">
            <h3 className="mb-2 text-sm font-semibold text-neutral-700">
              Description
            </h3>
            <p className="text-sm leading-relaxed text-neutral-600">
              {workOrder.description}
            </p>
          </div>
        )}

        {/* Tabs */}
        <div className="mb-4 flex border-b border-neutral-200">
          {(
            [
              {
                key: "tasks",
                label: `Tasks (${completedTasks}/${totalTasks})`,
              },
              {
                key: "checkins",
                label: `Check-Ins (${(workOrder.check_ins ?? []).length})`,
              },
              { key: "attachments", label: "Attachments" },
            ] as const
          ).map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                "px-4 py-2.5 text-sm font-medium transition-colors",
                activeTab === tab.key
                  ? "border-b-2 border-primary-600 text-primary-700"
                  : "text-neutral-500 hover:text-neutral-700"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === "tasks" && (
          <TaskList
            workOrderId={workOrder.id}
            tasks={workOrder.tasks ?? []}
            allowAdd
          />
        )}

        {activeTab === "checkins" && (
          <div className="card overflow-hidden">
            {(workOrder.check_ins ?? []).length === 0 ? (
              <p className="px-5 py-8 text-center text-sm text-neutral-400">
                No check-ins recorded yet
              </p>
            ) : (
              <ul className="divide-y divide-neutral-100">
                {(workOrder.check_ins ?? []).map((checkIn: CheckIn) => (
                  <li key={checkIn.id} className="flex items-start gap-4 px-5 py-4">
                    <div
                      className={cn(
                        "mt-1 h-3 w-3 shrink-0 rounded-full",
                        checkIn.is_valid
                          ? "bg-success-400"
                          : "bg-danger-400"
                      )}
                    />
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-neutral-900">
                          User {checkIn.user_id.slice(0, 8)}
                        </p>
                        {!checkIn.is_valid && (
                          <span className="rounded-full bg-danger-50 px-2 py-0.5 text-xs text-danger-600">
                            Outside geofence
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-neutral-500">
                        Checked in: {formatDateTime(checkIn.check_in_time)}
                      </p>
                      {checkIn.check_out_time && (
                        <p className="text-xs text-neutral-500">
                          Checked out: {formatDateTime(checkIn.check_out_time)}
                        </p>
                      )}
                      {checkIn.distance_from_location_meters !== undefined && (
                        <p className="mt-0.5 text-xs text-neutral-400">
                          {checkIn.distance_from_location_meters.toFixed(0)}m from site
                        </p>
                      )}
                    </div>
                    <span className="shrink-0 text-xs text-neutral-400">
                      {formatRelativeTime(checkIn.check_in_time)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {activeTab === "attachments" && (
          <div className="card p-5">
            <div className="mb-4 flex items-center justify-between">
              <p className="text-sm text-neutral-500">Photos and files</p>
              <button className="btn-secondary gap-2 text-sm">
                <Upload className="h-4 w-4" />
                Upload
              </button>
            </div>
            <p className="py-8 text-center text-sm text-neutral-400">
              No attachments yet
            </p>
          </div>
        )}
      </div>

      <Modal
        open={showEditModal}
        onClose={() => setShowEditModal(false)}
        title="Edit Work Order"
        size="xl"
      >
        <WorkOrderForm
          workOrder={workOrder}
          onSuccess={() => setShowEditModal(false)}
          onCancel={() => setShowEditModal(false)}
        />
      </Modal>
    </div>
  );
}
