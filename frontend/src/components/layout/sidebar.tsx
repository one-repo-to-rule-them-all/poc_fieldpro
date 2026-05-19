"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  ClipboardList,
  Users,
  MapPin,
  HardHat,
  Calendar,
  FileText,
  BarChart3,
  Settings,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Menu,
  ScanLine,
} from "lucide-react";
import { cn, getInitials } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { useSidebar } from "@/stores/ui-store";

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
  roles?: string[];
  testid: string;
}

const NAV_ITEMS: NavItem[] = [
  {
    label: "Dashboard",
    href: "/dashboard",
    icon: LayoutDashboard,
    roles: ["platform_owner", "tenant_admin", "manager"],
    testid: "nav-dashboard",
  },
  { label: "Work Orders", href: "/dashboard/work-orders", icon: ClipboardList, testid: "nav-work-orders" },
  { label: "Check In", href: "/dashboard/check-in", icon: ScanLine, roles: ["employee"], testid: "nav-check-in" },
  { label: "Schedule", href: "/dashboard/schedule", icon: Calendar, testid: "nav-schedule" },
  {
    label: "Clients",
    href: "/dashboard/clients",
    icon: Users,
    roles: ["platform_owner", "tenant_admin", "manager"],
    testid: "nav-clients",
  },
  {
    label: "Locations",
    href: "/dashboard/locations",
    icon: MapPin,
    roles: ["platform_owner", "tenant_admin", "manager"],
    testid: "nav-locations",
  },
  {
    label: "Crews",
    href: "/dashboard/crews",
    icon: HardHat,
    roles: ["platform_owner", "tenant_admin", "manager"],
    testid: "nav-crews",
  },
  {
    label: "Invoices",
    href: "/dashboard/invoices",
    icon: FileText,
    roles: ["platform_owner", "tenant_admin", "manager"],
    testid: "nav-invoices",
  },
  {
    label: "Analytics",
    href: "/dashboard/analytics",
    icon: BarChart3,
    roles: ["platform_owner", "tenant_admin", "manager"],
    testid: "nav-analytics",
  },
  {
    label: "Settings",
    href: "/dashboard/settings",
    icon: Settings,
    roles: ["platform_owner", "tenant_admin"],
    testid: "nav-settings",
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, tenant, logout, hasRole } = useAuth();
  const { isCollapsed, toggle } = useSidebar();

  const visibleItems = NAV_ITEMS.filter((item) => {
    if (!item.roles) return true;
    return item.roles.some((role) =>
      hasRole(role as Parameters<typeof hasRole>[0])
    );
  });

  return (
    <>
      {/* Desktop Sidebar */}
      <aside
        className={cn(
          "hidden lg:flex flex-col h-screen sticky top-0 bg-neutral-900 transition-all duration-300 shrink-0",
          isCollapsed ? "w-[68px]" : "w-[220px]"
        )}
      >
        {/* Logo + Tenant */}
        <div className="flex h-16 items-center justify-between border-b border-white/[0.06] px-3">
          {!isCollapsed && (
            <div className="flex items-center gap-2.5 overflow-hidden">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary-600 shadow-md shadow-primary-900/40">
                <span className="text-sm font-bold text-white">F</span>
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-bold text-white leading-tight">
                  FieldPro
                </p>
                {tenant && (
                  <p className="truncate text-[11px] text-neutral-400 leading-tight">
                    {tenant.name}
                  </p>
                )}
              </div>
            </div>
          )}
          {isCollapsed && (
            <div className="flex w-full justify-center">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-600">
                <span className="text-sm font-bold text-white">F</span>
              </div>
            </div>
          )}
          {!isCollapsed && (
            <button
              onClick={toggle}
              className="rounded-md p-1 text-neutral-500 hover:bg-white/[0.06] hover:text-neutral-300 transition-colors"
              aria-label="Collapse sidebar"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          )}
        </div>

        {isCollapsed && (
          <button
            onClick={toggle}
            className="flex w-full justify-center py-3 text-neutral-500 hover:text-neutral-300 transition-colors"
            aria-label="Expand sidebar"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        )}

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-3 scrollbar-thin">
          <ul className="space-y-0.5 px-2">
            {visibleItems.map((item) => {
              const Icon = item.icon;
              const isActive =
                item.href === "/dashboard"
                  ? pathname === "/dashboard"
                  : pathname.startsWith(item.href);

              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    data-testid={item.testid}
                    title={isCollapsed ? item.label : undefined}
                    className={cn(
                      "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-all duration-150",
                      isActive
                        ? "bg-white/[0.1] text-white"
                        : "text-neutral-400 hover:bg-white/[0.05] hover:text-neutral-200",
                      isCollapsed && "justify-center px-0 py-2.5"
                    )}
                  >
                    <Icon
                      className={cn(
                        "h-4 w-4 shrink-0",
                        isActive ? "text-primary-400" : "text-neutral-500"
                      )}
                    />
                    {!isCollapsed && (
                      <>
                        <span className="flex-1">{item.label}</span>
                        {isActive && (
                          <span className="h-1.5 w-1.5 rounded-full bg-primary-400 shrink-0" />
                        )}
                      </>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* User section */}
        <div className="border-t border-white/[0.06] p-2">
          {!isCollapsed && user ? (
            <div className="flex items-center gap-2.5 rounded-lg p-2 hover:bg-white/[0.05] transition-colors group">
              <Link
                href="/dashboard/profile"
                className="flex min-w-0 flex-1 items-center gap-2.5"
              >
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-500/20 text-[11px] font-semibold text-primary-400">
                  {getInitials(user.first_name, user.last_name)}
                </div>
                <div className="min-w-0">
                  <p className="truncate text-xs font-medium text-neutral-200">
                    {user.first_name} {user.last_name}
                  </p>
                  <p className="truncate text-[10px] text-neutral-500">
                    {user.email}
                  </p>
                </div>
              </Link>
              <button
                onClick={logout}
                className="shrink-0 rounded-md p-1 text-neutral-600 hover:bg-white/[0.1] hover:text-neutral-300 transition-colors opacity-0 group-hover:opacity-100"
                aria-label="Sign out"
                title="Sign out"
              >
                <LogOut className="h-3.5 w-3.5" />
              </button>
            </div>
          ) : (
            <button
              onClick={logout}
              className="flex w-full justify-center rounded-lg p-2.5 text-neutral-500 hover:bg-white/[0.06] hover:text-neutral-300 transition-colors"
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOut className="h-4 w-4" />
            </button>
          )}
        </div>
      </aside>

      {/* Mobile bottom tab bar */}
      <nav className="fixed inset-x-0 bottom-0 z-40 flex h-16 items-center justify-around border-t border-neutral-200 bg-white lg:hidden">
        {[
          { label: "Orders", href: "/dashboard/work-orders", icon: ClipboardList },
          { label: "Schedule", href: "/dashboard/schedule", icon: Calendar },
          { label: "Crews", href: "/dashboard/crews", icon: HardHat },
          {
            label: "Dashboard",
            href: "/dashboard",
            icon: LayoutDashboard,
            adminOnly: true,
          },
          { label: "More", href: "/dashboard/settings", icon: Settings },
        ]
          .filter((item) => {
            if (!("adminOnly" in item) || !item.adminOnly) return true;
            return hasRole("manager");
          })
          .map((item) => {
            const Icon = item.icon;
            const isActive =
              item.href === "/dashboard"
                ? pathname === "/dashboard"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex flex-col items-center gap-0.5 px-3 py-2 text-xs font-medium",
                  isActive ? "text-primary-600" : "text-neutral-500"
                )}
              >
                <Icon
                  className={cn(
                    "h-5 w-5",
                    isActive ? "text-primary-600" : "text-neutral-400"
                  )}
                />
                {item.label}
              </Link>
            );
          })}
      </nav>
    </>
  );
}

export function MobileSidebarButton() {
  const { toggle } = useSidebar();
  return (
    <button
      onClick={toggle}
      className="rounded-lg p-2 text-neutral-600 hover:bg-neutral-100 lg:hidden"
      aria-label="Open menu"
    >
      <Menu className="h-5 w-5" />
    </button>
  );
}
