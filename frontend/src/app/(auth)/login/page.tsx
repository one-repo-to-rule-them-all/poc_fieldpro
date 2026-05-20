"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, EyeOff, Loader2, Zap } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import { cn } from "@/lib/utils";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

const DEMO_LOGINS: ReadonlyArray<{
  label: string;
  email: string;
  password: string;
}> = [
  { label: "Admin", email: "admin@demo.fieldpro.app", password: "Admin123!" },
  { label: "Manager", email: "manager@demo.fieldpro.app", password: "Manager123!" },
  { label: "Field worker", email: "carlos@demo.fieldpro.app", password: "Employee123!" },
];

export default function LoginPage() {
  const router = useRouter();
  const login = useAuthStore((s) => s.login);
  const [showPassword, setShowPassword] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = async (values: LoginFormValues) => {
    setServerError(null);
    try {
      await login(values.email, values.password);
      router.push("/dashboard");
    } catch (err: unknown) {
      const message =
        (err as { message?: string })?.message ??
        "Invalid email or password. Please try again.";
      setServerError(message);
    }
  };

  const quickLogin = async (email: string, password: string) => {
    setServerError(null);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err: unknown) {
      const message =
        (err as { message?: string })?.message ??
        "Demo login failed. The demo may be resetting — try again in a moment.";
      setServerError(message);
    }
  };

  return (
    <div className="flex min-h-screen">
      {/* Left panel — branding */}
      <div className="hidden lg:flex lg:w-[420px] xl:w-[480px] flex-col justify-between bg-neutral-900 p-10">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary-600 shadow-lg shadow-primary-900/40">
            <span className="text-base font-bold text-white">F</span>
          </div>
          <span className="text-lg font-bold text-white">FieldPro</span>
        </div>

        <div>
          <blockquote className="text-lg font-medium leading-relaxed text-neutral-200">
            &ldquo;FieldPro cut our scheduling time in half and gave our crews
            real-time visibility. It&apos;s the backbone of our operations.&rdquo;
          </blockquote>
          <div className="mt-6 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-600/20 text-sm font-semibold text-primary-400">
              MR
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Marcus Rivera</p>
              <p className="text-xs text-neutral-400">Operations Director, CleanPro Services</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-6">
          {[
            { label: "Work Orders", value: "50K+" },
            { label: "Field Teams", value: "1,200+" },
            { label: "Uptime", value: "99.9%" },
          ].map((stat) => (
            <div key={stat.label}>
              <p className="text-xl font-bold text-white">{stat.value}</p>
              <p className="text-xs text-neutral-500">{stat.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Right panel — form */}
      <div className="flex flex-1 flex-col items-center justify-center px-6 py-12 bg-neutral-50">
        {/* Mobile logo */}
        <div className="mb-8 flex items-center gap-2.5 lg:hidden">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary-600">
            <span className="text-base font-bold text-white">F</span>
          </div>
          <span className="text-lg font-bold text-neutral-900">FieldPro</span>
        </div>

        <div className="w-full max-w-[380px]">
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-neutral-900">Welcome back</h1>
            <p className="mt-1.5 text-sm text-neutral-500">
              Sign in to your FieldPro account
            </p>
          </div>

          <div className="card p-7">
            {serverError && (
              <div
                data-testid="login-error"
                className="mb-5 flex items-start gap-2.5 rounded-lg border border-danger-200 bg-danger-50 px-4 py-3"
              >
                <div className="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-danger-500" />
                <p className="text-sm text-danger-700">{serverError}</p>
              </div>
            )}

            <form onSubmit={handleSubmit(onSubmit)} noValidate>
              <div className="mb-4">
                <label htmlFor="email" className="label">
                  Email address
                </label>
                <input
                  id="email"
                  data-testid="login-email"
                  type="email"
                  autoComplete="email"
                  autoFocus
                  className={cn(
                    "input-field",
                    errors.email &&
                      "border-danger-400 focus:border-danger-400 focus:ring-danger-100"
                  )}
                  placeholder="you@company.com"
                  {...register("email")}
                />
                {errors.email && (
                  <p className="error-message">{errors.email.message}</p>
                )}
              </div>

              <div className="mb-6">
                <div className="mb-1 flex items-center justify-between">
                  <label htmlFor="password" className="label mb-0">
                    Password
                  </label>
                  <span
                    className="cursor-not-allowed text-xs font-medium text-neutral-400"
                    title="Disabled in the public demo"
                  >
                    Forgot password?
                  </span>
                </div>
                <div className="relative">
                  <input
                    id="password"
                    data-testid="login-password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    className={cn(
                      "input-field pr-10",
                      errors.password &&
                        "border-danger-400 focus:border-danger-400 focus:ring-danger-100"
                    )}
                    placeholder="••••••••"
                    {...register("password")}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute inset-y-0 right-0 flex items-center px-3 text-neutral-400 hover:text-neutral-600 transition-colors"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
                {errors.password && (
                  <p className="error-message">{errors.password.message}</p>
                )}
              </div>

              <button
                type="submit"
                data-testid="login-submit"
                disabled={isSubmitting}
                className="btn-primary w-full py-2.5"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Signing in…
                  </>
                ) : (
                  <>
                    <Zap className="h-4 w-4" />
                    Sign in
                  </>
                )}
              </button>
            </form>

            <div className="mt-6 border-t border-neutral-200 pt-5">
              <p className="mb-3 text-center text-xs font-medium uppercase tracking-wider text-neutral-500">
                Or try the demo
              </p>
              <div className="grid grid-cols-3 gap-2">
                {DEMO_LOGINS.map((d) => (
                  <button
                    key={d.email}
                    type="button"
                    onClick={() => quickLogin(d.email, d.password)}
                    disabled={isSubmitting}
                    className="rounded-lg border border-neutral-200 bg-white px-2 py-2 text-xs font-medium text-neutral-700 transition-colors hover:border-primary-300 hover:bg-primary-50 hover:text-primary-700 disabled:opacity-50"
                  >
                    {d.label}
                  </button>
                ))}
              </div>
              <p className="mt-3 text-center text-[11px] text-neutral-400">
                Public demo · data resets nightly
              </p>
            </div>
          </div>

          <p className="mt-5 text-center text-sm text-neutral-500">
            Sign-up is disabled in the public demo. To run your own instance,{" "}
            <a
              href="https://github.com/one-repo-to-rule-them-all/poc_fieldpro"
              target="_blank"
              rel="noreferrer noopener"
              className="font-semibold text-primary-600 hover:text-primary-700 transition-colors"
            >
              view the source
            </a>
            .
          </p>
        </div>
      </div>
    </div>
  );
}
