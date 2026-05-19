"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { Navbar } from "@/components/layout/navbar";
import { GlobalModals } from "@/components/layout/global-modals";
import { useAuthStore } from "@/stores/auth-store";
import { cn } from "@/lib/utils";
import { useSidebar } from "@/stores/ui-store";

/**
 * Tracks Zustand persist hydration. The store reads localStorage asynchronously
 * on first mount, so `isAuthenticated` is briefly its initial-state `false`
 * before rehydration. Without this guard, a hard page refresh on a protected
 * route triggers a flash-redirect to /login.
 */
function useAuthHydrated() {
  const [hydrated, setHydrated] = useState(() => useAuthStore.persist.hasHydrated());
  useEffect(() => {
    const unsub = useAuthStore.persist.onFinishHydration(() => setHydrated(true));
    setHydrated(useAuthStore.persist.hasHydrated());
    return unsub;
  }, []);
  return hydrated;
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const hydrated = useAuthHydrated();
  const { isAuthenticated, isLoading } = useAuthStore();
  const { isCollapsed } = useSidebar();

  useEffect(() => {
    if (hydrated && !isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [hydrated, isAuthenticated, isLoading, router]);

  // Show nothing while checking auth (either store loading, or persist still hydrating)
  if (!hydrated || isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-neutral-50">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
          <p className="text-sm text-neutral-500">Loading…</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-neutral-50">
      {/* Sidebar */}
      <Sidebar />

      {/* Main content */}
      <div
        className={cn(
          "flex flex-1 flex-col overflow-hidden transition-all duration-300",
          // On desktop, account for sidebar width
          "lg:ml-0"
        )}
      >
        <Navbar />

        <main
          className={cn(
            "flex-1 overflow-y-auto",
            // Add bottom padding on mobile for the tab bar
            "pb-16 lg:pb-0"
          )}
        >
          {children}
        </main>
      </div>

      <GlobalModals />
    </div>
  );
}
