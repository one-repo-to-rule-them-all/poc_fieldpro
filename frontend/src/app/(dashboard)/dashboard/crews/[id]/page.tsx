"use client";

import { useState, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Users,
  Crown,
  Trash2,
  UserPlus,
  Loader2,
  AlertTriangle,
  Mail,
} from "lucide-react";
import { useCrew, useAddCrewMember, useRemoveCrewMember } from "@/hooks/use-crews";
import { usersApi } from "@/lib/api";
import { PageHeader } from "@/components/ui/page-header";
import { cn } from "@/lib/utils";
import type { CrewMember } from "@/types";

function MemberRow({
  member,
  crewId,
}: {
  member: CrewMember;
  crewId: string;
}) {
  const removeMember = useRemoveCrewMember();
  const [confirmOpen, setConfirmOpen] = useState(false);

  const name = member.user
    ? `${member.user.first_name} ${member.user.last_name}`
    : member.user_id;
  const initials = member.user
    ? `${member.user.first_name.charAt(0)}${member.user.last_name.charAt(0)}`.toUpperCase()
    : "??";

  return (
    <div className="flex items-center justify-between border-b border-neutral-100 px-4 py-3 last:border-b-0">
      <div className="flex items-center gap-3 min-w-0">
        <div
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
            member.role === "lead"
              ? "bg-amber-100 text-amber-800"
              : "bg-neutral-200 text-neutral-700"
          )}
        >
          {initials}
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-neutral-900">
            {name}
            {member.role === "lead" && (
              <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-800">
                <Crown className="h-3 w-3" />
                Lead
              </span>
            )}
          </p>
          {member.user?.email && (
            <p className="flex items-center gap-1 truncate text-xs text-neutral-500">
              <Mail className="h-3 w-3" />
              {member.user.email}
            </p>
          )}
        </div>
      </div>

      {!confirmOpen ? (
        <button
          onClick={() => setConfirmOpen(true)}
          className="rounded p-1.5 text-neutral-400 hover:bg-danger-50 hover:text-danger-600"
          aria-label="Remove member"
          title="Remove member"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      ) : (
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-neutral-600">Remove?</span>
          <button
            onClick={() =>
              removeMember.mutate(
                { crewId, userId: member.user_id },
                { onSettled: () => setConfirmOpen(false) }
              )
            }
            disabled={removeMember.isPending}
            className="rounded bg-danger-600 px-2 py-1 text-xs font-semibold text-white hover:bg-danger-700 disabled:opacity-50"
          >
            {removeMember.isPending ? "…" : "Yes"}
          </button>
          <button
            onClick={() => setConfirmOpen(false)}
            disabled={removeMember.isPending}
            className="rounded border border-neutral-300 px-2 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-50 disabled:opacity-50"
          >
            No
          </button>
        </div>
      )}
    </div>
  );
}

