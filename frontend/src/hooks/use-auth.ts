"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import type { UserRole } from "@/types";

// Role hierarchy for permission checks
const ROLE_HIERARCHY: Record<UserRole, number> = {
  platform_owner: 100,
  tenant_admin: 80,
  manager: 60,
  employee: 40,
  client_user: 20,
};

// Permission map — which roles can perform which actions
const PERMISSIONS: Record<string, UserRole[]> = {
  "work-orders:create": ["platform_owner", "tenant_admin", "manager"],
  "work-orders:delete": ["platform_owner", "tenant_admin", "manager"],
  "work-orders:assign": ["platform_owner", "tenant_admin", "manager"],
  "work-orders:view": [
    "platform_owner",
    "tenant_admin",
    "manager",
    "employee",
  ],
  "work-orders:check-in": ["platform_owner", "tenant_admin", "manager", "employee"],
  "clients:create": ["platform_owner", "tenant_admin", "manager"],
  "clients:delete": ["platform_owner", "tenant_admin"],
  "clients:view": ["platform_owner", "tenant_admin", "manager"],
  "invoices:create": ["platform_owner", "tenant_admin", "manager"],
  "invoices:view": ["platform_owner", "tenant_admin", "manager"],
  "crews:manage": ["platform_owner", "tenant_admin", "manager"],
  "analytics:view": ["platform_owner", "tenant_admin", "manager"],
  "settings:manage": ["platform_owner", "tenant_admin"],
};

export function useAuth() {
  const router = useRouter();
  const {
    user,
    tenant,
    isAuthenticated,
    isLoading,
    login: storeLogin,
    logout: storeLogout,
    updateUser,
  } = useAuthStore();

  const login = useCallback(
    async (email: string, password: string) => {
      await storeLogin(email, password);
      // Read role from fresh store state — the `user` closured at hook render
      // time is stale immediately after the await.
      const role = useAuthStore.getState().user?.role;
      router.push(role === "employee" ? "/dashboard/check-in" : "/dashboard");
    },
    [storeLogin, router]
  );

  const logout = useCallback(async () => {
    await storeLogout();
    router.push("/login");
  }, [storeLogout, router]);

  const hasRole = useCallback(
    (requiredRole: UserRole): boolean => {
      if (!user) return false;
      const userLevel = ROLE_HIERARCHY[user.role] ?? 0;
      const requiredLevel = ROLE_HIERARCHY[requiredRole] ?? 0;
      return userLevel >= requiredLevel;
    },
    [user]
  );

  const hasPermission = useCallback(
    (permission: string): boolean => {
      if (!user) return false;
      const allowedRoles = PERMISSIONS[permission];
      if (!allowedRoles) return false;
      return allowedRoles.includes(user.role);
    },
    [user]
  );

  const isFieldWorker = useCallback((): boolean => {
    return user?.role === "employee";
  }, [user]);

  const isAdmin = useCallback((): boolean => {
    return (
      user?.role === "tenant_admin" || user?.role === "platform_owner"
    );
  }, [user]);

  return {
    user,
    tenant,
    isAuthenticated,
    isLoading,
    login,
    logout,
    hasRole,
    hasPermission,
    isFieldWorker,
    isAdmin,
    updateUser,
    fullName: user ? `${user.first_name} ${user.last_name}` : "",
  };
}
