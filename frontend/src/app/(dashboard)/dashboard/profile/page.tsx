"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { User, Shield, CheckCircle, AlertCircle } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { useAuthStore } from "@/stores/auth-store";
import { authApi } from "@/lib/api";
import { cn } from "@/lib/utils";

const ROLE_LABELS: Record<string, string> = {
  platform_owner: "Platform Owner",
  tenant_admin: "Admin",
  manager: "Manager",
  employee: "Employee",
  client_user: "Client",
};

const passwordSchema = z
  .object({
    current_password: z.string().min(1, "Required"),
    new_password: z
      .string()
      .min(8, "Minimum 8 characters")
      .regex(/[A-Z]/, "Must contain an uppercase letter")
      .regex(/[a-z]/, "Must contain a lowercase letter")
      .regex(/[0-9]/, "Must contain a number"),
    confirm_password: z.string().min(1, "Required"),
  })
  .refine((d) => d.new_password === d.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type PasswordFormValues = z.infer<typeof passwordSchema>;

export default function ProfilePage() {
  const { user, tenant } = useAuthStore();
  const [pwSuccess, setPwSuccess] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<PasswordFormValues>({ resolver: zodResolver(passwordSchema) });

  const onChangePassword = async (values: PasswordFormValues) => {
    setPwSuccess(false);
    setPwError(null);
    try {
      await authApi.changePassword({
        current_password: values.current_password,
        new_password: values.new_password,
      });
      setPwSuccess(true);
      reset();
    } catch (err: unknown) {
      setPwError(
        (err as { message?: string })?.message ?? "Failed to change password."
      );
    }
  };

  return (
    <div className="flex flex-col">
      <PageHeader
        title="My Profile"
        breadcrumbs={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Profile" },
        ]}
      />

      <div className="p-6 space-y-6 max-w-2xl">
        {/* Account info */}
        <div className="card p-6">
          <div className="mb-4 flex items-center gap-2">
            <User className="h-4 w-4 text-neutral-400" />
            <h2 className="font-semibold text-neutral-900">Account</h2>
          </div>
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-primary-100 text-xl font-bold text-primary-700">
                {user ? `${user.first_name[0]}${user.last_name[0]}` : "?"}
              </div>
              <div>
                <p className="text-base font-semibold text-neutral-900">
                  {user?.first_name} {user?.last_name}
                </p>
                <p className="text-sm text-neutral-500">{user?.email}</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 rounded-lg bg-neutral-50 p-4 text-sm">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-neutral-400">
                  Role
                </p>
                <p className="mt-1 font-medium text-neutral-800">
                  {user?.role ? (ROLE_LABELS[user.role] ?? user.role) : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-neutral-400">
                  Workspace
                </p>
                <p className="mt-1 font-medium text-neutral-800">
                  {tenant?.name ?? "—"}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Change password */}
        <div className="card p-6">
          <div className="mb-4 flex items-center gap-2">
            <Shield className="h-4 w-4 text-neutral-400" />
            <h2 className="font-semibold text-neutral-900">Change Password</h2>
          </div>

          {pwSuccess && (
            <div className="mb-4 flex items-center gap-2 rounded-lg border border-success-200 bg-success-50 px-4 py-3 text-sm text-success-700">
              <CheckCircle className="h-4 w-4 shrink-0" />
              Password updated. All other sessions have been signed out.
            </div>
          )}

          {pwError && (
            <div className="mb-4 flex items-center gap-2 rounded-lg border border-danger-200 bg-danger-50 px-4 py-3 text-sm text-danger-700">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {pwError}
            </div>
          )}

          <form onSubmit={handleSubmit(onChangePassword)} className="space-y-4">
            <div>
              <label className="label">Current Password</label>
              <input
                type="password"
                {...register("current_password")}
                className={cn("input-field", errors.current_password && "border-danger-500")}
                autoComplete="current-password"
              />
              {errors.current_password && (
                <p className="error-message">{errors.current_password.message}</p>
              )}
            </div>

            <div>
              <label className="label">New Password</label>
              <input
                type="password"
                {...register("new_password")}
                className={cn("input-field", errors.new_password && "border-danger-500")}
                autoComplete="new-password"
              />
              {errors.new_password && (
                <p className="error-message">{errors.new_password.message}</p>
              )}
            </div>

            <div>
              <label className="label">Confirm New Password</label>
              <input
                type="password"
                {...register("confirm_password")}
                className={cn("input-field", errors.confirm_password && "border-danger-500")}
                autoComplete="new-password"
              />
              {errors.confirm_password && (
                <p className="error-message">{errors.confirm_password.message}</p>
              )}
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="submit"
                disabled={isSubmitting}
                className="btn-primary"
              >
                {isSubmitting ? "Saving…" : "Update Password"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
