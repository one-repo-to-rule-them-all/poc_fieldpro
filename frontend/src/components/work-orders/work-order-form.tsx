"use client";

import { useState, useEffect } from "react";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Plus,
  Trash2,
  GripVertical,
  Loader2,
  X,
} from "lucide-react";
import { useCreateWorkOrder, useUpdateWorkOrder } from "@/hooks/use-work-orders";
import { useClients } from "@/hooks/use-clients";
import { locationsApi, crewsApi } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import type { WorkOrder, Priority, WorkType } from "@/types";

// ─── Schema ───────────────────────────────────────────────────────────────────

const taskSchema = z.object({
  title: z.string().min(1, "Task title required"),
  is_required: z.boolean().default(false),
  sort_order: z.number().default(0),
});

const workOrderSchema = z.object({
  title: z.string().min(2, "Title must be at least 2 characters").max(200),
  description: z.string().optional(),
  client_id: z.string().min(1, "Please select a client"),
  location_id: z.string().min(1, "Please select a location"),
  crew_id: z.string().optional(),
  priority: z.enum(["low", "normal", "high", "urgent"]),
  scheduled_date: z.string().min(1, "Scheduled date required"),
  scheduled_start_time: z.string().optional(),
  scheduled_end_time: z.string().optional(),
  estimated_hours: z.coerce.number().min(0).optional(),
  sla_deadline_date: z.string().optional(),
  sla_deadline_time: z.string().optional(),
  work_type: z.enum(["one_time", "recurring"]).default("one_time"),
  recurrence_preset: z.string().optional(),
  recurrence_rule: z.string().optional(),
  tasks: z.array(taskSchema).default([]),
});

// ─── Recurrence presets ───────────────────────────────────────────────────────

const RECURRENCE_PRESETS = [
  { value: "FREQ=DAILY", label: "Daily" },
  { value: "FREQ=WEEKLY", label: "Weekly" },
  { value: "FREQ=WEEKLY;INTERVAL=2", label: "Every 2 weeks" },
  { value: "FREQ=MONTHLY", label: "Monthly" },
  { value: "custom", label: "Custom RRULE…" },
];

type WorkOrderFormValues = z.infer<typeof workOrderSchema>;

// ─── Props ────────────────────────────────────────────────────────────────────

interface WorkOrderFormProps {
  workOrder?: WorkOrder;
  onSuccess?: (wo: WorkOrder) => void;
  onCancel?: () => void;
}

// ─── Default values helper ────────────────────────────────────────────────────

function buildDefaults(wo?: WorkOrder): Partial<WorkOrderFormValues> {
  if (!wo) {
    return {
      priority: "normal",
      scheduled_date: new Date().toISOString().slice(0, 10),
      work_type: "one_time",
      tasks: [],
    };
  }
  const existingPreset = wo.recurrence_rule
    ? (RECURRENCE_PRESETS.find((p) => p.value === wo.recurrence_rule)?.value ?? "custom")
    : "";
  return {
    title: wo.title,
    description: wo.description ?? "",
    client_id: wo.client_id,
    location_id: wo.location_id,
    crew_id: wo.crew_id ?? "",
    priority: wo.priority,
    // Backend serialises date columns as datetime strings ("YYYY-MM-DDTHH:MM:SS").
    // <input type="date"> needs exactly "YYYY-MM-DD", so always slice to 10 chars.
    scheduled_date: wo.scheduled_date?.slice(0, 10) ?? "",
    scheduled_start_time: wo.scheduled_start_time?.slice(11, 16) ?? "",
    scheduled_end_time: wo.scheduled_end_time?.slice(11, 16) ?? "",
    estimated_hours: wo.estimated_hours ?? undefined,
    sla_deadline_date: wo.sla_deadline?.slice(0, 10) ?? "",
    sla_deadline_time: wo.sla_deadline?.slice(11, 16) ?? "",
    work_type: (wo.work_type as WorkType) ?? "one_time",
    recurrence_preset: existingPreset,
    recurrence_rule: wo.recurrence_rule ?? "",
    tasks: wo.tasks?.map((t) => ({
      title: t.title,
      is_required: t.is_required,
      sort_order: t.sort_order,
    })) ?? [],
  };
}

// ─── Component ────────────────────────────────────────────────────────────────

