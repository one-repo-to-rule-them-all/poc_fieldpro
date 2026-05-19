"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, EyeOff, Loader2, CheckCircle } from "lucide-react";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import { cn } from "@/lib/utils";

const PASSWORD_REQUIREMENTS = [
  { label: "At least 8 characters", test: (p: string) => p.length >= 8 },
  { label: "One uppercase letter", test: (p: string) => /[A-Z]/.test(p) },
  { label: "One number", test: (p: string) => /\d/.test(p) },
  {
    label: "One special character",
    test: (p: string) => /[!@#$%^&*(),.?":{}|<>]/.test(p),
  },
];

const registerSchema = z
  .object({
    company_name: z
      .string()
      .min(2, "Company name must be at least 2 characters")
      .max(100, "Company name is too long"),
    first_name: z
      .string()
      .min(1, "First name is required")
      .max(50, "First name is too long"),
    last_name: z
      .string()
      .min(1, "Last name is required")
      .max(50, "Last name is too long"),
    email: z.string().email("Enter a valid email address"),
    password: z
      .string()
      .min(8, "Password must be at least 8 characters")
      .regex(/[A-Z]/, "Password must contain an uppercase letter")
      .regex(/\d/, "Password must contain a number")
      .regex(
        /[!@#$%^&*(),.?":{}|<>]/,
        "Password must contain a special character"
      ),
    confirm_password: z.string(),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type RegisterFormValues = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const router = useRouter();
  const { setTokens, setUser } = useAuthStore();
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      company_name: "",
      first_name: "",
      last_name: "",
      email: "",
      password: "",
      confirm_password: "",
    },
  });

  const passwordValue = watch("password", "");

  const onSubmit = async (values: RegisterFormValues) => {
    setServerError(null);
    try {
      const response = await authApi.register({
        company_name: values.company_name,
        first_name: values.first_name,
        last_name: values.last_name,
        email: values.email,
        password: values.password,
      });

      setTokens(response.access_token, response.refresh_token);
      setUser(response.user, response.tenant);
      router.push("/dashboard/onboarding");
    } catch (err: unknown) {
      const message =
        (err as { message?: string })?.message ??
        "Registration failed. Please try again.";
      setServerError(message);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-primary-50 to-neutral-100 px-4 py-12">
      <div className="w-full max-w-lg">
        {/* Header */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-600 shadow-lg">
            <span className="text-2xl font-bold text-white">F</span>
          </div>
          <h1 className="text-2xl font-bold text-neutral-900">
            Start your free trial
          </h1>
          <p className="mt-1 text-sm text-neutral-500">
            Set up your FieldPro workspace in minutes
          </p>
        </div>

        <div className="card p-8">
          {serverError && (
            <div className="mb-6 rounded-lg border border-danger-200 bg-danger-50 px-4 py-3 text-sm text-danger-700">
              {serverError}
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} noValidate>
            {/* Company name */}
            <div className="mb-4">
              <label htmlFor="company_name" className="label">
                Company name
              </label>
              <input
                id="company_name"
                type="text"
                autoComplete="organization"
                className={cn(
                  "input-field",
                  errors.company_name && "border-danger-500"
                )}
                placeholder="Acme Field Services"
                {...register("company_name")}
              />
              {errors.company_name && (
                <p className="error-message">{errors.company_name.message}</p>
              )}
            </div>

            {/* Name row */}
            <div className="mb-4 grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="first_name" className="label">
                  First name
                </label>
                <input
                  id="first_name"
                  type="text"
                  autoComplete="given-name"
                  className={cn(
                    "input-field",
                    errors.first_name && "border-danger-500"
                  )}
                  placeholder="Jane"
                  {...register("first_name")}
                />
                {errors.first_name && (
                  <p className="error-message">{errors.first_name.message}</p>
                )}
              </div>
              <div>
                <label htmlFor="last_name" className="label">
                  Last name
                </label>
                <input
                  id="last_name"
                  type="text"
                  autoComplete="family-name"
                  className={cn(
                    "input-field",
                    errors.last_name && "border-danger-500"
                  )}
                  placeholder="Smith"
                  {...register("last_name")}
                />
                {errors.last_name && (
                  <p className="error-message">{errors.last_name.message}</p>
                )}
              </div>
            </div>

            {/* Email */}
            <div className="mb-4">
              <label htmlFor="email" className="label">
                Work email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                className={cn(
                  "input-field",
                  errors.email && "border-danger-500"
                )}
                placeholder="jane@acme.com"
                {...register("email")}
              />
              {errors.email && (
                <p className="error-message">{errors.email.message}</p>
              )}
            </div>

            {/* Password */}
            <div className="mb-4">
              <label htmlFor="password" className="label">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="new-password"
                  className={cn(
                    "input-field pr-10",
                    errors.password && "border-danger-500"
                  )}
                  placeholder="Create a strong password"
                  {...register("password")}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute inset-y-0 right-0 flex items-center px-3 text-neutral-400 hover:text-neutral-600"
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

              {/* Password strength checklist */}
              {passwordValue && (
                <ul className="mt-2 space-y-1">
                  {PASSWORD_REQUIREMENTS.map((req) => {
                    const passed = req.test(passwordValue);
                    return (
                      <li
                        key={req.label}
                        className={cn(
                          "flex items-center gap-1.5 text-xs",
                          passed ? "text-success-600" : "text-neutral-400"
                        )}
                      >
                        <CheckCircle className="h-3 w-3 shrink-0" />
                        {req.label}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {/* Confirm Password */}
            <div className="mb-6">
              <label htmlFor="confirm_password" className="label">
                Confirm password
              </label>
              <div className="relative">
                <input
                  id="confirm_password"
                  type={showConfirm ? "text" : "password"}
                  autoComplete="new-password"
                  className={cn(
                    "input-field pr-10",
                    errors.confirm_password && "border-danger-500"
                  )}
                  placeholder="Repeat your password"
                  {...register("confirm_password")}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm((v) => !v)}
                  className="absolute inset-y-0 right-0 flex items-center px-3 text-neutral-400 hover:text-neutral-600"
                >
                  {showConfirm ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
              {errors.confirm_password && (
                <p className="error-message">
                  {errors.confirm_password.message}
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="btn-primary w-full py-2.5"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Creating your account…
                </>
              ) : (
                "Create account"
              )}
            </button>

            <p className="mt-4 text-center text-xs text-neutral-400">
              By creating an account you agree to our{" "}
              <a href="/terms" className="underline hover:text-neutral-600">
                Terms of Service
              </a>{" "}
              and{" "}
              <a href="/privacy" className="underline hover:text-neutral-600">
                Privacy Policy
              </a>
              .
            </p>
          </form>
        </div>

        <p className="mt-6 text-center text-sm text-neutral-500">
          Already have an account?{" "}
          <Link
            href="/login"
            className="font-medium text-primary-600 hover:text-primary-700"
          >
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
