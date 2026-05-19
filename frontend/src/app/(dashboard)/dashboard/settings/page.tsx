"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useAuth } from "@/hooks/use-auth";
import { useAuthStore } from "@/stores/auth-store";
import { authApi } from "@/lib/api";
import { TIMINGS } from "@/lib/timings";

// ─── Schemas ──────────────────────────────────────────────────────────────────

const profileSchema = z.object({
  first_name: z.string().min(1, "First name is required"),
  last_name: z.string().min(1, "Last name is required"),
  email: z.string().email("Invalid email address"),
  phone: z.string().optional(),
});

const passwordSchema = z
  .object({
    current_password: z.string().min(1, "Current password is required"),
    new_password: z.string().min(8, "Minimum 8 characters"),
    confirm_password: z.string(),
  })
  .refine((d) => d.new_password === d.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type ProfileForm = z.infer<typeof profileSchema>;
type PasswordForm = z.infer<typeof passwordSchema>;

const TABS = ["Profile", "Company", "Security", "Notifications"] as const;
type Tab = (typeof TABS)[number];

// ─── Shared field component ───────────────────────────────────────────────────

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-sm font-medium text-neutral-700">{label}</label>
      {children}
      {error && <p className="text-xs text-danger-600">{error}</p>}
    </div>
  );
}

const inputCls =
  "rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 placeholder-neutral-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:bg-neutral-50 disabled:text-neutral-500";

// ─── Tab: Profile ─────────────────────────────────────────────────────────────

function ProfileTab() {
  const { user } = useAuth();
  const updateUser = useAuthStore((s) => s.updateUser);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<ProfileForm>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      first_name: user?.first_name ?? "",
      last_name: user?.last_name ?? "",
      email: user?.email ?? "",
      phone: (user as (typeof user & { phone?: string }))?.phone ?? "",
    },
  });

  const onSubmit = async (data: ProfileForm) => {
    setSaveError(null);
    try {
      const updated = await authApi.updateProfile({
        first_name: data.first_name,
        last_name: data.last_name,
        phone: data.phone || undefined,
      });
      updateUser(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), TIMINGS.TOAST_SUCCESS_MS);
    } catch (err: unknown) {
      setSaveError((err as { message?: string })?.message ?? "Failed to save.");
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="max-w-lg space-y-5">
      <div className="grid grid-cols-2 gap-4">
        <Field label="First name" error={errors.first_name?.message}>
          <input {...register("first_name")} className={inputCls} />
        </Field>
        <Field label="Last name" error={errors.last_name?.message}>
          <input {...register("last_name")} className={inputCls} />
        </Field>
      </div>
      <Field label="Email" error={errors.email?.message}>
        <input {...register("email")} type="email" className={inputCls} />
      </Field>
      <Field label="Phone" error={errors.phone?.message}>
        <input {...register("phone")} type="tel" placeholder="+1 (555) 000-0000" className={inputCls} />
      </Field>

      {saveError && (
        <p className="text-xs text-danger-600">{saveError}</p>
      )}
      <div className="flex items-center gap-3 pt-2">
        <button
          type="submit"
          disabled={isSubmitting || !isDirty}
          className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50 transition-colors"
        >
          {isSubmitting ? "Saving…" : "Save changes"}
        </button>
        {saved && (
          <span className="text-sm text-success-600 font-medium">Saved!</span>
        )}
      </div>
    </form>
  );
}

// ─── Tab: Company ─────────────────────────────────────────────────────────────

function CompanyTab() {
  const { tenant } = useAuth();

  return (
    <div className="max-w-lg space-y-5">
      <Field label="Company name" error={undefined}>
        <input defaultValue={tenant?.name ?? ""} className={inputCls} />
      </Field>
      <Field label="Industry" error={undefined}>
        <select className={inputCls}>
          <option>Cleaning Services</option>
          <option>HVAC</option>
          <option>Plumbing</option>
          <option>Electrical</option>
          <option>Landscaping</option>
          <option>Other</option>
        </select>
      </Field>
      <Field label="Timezone" error={undefined}>
        <select className={inputCls}>
          <option value="America/New_York">Eastern (ET)</option>
          <option value="America/Chicago">Central (CT)</option>
          <option value="America/Denver">Mountain (MT)</option>
          <option value="America/Los_Angeles">Pacific (PT)</option>
        </select>
      </Field>
      <Field label="Logo" error={undefined}>
        <div className="flex items-center gap-4">
          <div className="h-16 w-16 rounded-lg border-2 border-dashed border-neutral-300 flex items-center justify-center bg-neutral-50 text-neutral-400 text-xs text-center leading-tight px-1">
            No logo
          </div>
          <label className="cursor-pointer rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-700 hover:bg-neutral-50 transition-colors">
            Upload logo
            <input type="file" accept="image/*" className="sr-only" />
          </label>
        </div>
      </Field>
      <button className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 transition-colors">
        Save changes
      </button>
    </div>
  );
}