export function WorkOrderForm({
  workOrder,
  onSuccess,
  onCancel,
}: WorkOrderFormProps) {
  const isEditing = Boolean(workOrder);
  const createMutation = useCreateWorkOrder();
  const updateMutation = useUpdateWorkOrder();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    control,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<WorkOrderFormValues>({
    resolver: zodResolver(workOrderSchema),
    defaultValues: buildDefaults(workOrder),
  });

  // Re-sync whenever data changes: handles the race where the modal opens while
  // the detail fetch is still resolving (placeholder data lacks some fields).
  useEffect(() => {
    if (workOrder) reset(buildDefaults(workOrder));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workOrder?.id, workOrder?.updated_at]);

  const { fields, append, remove, move } = useFieldArray({
    control,
    name: "tasks",
  });

  const selectedClientId = watch("client_id");

  // Clients
  const { data: clientsData } = useClients({ page_size: 100 });

  // Locations filtered by client
  const { data: locationsData } = useQuery({
    queryKey: ["locations", { client_id: selectedClientId }],
    queryFn: () =>
      locationsApi.list({ client_id: selectedClientId, is_active: true }),
    enabled: Boolean(selectedClientId),
  });

  // Crews
  const { data: crewsData } = useQuery({
    queryKey: ["crews", "list"],
    queryFn: () => crewsApi.list({ page_size: 100 }),
  });

  // React Hook Form registers selects as uncontrolled (via ref, no value prop).
  // When options load async after mount, the browser can't retroactively match
  // the stored value to a new option. Re-applying via setValue after each option
  // list arrives fixes the visual blank select.
  useEffect(() => {
    if (isEditing && workOrder?.client_id) {
      setValue("client_id", workOrder.client_id, { shouldValidate: false });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientsData]);

  useEffect(() => {
    if (isEditing && workOrder?.location_id) {
      setValue("location_id", workOrder.location_id, { shouldValidate: false });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locationsData]);

  useEffect(() => {
    if (isEditing && workOrder?.crew_id) {
      setValue("crew_id", workOrder.crew_id, { shouldValidate: false });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [crewsData]);

  const workType = watch("work_type");
  const recurrencePreset = watch("recurrence_preset");

  const onSubmit = async (values: WorkOrderFormValues) => {
    setServerError(null);
    try {
      const rrule =
        values.work_type === "recurring"
          ? values.recurrence_preset === "custom"
            ? values.recurrence_rule || undefined
            : values.recurrence_preset || undefined
          : undefined;

      const toDatetime = (date: string, time?: string) =>
        date && time ? `${date}T${time}:00` : undefined;

      const slaDeadline = values.sla_deadline_date
        ? toDatetime(values.sla_deadline_date, values.sla_deadline_time || "00:00")
        : undefined;

      const payload = {
        ...values,
        crew_id: values.crew_id || undefined,
        description: values.description || undefined,
        scheduled_start_time: toDatetime(values.scheduled_date, values.scheduled_start_time || undefined),
        scheduled_end_time: toDatetime(values.scheduled_date, values.scheduled_end_time || undefined),
        sla_deadline: slaDeadline,
        sla_deadline_date: undefined,
        sla_deadline_time: undefined,
        recurrence_rule: rrule,
        recurrence_preset: undefined,
        ...(isEditing ? {} : { status: "draft" as WorkOrder["status"] }),
      };

      if (isEditing && workOrder) {
        // Strip fields the PATCH endpoint doesn't accept (client_id, location_id,
        // work_type, tasks are immutable after creation or managed via sub-endpoints)
        const { client_id, location_id, work_type, tasks, ...updatePayload } = payload as typeof payload & {
          client_id?: string; location_id?: string; work_type?: string; tasks?: unknown;
        };
        void client_id; void location_id; void work_type; void tasks;
        const updated = await updateMutation.mutateAsync({
          id: workOrder.id,
          data: updatePayload,
        });
        onSuccess?.(updated);
      } else {
        const created = await createMutation.mutateAsync(payload as Omit<WorkOrder, "id" | "tasks" | "check_ins" | "sla_met" | "actual_hours">);
        onSuccess?.(created);
      }
    } catch (err: unknown) {
      setServerError(
        (err as { message?: string })?.message ?? "Failed to save work order."
      );
    }
  };

  const addTask = () => {
    append({ title: "", is_required: false, sort_order: fields.length });
  };

  const PRIORITIES: { value: Priority; label: string }[] = [
    { value: "low", label: "Low" },
    { value: "normal", label: "Normal" },
    { value: "high", label: "High" },
    { value: "urgent", label: "Urgent" },
  ];

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      {serverError && (
        <div className="mb-4 rounded-lg border border-danger-200 bg-danger-50 px-4 py-3 text-sm text-danger-700">
          {serverError}
        </div>
      )}

      {/* Basic info */}
      <div className="mb-6 space-y-4">
        <div>
          <label className="label">Title *</label>
          <input
            type="text"
            data-testid="wo-form-title"
            {...register("title")}
            className={cn("input-field", errors.title && "border-danger-500")}
            placeholder="e.g. HVAC Maintenance - Building A"
          />
          {errors.title && (
            <p className="error-message">{errors.title.message}</p>
          )}
        </div>

        <div>
          <label className="label">Description</label>
          <textarea
            data-testid="wo-form-description"
            {...register("description")}
            rows={3}
            className="input-field resize-none"
            placeholder="Describe the work to be done…"
          />
        </div>
      </div>

      {/* Client + Location */}
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label className="label">Client *</label>
          <select
            data-testid="wo-form-client"
            {...register("client_id")}
            className={cn(
              "input-field",
              errors.client_id && "border-danger-500"
            )}
          >
            <option value="">Select client…</option>
            {clientsData?.items.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          {errors.client_id && (
            <p className="error-message">{errors.client_id.message}</p>
          )}
        </div>

        <div>
          <label className="label">Location *</label>
          <select
            data-testid="wo-form-location"
            {...register("location_id")}
            disabled={!selectedClientId}
            className={cn(
              "input-field",
              errors.location_id && "border-danger-500",
              !selectedClientId && "cursor-not-allowed opacity-50"
            )}
          >
            <option value="">
              {selectedClientId
                ? "Select location…"
                : "Select a client first"}
            </option>
            {locationsData?.items.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </select>
          {errors.location_id && (
            <p className="error-message">{errors.location_id.message}</p>
          )}
        </div>
      </div>

      {/* Crew + Priority */}
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label className="label">Assign Crew</label>
          <select
            data-testid="wo-form-crew"
            {...register("crew_id")}
            className="input-field"
          >
            <option value="">Unassigned</option>
            {crewsData?.items.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="label">Priority *</label>
          <select
            data-testid="wo-form-priority"
            {...register("priority")}
            className={cn(
              "input-field",
              errors.priority && "border-danger-500"
            )}
          >
            {PRIORITIES.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Scheduling */}
      <div className="mb-6 space-y-4">
        {/* Date row */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="label">Scheduled Date *</label>
            <input
              type="date"
              data-testid="wo-form-scheduled-date"
              {...register("scheduled_date")}
              className={cn("input-field", errors.scheduled_date && "border-danger-500")}
            />
            {errors.scheduled_date && (
              <p className="error-message">{errors.scheduled_date.message}</p>
            )}
          </div>

          <div>
            <label className="label">Est. Hours</label>
            <input
              type="number"
              step="0.5"
              min="0"
              {...register("estimated_hours")}
              className="input-field"
              placeholder="Auto-calculated from window, or enter manually"
            />
          </div>
        </div>

        {/* Time window row */}
        <div>
          <label className="label">Time Window</label>
          <div className="flex items-center gap-3">
            <div className="flex flex-1 items-center gap-2 rounded-lg border border-neutral-200 bg-white px-3 py-2">
              <span className="text-xs font-medium text-neutral-400 shrink-0">From</span>
              <input
                type="time"
                {...register("scheduled_start_time")}
                onChange={(e) => {
                  register("scheduled_start_time").onChange(e);
                  const start = e.target.value;
                  const end = watch("scheduled_end_time");
                  if (start && end) {
                    const [sh = 0, sm = 0] = start.split(":").map(Number);
                    const [eh = 0, em = 0] = end.split(":").map(Number);
                    const diff = (eh * 60 + em - (sh * 60 + sm)) / 60;
                    if (diff > 0) setValue("estimated_hours", Math.round(diff * 2) / 2);
                  }
                }}
                className="flex-1 border-0 bg-transparent p-0 text-sm focus:ring-0"
              />
              <span className="text-xs font-medium text-neutral-400 shrink-0">To</span>
              <input
                type="time"
                {...register("scheduled_end_time")}
                onChange={(e) => {
                  register("scheduled_end_time").onChange(e);
                  const end = e.target.value;
                  const start = watch("scheduled_start_time");
                  if (start && end) {
                    const [sh = 0, sm = 0] = start.split(":").map(Number);
                    const [eh = 0, em = 0] = end.split(":").map(Number);
                    const diff = (eh * 60 + em - (sh * 60 + sm)) / 60;
                    if (diff > 0) setValue("estimated_hours", Math.round(diff * 2) / 2);
                  }
                }}
                className="flex-1 border-0 bg-transparent p-0 text-sm focus:ring-0"
              />
            </div>
          </div>
          <p className="mt-1 text-xs text-neutral-400">Est. hours auto-fills from the window above</p>
        </div>
      </div>

      {/* SLA Deadline */}
      <div className="mb-6">
        <label className="label">SLA Deadline</label>
        <div className="flex items-center gap-2">
          <input
            type="date"
            {...register("sla_deadline_date")}
            className="input-field w-auto"
          />
          <input
            type="time"
            {...register("sla_deadline_time")}
            className="input-field w-auto"
          />
          <span className="text-xs text-neutral-400">Leave blank to skip</span>
        </div>
      </div>

      {/* Recurrence */}
      <div className="mb-6 rounded-lg border border-neutral-200 bg-neutral-50 p-4">
        <label className="flex cursor-pointer items-center gap-3">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-neutral-300 text-primary-600"
            checked={workType === "recurring"}
            onChange={(e) =>
              setValue("work_type", e.target.checked ? "recurring" : "one_time")
            }
          />
          <span className="text-sm font-medium text-neutral-800">
            Recurring work order
          </span>
        </label>

        {workType === "recurring" && (
          <div className="mt-4 space-y-3">
            <div>
              <label className="label">Repeat</label>
              <select
                {...register("recurrence_preset")}
                className="input-field max-w-xs"
              >
                <option value="">Select frequency…</option>
                {RECURRENCE_PRESETS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>

            {recurrencePreset === "custom" && (
              <div>
                <label className="label">RRULE string</label>
                <input
                  type="text"
                  {...register("recurrence_rule")}
                  className="input-field font-mono text-sm"
                  placeholder="FREQ=WEEKLY;BYDAY=MO,WE,FR"
                />
                <p className="mt-1 text-xs text-neutral-500">
                  iCal RRULE format — must start with FREQ=
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Task Checklist */}
      <div className="mb-6">
        <div className="mb-2 flex items-center justify-between">
          <label className="label mb-0">Task Checklist</label>
          <button
            type="button"
            onClick={addTask}
            className="flex items-center gap-1 text-xs font-medium text-primary-600 hover:text-primary-700"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Task
          </button>
        </div>

        {fields.length === 0 ? (
          <div
            className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed border-neutral-200 py-6 text-neutral-400 hover:border-primary-300 hover:text-primary-500"
            onClick={addTask}
          >
            <Plus className="h-5 w-5" />
            <span className="text-sm">Add tasks for field workers</span>
          </div>
        ) : (
          <div className="space-y-2">
            {fields.map((field, index) => (
              <div
                key={field.id}
                className="flex items-center gap-2 rounded-lg border border-neutral-200 bg-white p-2"
              >
                <GripVertical className="h-4 w-4 shrink-0 cursor-grab text-neutral-300" />

                <input
                  type="text"
                  {...register(`tasks.${index}.title`)}
                  className="input-field flex-1 border-0 bg-transparent px-0 py-0 text-sm shadow-none focus:ring-0"
                  placeholder="Task description…"
                />

                <label className="flex items-center gap-1.5 text-xs text-neutral-500">
                  <input
                    type="checkbox"
                    {...register(`tasks.${index}.is_required`)}
                    className="h-3.5 w-3.5 rounded border-neutral-300 text-primary-600"
                  />
                  Required
                </label>

                <button
                  type="button"
                  onClick={() => remove(index)}
                  className="shrink-0 rounded p-1 text-neutral-300 hover:text-danger-500"
                  aria-label="Remove task"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center justify-end gap-3 border-t border-neutral-100 pt-4">
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            data-testid="wo-form-cancel"
            className="btn-secondary"
          >
            Cancel
          </button>
        )}
        <button
          type="submit"
          data-testid="wo-form-submit"
          disabled={isSubmitting}
          className="btn-primary"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              {isEditing ? "Saving…" : "Creating…"}
            </>
          ) : isEditing ? (
            "Save Changes"
          ) : (
            "Create Work Order"
          )}
        </button>
      </div>
    </form>
  );
}