function AddMemberForm({
  crewId,
  existingUserIds,
}: {
  crewId: string;
  existingUserIds: Set<string>;
}) {
  const [selectedUserId, setSelectedUserId] = useState("");
  const [role, setRole] = useState<"lead" | "member">("member");

  const addMember = useAddCrewMember();

  const { data: usersData, isLoading: usersLoading } = useQuery({
    queryKey: ["users", "list", { is_active: true }],
    queryFn: () => usersApi.list({ is_active: true, limit: 100 }),
    staleTime: 60_000,
  });

  const availableUsers = useMemo(() => {
    return (usersData?.data ?? []).filter((u) => !existingUserIds.has(u.id));
  }, [usersData, existingUserIds]);

  const onAdd = () => {
    if (!selectedUserId) return;
    addMember.mutate(
      { crewId, user_id: selectedUserId, role },
      {
        onSuccess: () => {
          setSelectedUserId("");
          setRole("member");
        },
      }
    );
  };

  return (
    <div className="rounded-lg border border-neutral-200 bg-neutral-50 p-4">
      <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-neutral-700">
        <UserPlus className="h-4 w-4" />
        Add Member
      </h4>
      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-56 flex-1">
          <label className="label text-xs">User</label>
          <select
            value={selectedUserId}
            onChange={(e) => setSelectedUserId(e.target.value)}
            disabled={usersLoading || addMember.isPending}
            className="input-field text-sm"
          >
            <option value="">
              {usersLoading
                ? "Loading users…"
                : availableUsers.length === 0
                ? "No users available"
                : "Select a user…"}
            </option>
            {availableUsers.map((u) => (
              <option key={u.id} value={u.id}>
                {u.first_name} {u.last_name} ({u.email})
              </option>
            ))}
          </select>
        </div>
        <div className="min-w-32">
          <label className="label text-xs">Role</label>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as "lead" | "member")}
            disabled={addMember.isPending}
            className="input-field text-sm"
          >
            <option value="member">Member</option>
            <option value="lead">Lead</option>
          </select>
        </div>
        <button
          onClick={onAdd}
          disabled={!selectedUserId || addMember.isPending}
          className="btn-primary text-sm disabled:opacity-50"
        >
          {addMember.isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Adding…
            </>
          ) : (
            "Add"
          )}
        </button>
      </div>
      {addMember.isError && (
        <p className="mt-2 text-xs text-danger-600">
          Failed to add member — they may already be on this crew.
        </p>
      )}
    </div>
  );
}

export default function CrewDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const { data: crew, isLoading, isError } = useCrew(id);

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary-500" />
      </div>
    );
  }

  if (isError || !crew) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-2 text-neutral-400">
        <AlertTriangle className="h-10 w-10" />
        <p>Crew not found</p>
        <button
          onClick={() => router.push("/dashboard/crews")}
          className="btn-secondary mt-2 text-sm"
        >
          Back to crews
        </button>
      </div>
    );
  }

  const members = crew.members ?? [];
  const lead = members.find((m) => m.role === "lead");
  const existingUserIds = new Set(members.map((m) => m.user_id));

  return (
    <div>
      <PageHeader
        title={crew.name}
        subtitle={crew.code}
        breadcrumbs={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Crews", href: "/dashboard/crews" },
          { label: crew.name },
        ]}
        actions={
          <span
            className={cn(
              "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
              crew.is_active
                ? "bg-success-100 text-success-700"
                : "bg-neutral-100 text-neutral-500"
            )}
          >
            {crew.is_active ? "Active" : "Inactive"}
          </span>
        }
      />

      <div className="space-y-6 p-6">
        {/* Crew summary */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="card p-4">
            <div className="flex items-center gap-2 text-xs text-neutral-500">
              <Users className="h-3.5 w-3.5" />
              Members
            </div>
            <p className="mt-1 text-lg font-semibold text-neutral-900">
              {members.length}
            </p>
          </div>
          <div className="card p-4">
            <div className="flex items-center gap-2 text-xs text-neutral-500">
              <Crown className="h-3.5 w-3.5" />
              Lead
            </div>
            <p className="mt-1 text-sm font-medium text-neutral-900">
              {lead?.user
                ? `${lead.user.first_name} ${lead.user.last_name}`
                : "No lead assigned"}
            </p>
          </div>
          <div className="card p-4">
            <div className="text-xs text-neutral-500">Description</div>
            <p className="mt-1 text-sm text-neutral-900">
              {crew.description ?? "—"}
            </p>
          </div>
        </div>

        {/* Member roster */}
        <div className="card overflow-hidden">
          <div className="border-b border-neutral-200 px-4 py-3">
            <h3 className="text-sm font-semibold text-neutral-700">
              Members ({members.length})
            </h3>
          </div>
          {members.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-12 text-neutral-400">
              <Users className="h-10 w-10" />
              <p className="text-sm">No members on this crew yet.</p>
            </div>
          ) : (
            <div>
              {members.map((m) => (
                <MemberRow key={m.id} member={m} crewId={crew.id} />
              ))}
            </div>
          )}
        </div>

        {/* Add member form */}
        <AddMemberForm crewId={crew.id} existingUserIds={existingUserIds} />
      </div>
    </div>
  );
}