// ─── Tab: Security ────────────────────────────────────────────────────────────

function SecurityTab() {
  const [mfaEnabled, setMfaEnabled] = useState(false);
  const [pwSuccess, setPwSuccess] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<PasswordForm>({ resolver: zodResolver(passwordSchema) });

  const onSubmit = async (data: PasswordForm) => {
    setPwSuccess(false);
    setPwError(null);
    try {
      await authApi.changePassword({
        current_password: data.current_password,
        new_password: data.new_password,
      });
      setPwSuccess(true);
      reset();
    } catch (err: unknown) {
      setPwError((err as { message?: string })?.message ?? "Failed to change password.");
    }
  };

  return (
    <div className="max-w-lg space-y-8">
      <div>
        <h3 className="text-base font-semibold text-neutral-800 mb-4">Change password</h3>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <Field label="Current password" error={errors.current_password?.message}>
            <input {...register("current_password")} type="password" className={inputCls} autoComplete="current-password" />
          </Field>
          <Field label="New password" error={errors.new_password?.message}>
            <input {...register("new_password")} type="password" className={inputCls} autoComplete="new-password" />
          </Field>
          <Field label="Confirm new password" error={errors.confirm_password?.message}>
            <input {...register("confirm_password")} type="password" className={inputCls} autoComplete="new-password" />
          </Field>
          {pwSuccess && (
            <p className="text-sm text-success-600 font-medium">Password updated. Other sessions have been signed out.</p>
          )}
          {pwError && (
            <p className="text-sm text-danger-600">{pwError}</p>
          )}
          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50 transition-colors"
          >
            {isSubmitting ? "Updating…" : "Update password"}
          </button>
        </form>
      </div>

      <div className="border-t border-neutral-200 pt-6">
        <h3 className="text-base font-semibold text-neutral-800 mb-1">
          Multi-factor authentication
        </h3>
        <p className="text-sm text-neutral-500 mb-4">
          Add an extra layer of security to your account.
        </p>
        <div className="flex items-center gap-4">
          <span
            className={`text-sm font-medium ${mfaEnabled ? "text-success-700" : "text-neutral-500"}`}
          >
            {mfaEnabled ? "Enabled" : "Disabled"}
          </span>
          <button
            onClick={() => setMfaEnabled((v) => !v)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              mfaEnabled ? "bg-primary-600" : "bg-neutral-300"
            }`}
          >
            <span
              className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${
                mfaEnabled ? "translate-x-6" : "translate-x-1"
              }`}
            />
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Tab: Notifications ───────────────────────────────────────────────────────

const NOTIFICATION_OPTIONS = [
  { key: "work_order_assigned", label: "Work order assigned to me" },
  { key: "work_order_status_changed", label: "Work order status changes" },
  { key: "invoice_paid", label: "Invoice paid" },
  { key: "invoice_overdue", label: "Invoice overdue reminder" },
  { key: "crew_check_in", label: "Crew check-in / check-out" },
  { key: "daily_summary", label: "Daily summary digest" },
] as const;

function NotificationsTab() {
  const [toggles, setToggles] = useState<Record<string, boolean>>({
    work_order_assigned: true,
    invoice_overdue: true,
    daily_summary: false,
    crew_check_in: false,
    work_order_status_changed: true,
    invoice_paid: false,
  });

  const toggle = (key: string) =>
    setToggles((prev) => ({ ...prev, [key]: !prev[key] }));

  return (
    <div className="max-w-lg">
      <p className="text-sm text-neutral-500 mb-5">
        Choose which events trigger email notifications.
      </p>
      <ul className="divide-y divide-neutral-100">
        {NOTIFICATION_OPTIONS.map(({ key, label }) => (
          <li key={key} className="flex items-center justify-between py-3">
            <span className="text-sm text-neutral-800">{label}</span>
            <button
              onClick={() => toggle(key)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                toggles[key] ? "bg-primary-600" : "bg-neutral-300"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${
                  toggles[key] ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("Profile");

  return (
    <div className="p-4 md:p-8 max-w-4xl mx-auto">
      <h1 className="text-2xl font-semibold text-neutral-900 mb-6">Settings</h1>

      {/* Tab bar */}
      <div className="border-b border-neutral-200 mb-8">
        <nav className="-mb-px flex gap-6 overflow-x-auto">
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`shrink-0 pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab
                  ? "border-primary-600 text-primary-600"
                  : "border-transparent text-neutral-500 hover:text-neutral-700 hover:border-neutral-300"
              }`}
            >
              {tab}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === "Profile" && <ProfileTab />}
      {activeTab === "Company" && <CompanyTab />}
      {activeTab === "Security" && <SecurityTab />}
      {activeTab === "Notifications" && <NotificationsTab />}
    </div>
  );
}
