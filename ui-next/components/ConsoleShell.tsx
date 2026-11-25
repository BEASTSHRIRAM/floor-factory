"use client";

/* Console shell: the shared chrome for every /console route — a slim
 * left rail (floor mark + Foreman, section nav, operator chip +
 * logout at the bottom) and the session guard. Without a local
 * session (lib/session.ts) every console route redirects to /login;
 * children render only once the session is known, so the board never
 * flashes (or falls into its recorded replay) behind the guard.
 *
 * The rail collapses to an icon-only strip (app-shell skill: mark
 * alone when collapsed, labels kept as screen-reader text + title
 * tooltips, group chrome hidden rather than shrunk). The choice
 * persists in localStorage and wins over the narrow-viewport
 * default; it also syncs across open tabs via the storage event. */

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  Bot,
  Building2,
  ChartColumn,
  ChevronsLeft,
  ChevronsRight,
  ContactRound,
  Factory,
  LogOut,
  Plug,
  UserPlus,
  CircleUserRound,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import Mascot from "./Mascot";
import {
  clearSession,
  getSession,
  operatorInitial,
  type FloorSession,
} from "../lib/session";

const SIDEBAR_KEY = "floor_sidebar_collapsed";

const NAV: {
  href: string;
  label: string;
  icon: LucideIcon;
  match: (p: string) => boolean;
}[] = [
  { href: "/console", label: "Floor", icon: Factory, match: (p) => p === "/console" },
  {
    href: "/console/connections",
    label: "Connections",
    icon: Plug,
    match: (p) => p.startsWith("/console/connections"),
  },
  {
    href: "/console/agents",
    label: "Agents",
    icon: Bot,
    match: (p) => p.startsWith("/console/agents"),
  },
  {
    href: "/console/directory",
    label: "Directory",
    icon: ContactRound,
    match: (p) => p.startsWith("/console/directory"),
  },
  {
    href: "/console/departments",
    label: "Departments",
    icon: Building2,
    match: (p) => p.startsWith("/console/departments"),
  },
  {
    href: "/console/payroll",
    label: "Payroll",
    icon: Wallet,
    match: (p) => p.startsWith("/console/payroll"),
  },
  {
    href: "/console/analytics",
    label: "Analytics",
    icon: ChartColumn,
    match: (p) => p.startsWith("/console/analytics"),
  },
  {
    href: "/console/hire",
    label: "Hire",
    icon: UserPlus,
    match: (p) => p.startsWith("/console/hire"),
  },
  {
    href: "/console/profile",
    label: "Profile",
    icon: CircleUserRound,
    match: (p) => p.startsWith("/console/profile"),
  },
];

export default function ConsoleShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname() || "/console";
  const [session, setSessionState] = useState<FloorSession | null>(null);
  const [checked, setChecked] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const s = getSession();
    setSessionState(s);
    // Stored choice wins; with no stored choice, start collapsed
    // only on narrow viewports (app-shell skill).
    const stored = window.localStorage.getItem(SIDEBAR_KEY);
    if (stored !== null) setCollapsed(stored === "1");
    else if (window.innerWidth < 1024) setCollapsed(true);
    setChecked(true);
    if (!s) router.replace("/login");
  }, [router]);

  // Keep open tabs in step with each other's preference.
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === SIDEBAR_KEY) setCollapsed(e.newValue === "1");
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      window.localStorage.setItem(SIDEBAR_KEY, prev ? "0" : "1");
      return !prev;
    });
  };

  if (!checked || !session) {
    return (
      <div className="flex h-dvh w-full items-center justify-center bg-background text-sm text-muted-foreground">
        Opening your floor…
      </div>
    );
  }

  return (
    <div className="flex h-dvh w-full overflow-hidden bg-background font-sans text-foreground">
      <aside
        className={`flex shrink-0 flex-col border-r border-border bg-sidebar transition-[width] duration-200 ${
          collapsed ? "w-[60px]" : "w-[212px]"
        }`}
        aria-label="Console"
      >
        {/* The logo links home (app-shell skill: in a sidebar app the
            logo is the one way back to the front door — a link, not a
            picture). The workspace name is the tenant, stated as a
            label, never applied as a theme. Collapsed, the lockup
            reduces to the mascot mark alone. */}
        <a
          href="/console"
          className={`flex items-center gap-2.5 pb-2 pt-4 ${
            collapsed ? "justify-center px-0" : "px-4"
          }`}
          aria-label="THE FLOOR — back to the floor board"
          title="THE FLOOR"
        >
          <Mascot state="idle" size={30} label="" />
          {!collapsed && (
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold leading-tight text-foreground">
                THE FLOOR
              </span>
              <span className="block truncate text-2xs leading-tight text-muted-foreground">
                {session.workspace}
              </span>
            </span>
          )}
        </a>

        <nav className="mt-3 flex flex-col gap-0.5 px-2" aria-label="Sections">
          {NAV.map((item) => {
            const active = item.match(pathname);
            const Icon = item.icon;
            return (
              <a
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                title={collapsed ? item.label : undefined}
                className={`flex items-center rounded-lg text-sm transition-colors ${
                  collapsed ? "justify-center px-0 py-2" : "gap-2.5 px-2.5 py-2"
                } ${
                  active
                    ? "bg-interactive-hover font-medium text-foreground"
                    : "text-muted-foreground hover:bg-interactive-hover hover:text-foreground"
                }`}
              >
                <Icon size={18} className="shrink-0" aria-hidden="true" />
                {collapsed ? (
                  <span className="sr-only">{item.label}</span>
                ) : (
                  <span className="truncate">{item.label}</span>
                )}
              </a>
            );
          })}
        </nav>

        <div
          className={`mt-auto shrink-0 border-t border-border py-3 ${
            collapsed ? "px-2" : "px-3"
          }`}
        >
          <button
            type="button"
            onClick={toggleCollapsed}
            aria-expanded={!collapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={`flex items-center rounded-md px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-interactive-hover hover:text-foreground ${
              collapsed ? "w-full justify-center px-0" : "mb-2.5 w-full gap-2"
            }`}
          >
            {collapsed ? (
              <ChevronsRight size={16} aria-hidden="true" />
            ) : (
              <>
                <ChevronsLeft size={16} className="shrink-0" aria-hidden="true" />
                Collapse sidebar
              </>
            )}
          </button>
          <div
            className={`flex items-center gap-2.5 ${collapsed ? "justify-center" : ""}`}
            title={collapsed ? `${session.displayName} · ${session.email}` : undefined}
          >
            <span
              className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground"
              aria-hidden="true"
            >
              {operatorInitial(session)}
            </span>
            {!collapsed && (
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium leading-tight text-foreground">
                  {session.displayName}
                </span>
                <span className="block truncate text-2xs leading-tight text-muted-foreground">
                  {session.email}
                </span>
              </span>
            )}
          </div>
          {collapsed ? (
            <button
              type="button"
              onClick={() => {
                clearSession();
                router.replace("/login");
              }}
              aria-label="Log out"
              title="Log out"
              className="mt-2.5 flex w-full items-center justify-center rounded-md border border-border px-0 py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              <LogOut size={14} aria-hidden="true" />
            </button>
          ) : (
            <button
              type="button"
              onClick={() => {
                clearSession();
                router.replace("/login");
              }}
              className="mt-2.5 w-full rounded-md border border-border px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              Log out
            </button>
          )}
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">{children}</div>
    </div>
  );
}
