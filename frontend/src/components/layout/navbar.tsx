"use client";

import { useState } from "react";
import Link from "next/link";
import type { Route } from "next";
import { usePathname } from "next/navigation";
import {
  Bell,
  ChevronDown,
  User,
  Settings,
  LogOut,
  Search,
  Menu,
} from "lucide-react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { cn, getInitials, formatRelativeTime } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { useNotifications } from "@/stores/ui-store";
import { useSidebar } from "@/stores/ui-store";

const ROUTE_LABELS: Record<string, string> = {
  dashboard: "Dashboard",
  "work-orders": "Work Orders",
  schedule: "Schedule",
  clients: "Clients",
  locations: "Locations",
  crews: "Crews",
  invoices: "Invoices",
  analytics: "Analytics",
  settings: "Settings",
};

function getBreadcrumbs(pathname: string) {
  const segments = pathname.split("/").filter(Boolean);
  const crumbs: { label: string; href: string }[] = [];

  let path = "";
  for (const seg of segments) {
    path += `/${seg}`;
    const label = ROUTE_LABELS[seg];
    if (!label) continue;
    crumbs.push({ label, href: path });
  }
  return crumbs;
}

export function Navbar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { items: notifications, unreadCount, dismiss, markAllRead } =
    useNotifications();
  const { toggle } = useSidebar();
  const [notifOpen, setNotifOpen] = useState(false);

  const breadcrumbs = getBreadcrumbs(pathname);
  const pageTitle = breadcrumbs[breadcrumbs.length - 1]?.label ?? "Dashboard";

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-4 border-b border-neutral-200 bg-white px-4 sm:px-6">
      {/* Left: hamburger (mobile) + breadcrumbs */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={toggle}
          className="rounded-lg p-1.5 text-neutral-500 hover:bg-neutral-100 lg:hidden"
          aria-label="Toggle menu"
        >
          <Menu className="h-5 w-5" />
        </button>

        <nav className="hidden items-center gap-1.5 text-sm sm:flex" aria-label="Breadcrumb">
          {breadcrumbs.map((crumb, i) => {
            const isLast = i === breadcrumbs.length - 1;
            return (
              <span key={crumb.href} className="flex items-center gap-1.5">
                {i > 0 && <span className="text-neutral-300">/</span>}
                {isLast ? (
                  <span className="font-semibold text-neutral-900">{crumb.label}</span>
                ) : (
                  <Link
                    href={crumb.href as Route}
                    className="text-neutral-400 hover:text-neutral-600 transition-colors"
                  >
                    {crumb.label}
                  </Link>
                )}
              </span>
            );
          })}
          {breadcrumbs.length === 0 && (
            <span className="font-semibold text-neutral-900">{pageTitle}</span>
          )}
        </nav>

        {/* Mobile: just page title */}
        <span className="text-sm font-semibold text-neutral-900 sm:hidden">
          {pageTitle}
        </span>
      </div>

      {/* Center: search */}
      <div className="hidden flex-1 max-w-sm md:block">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-neutral-400 pointer-events-none" />
          <input
            type="text"
            placeholder="Search work orders, clients…"
            className="w-full rounded-lg border border-neutral-200 bg-neutral-50 py-1.5 pl-8 pr-3 text-sm text-neutral-900 placeholder-neutral-400 transition-colors focus:border-primary-300 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-100"
          />
        </div>
      </div>

      <div className="ml-auto flex items-center gap-1">
        {/* Notifications */}
        <DropdownMenu.Root open={notifOpen} onOpenChange={setNotifOpen}>
          <DropdownMenu.Trigger asChild>
            <button
              className="relative rounded-lg p-2 text-neutral-500 hover:bg-neutral-100 transition-colors"
              aria-label="Notifications"
            >
              <Bell className="h-4.5 w-4.5" />
              {unreadCount > 0 && (
                <span className="absolute right-1.5 top-1.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-danger-500 text-[9px] font-bold text-white leading-none">
                  {unreadCount > 9 ? "9+" : unreadCount}
                </span>
              )}
            </button>
          </DropdownMenu.Trigger>

          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="end"
              sideOffset={8}
              className="z-50 w-80 overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-xl shadow-neutral-900/10"
            >
              <div className="flex items-center justify-between border-b border-neutral-100 px-4 py-3">
                <span className="text-sm font-semibold text-neutral-900">
                  Notifications
                </span>
                {unreadCount > 0 && (
                  <button
                    onClick={markAllRead}
                    className="text-xs font-medium text-primary-600 hover:text-primary-700"
                  >
                    Mark all read
                  </button>
                )}
              </div>

              <div className="max-h-80 overflow-y-auto scrollbar-thin">
                {notifications.length === 0 ? (
                  <div className="px-4 py-10 text-center text-sm text-neutral-400">
                    You&apos;re all caught up
                  </div>
                ) : (
                  notifications.slice(0, 10).map((n) => (
                    <div
                      key={n.id}
                      className={cn(
                        "flex items-start gap-3 border-b border-neutral-50 px-4 py-3 last:border-0",
                        !n.read && "bg-primary-50/60"
                      )}
                    >
                      <div
                        className={cn(
                          "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
                          n.type === "success" && "bg-success-500",
                          n.type === "error" && "bg-danger-500",
                          n.type === "warning" && "bg-warning-500",
                          n.type === "info" && "bg-primary-500"
                        )}
                      />
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-semibold text-neutral-800">
                          {n.title}
                        </p>
                        <p className="mt-0.5 text-xs text-neutral-500">
                          {n.message}
                        </p>
                        <p className="mt-1 text-[11px] text-neutral-400">
                          {formatRelativeTime(n.created_at)}
                        </p>
                      </div>
                      <button
                        onClick={() => dismiss(n.id)}
                        className="shrink-0 text-neutral-300 hover:text-neutral-500 transition-colors"
                      >
                        ×
                      </button>
                    </div>
                  ))
                )}
              </div>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>

        {/* User dropdown */}
        {user && (
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <button className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm font-medium text-neutral-700 hover:bg-neutral-100 transition-colors">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-primary-500 to-primary-700 text-[11px] font-bold text-white shadow-sm">
                  {getInitials(user.first_name, user.last_name)}
                </div>
                <span className="hidden sm:inline text-sm font-medium text-neutral-800">
                  {user.first_name}
                </span>
                <ChevronDown className="h-3.5 w-3.5 text-neutral-400" />
              </button>
            </DropdownMenu.Trigger>

            <DropdownMenu.Portal>
              <DropdownMenu.Content
                align="end"
                sideOffset={8}
                className="z-50 w-52 overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-xl shadow-neutral-900/10"
              >
                <div className="border-b border-neutral-100 px-4 py-3">
                  <p className="text-sm font-semibold text-neutral-900">
                    {user.first_name} {user.last_name}
                  </p>
                  <p className="text-xs text-neutral-500 mt-0.5">{user.email}</p>
                </div>

                <div className="py-1">
                  <DropdownMenu.Item asChild>
                    <Link
                      href="/dashboard/settings"
                      className="flex items-center gap-2.5 px-4 py-2 text-sm text-neutral-700 outline-none hover:bg-neutral-50 cursor-pointer transition-colors"
                    >
                      <User className="h-4 w-4 text-neutral-400" />
                      Profile
                    </Link>
                  </DropdownMenu.Item>

                  <DropdownMenu.Item asChild>
                    <Link
                      href="/dashboard/settings"
                      className="flex items-center gap-2.5 px-4 py-2 text-sm text-neutral-700 outline-none hover:bg-neutral-50 cursor-pointer transition-colors"
                    >
                      <Settings className="h-4 w-4 text-neutral-400" />
                      Settings
                    </Link>
                  </DropdownMenu.Item>
                </div>

                <DropdownMenu.Separator className="h-px bg-neutral-100" />

                <div className="py-1">
                  <DropdownMenu.Item
                    onSelect={logout}
                    className="flex items-center gap-2.5 px-4 py-2 text-sm text-danger-600 outline-none hover:bg-danger-50 cursor-pointer transition-colors"
                  >
                    <LogOut className="h-4 w-4" />
                    Sign out
                  </DropdownMenu.Item>
                </div>
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        )}
      </div>
    </header>
  );
}
