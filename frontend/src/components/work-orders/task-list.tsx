"use client";

import { useState } from "react";
import { CheckCircle, SkipForward, XCircle, RotateCcw, Plus, X } from "lucide-react";
import { useCompleteTask, useAddTask } from "@/hooks/use-work-orders";
import { cn } from "@/lib/utils";
import type { WorkOrderTask } from "@/types";

interface TaskListProps {
  workOrderId: string;
  tasks: WorkOrderTask[];
  allowAdd?: boolean;
  readOnly?: boolean;
}

export function TaskList({ workOrderId, tasks, allowAdd = false, readOnly = false }: TaskListProps) {
  const completeTask = useCompleteTask(workOrderId);
  const addTask = useAddTask(workOrderId);

  const [skippingTaskId, setSkippingTaskId] = useState<string | null>(null);
  const [skipReason, setSkipReason] = useState("");
  const [showAddTask, setShowAddTask] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState("");

  const sorted = [...tasks].sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0));
  const completedCount = tasks.filter((t) => t.status === "completed").length;

  const toggle = (task: WorkOrderTask) => {
    if (task.status === "blocked") return;
    const newStatus = task.status === "pending" ? "completed" : "pending";
    completeTask.mutate({ taskId: task.id, data: { status: newStatus } });
  };

  const confirmSkip = () => {
    if (!skippingTaskId) return;
    completeTask.mutate(
      { taskId: skippingTaskId, data: { skip_reason: skipReason || undefined } },
      { onSuccess: () => { setSkippingTaskId(null); setSkipReason(""); } }
    );
  };

  const submitAddTask = () => {
    if (!newTaskTitle.trim()) return;
    addTask.mutate(
      { title: newTaskTitle.trim() },
      { onSuccess: () => { setNewTaskTitle(""); setShowAddTask(false); } }
    );
  };

  return (
    <div data-testid="task-list" className="card overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-neutral-100 px-5 py-3">
        <span className="text-sm font-medium text-neutral-700">
          {tasks.length} task{tasks.length !== 1 ? "s" : ""}
          {tasks.length > 0 && (
            <span className="ml-1.5 text-neutral-400">
              ({completedCount}/{tasks.length} done)
            </span>
          )}
        </span>
        {allowAdd && !showAddTask && !readOnly && (
          <button
            onClick={() => setShowAddTask(true)}
            className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-primary-600 hover:bg-primary-50 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            Add task
          </button>
        )}
      </div>

      {/* Inline add form */}
      {showAddTask && (
        <div className="flex items-center gap-2 border-b border-neutral-100 bg-neutral-50 px-5 py-3">
          <input
            type="text"
            value={newTaskTitle}
            onChange={(e) => setNewTaskTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") submitAddTask();
              if (e.key === "Escape") { setNewTaskTitle(""); setShowAddTask(false); }
            }}
            placeholder="Task title…"
            autoFocus
            className="input-field flex-1 py-1.5 text-sm"
          />
          <button
            onClick={submitAddTask}
            disabled={!newTaskTitle.trim() || addTask.isPending}
            className="btn-primary py-1.5 text-xs disabled:opacity-50"
          >
            {addTask.isPending ? "Adding…" : "Add"}
          </button>
          <button
            onClick={() => { setNewTaskTitle(""); setShowAddTask(false); }}
            className="rounded-md p-1.5 text-neutral-400 hover:bg-neutral-200 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Empty state */}
      {sorted.length === 0 && !showAddTask && (
        <p className="px-5 py-8 text-center text-sm text-neutral-400">
          {allowAdd ? 'No tasks yet. Click "Add task" to get started.' : "No tasks for this work order."}
        </p>
      )}

      {/* Task rows */}
      <ul className="divide-y divide-neutral-100">
        {sorted.map((task) => (
          <li key={task.id} data-testid={`task-row-${task.id}`} className="px-5 py-3">
            <div className="flex items-center gap-3">
              {/* Toggle / status button */}
              <button
                onClick={() => {
                  if (readOnly || task.status === "blocked") return;
                  if (task.status === "skipped") {
                    // Undo skip
                    completeTask.mutate({ taskId: task.id, data: { status: "pending" } });
                  } else {
                    toggle(task);
                  }
                }}
                data-testid={`task-toggle-${task.id}`}
                disabled={completeTask.isPending || task.status === "blocked" || readOnly}
                className={cn(
                  "flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition-colors disabled:cursor-default",
                  task.status === "completed"
                    ? "border-success-500 bg-success-500 hover:border-neutral-300 hover:bg-white"
                    : task.status === "skipped"
                    ? "border-amber-400 bg-amber-50 hover:border-neutral-300 hover:bg-white"
                    : task.status === "blocked"
                    ? "border-danger-400 bg-danger-50"
                    : "border-neutral-300 hover:border-success-400"
                )}
                title={
                  task.status === "completed" ? "Click to undo"
                  : task.status === "skipped" ? "Click to restore"
                  : "Mark complete"
                }
              >
                {task.status === "completed" && <CheckCircle className="h-4 w-4 text-white" />}
                {task.status === "skipped" && <SkipForward className="h-3 w-3 text-amber-500" />}
                {task.status === "blocked" && <XCircle className="h-3 w-3 text-danger-400" />}
              </button>

              {/* Title + meta */}
              <div className="flex-1 min-w-0">
                <p className={cn(
                  "text-sm",
                  task.status === "completed" && "text-neutral-400 line-through",
                  task.status === "skipped" && "text-neutral-400 italic",
                  task.status === "pending" && "text-neutral-900",
                )}>
                  {task.title}
                </p>
                {task.is_required && task.status === "pending" && (
                  <span className="text-xs text-danger-500">Required</span>
                )}
                {task.status === "skipped" && task.skip_reason && (
                  <span className="text-xs text-neutral-400">Reason: {task.skip_reason}</span>
                )}
              </div>

              {/* Actions */}
              {!readOnly && (
                <div className="flex items-center gap-1 shrink-0">
                  {(task.status === "completed" || task.status === "skipped") && (
                    <button
                      onClick={() => completeTask.mutate({ taskId: task.id, data: { status: "pending" } })}
                      disabled={completeTask.isPending}
                      className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-neutral-400 hover:bg-neutral-100 hover:text-neutral-600 disabled:opacity-50"
                    >
                      <RotateCcw className="h-3 w-3" />
                      Undo
                    </button>
                  )}
                  {task.status === "pending" && !task.is_required && skippingTaskId !== task.id && (
                    <button
                      onClick={() => setSkippingTaskId(task.id)}
                      disabled={completeTask.isPending}
                      className="rounded-lg px-2 py-1 text-xs text-neutral-400 hover:bg-neutral-100 hover:text-neutral-600 disabled:opacity-50"
                    >
                      Skip
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Inline skip reason */}
            {skippingTaskId === task.id && (
              <div className="mt-2 ml-8 flex items-center gap-2">
                <input
                  type="text"
                  value={skipReason}
                  onChange={(e) => setSkipReason(e.target.value)}
                  placeholder="Reason for skipping (optional)"
                  autoFocus
                  className="input-field flex-1 py-1 text-xs"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") confirmSkip();
                    if (e.key === "Escape") { setSkippingTaskId(null); setSkipReason(""); }
                  }}
                />
                <button
                  onClick={confirmSkip}
                  disabled={completeTask.isPending}
                  className="rounded-md bg-neutral-100 px-2 py-1 text-xs font-medium text-neutral-700 hover:bg-neutral-200 disabled:opacity-50"
                >
                  {completeTask.isPending ? "…" : "Confirm"}
                </button>
                <button
                  onClick={() => { setSkippingTaskId(null); setSkipReason(""); }}
                  className="rounded-md p-1 text-neutral-400 hover:text-neutral-600"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
