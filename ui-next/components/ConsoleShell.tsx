"use client";

/* Console shell: the shared chrome for every /console route — a slim
 * left rail (floor mark + Foreman, section nav, operator chip +
 * logout at the bottom) and the session guard. Without a local
 * session (lib/session.ts) every console route redirects to /login;
 * children render only once the session is known, so the board never
 * flashes (or falls into its recorded replay) behind the guard. */

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Mascot from "./Mascot";
import {
  clearSession,
  getSession,
  operatorInitial,
  type FloorSession,
} from "../lib/session";

const NAV: { href: string; label: string; match: (p: string) => boolean }[] = [
  { href: "/console", label: "Floor", match: (p) => p === "/console" },
  {
    href: "/console/connections",
    label: "Connections",
    match: (p) => p.startsWith("/console/connections"),
  },
  {
    href: "/console/agents",
    label: "Agents",
    match: (p) => p.startsWith("/console/agents"),
  },
  {
    href: "/console/directory",
    label: "Directory",
    match: (p) => p.startsWith("/console/directory"),
  },
  {
    href: "/console/departments",
    label: "Departments",
    match: (p) => p.startsWith("/console/departments"),
  },
  {
    href: "/console/payroll",
    label: "Payroll",
    match: (p) => p.startsWith("/console/payroll"),
  },
  {
    href: "/console/analytics",
    label: "Analytics",
    match: (p) => p.startsWith("/console/analytics"),
  },
  {
    href: "/console/hire",
    label: "Hire",
    match: (p) => p.startsWith("/console/hire"),
  },
  {
    href: "/console/profile",
    label: "Profile",
    match: (p) => p.startsWith("/console/profile"),
  },
];

export default function ConsoleShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname() || "/console";
  const [session, setSessionState] = useState<FloorSession | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const s = getSession();
    setSessionState(s);
    setChecked(true);
    if (!s) router.replace("/login");
  }, [router]);

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
        className="flex w-[212px] shrink-0 flex-col border-r border-border bg-sidebar"
        aria-label="Console"
      >
        {/* The logo links home (app-shell skill: in a sidebar app the
            logo is the one way back to the front door — a link, not a
            picture). The workspace name is the tenant, stated as a
            label, never applied as a theme. */}
        <a
          href="/console"
          className="flex items-center gap-2.5 px-4 pb-2 pt-4"
          aria-label="THE FLOOR — back to the floor board"
        >
          <Mascot state="idle" size={30} label="" />
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold leading-tight text-foreground">
              THE FLOOR
            </span>
            <span className="block truncate text-2xs leading-tight text-muted-foreground">
              {session.workspace}
            </span>
          </span>
        </a>

        <nav className="mt-3 flex flex-col gap-0.5 px-2" aria-label="Sections">
          {NAV.map((item) => {
            const active = item.match(pathname);
            return (
              <a
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`rounded-lg px-2.5 py-2 text-sm transition-colors ${
                  active
                    ? "bg-interactive-hover font-medium text-foreground"
                    : "text-muted-foreground hover:bg-interactive-hover hover:text-foreground"
                }`}
              >
                {item.label}
              </a>
            );
          })}
        </nav>

        <div className="mt-auto shrink-0 border-t border-border px-3 py-3">
          <div className="flex items-center gap-2.5">
            <span
              className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground"
              aria-hidden="true"
            >
              {operatorInitial(session)}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium leading-tight text-foreground">
                {session.displayName}
              </span>
              <span className="block truncate text-2xs leading-tight text-muted-foreground">
                {session.email}
              </span>
            </span>
          </div>
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
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">{children}</div>
    </div>
  );
}
