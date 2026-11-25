"use client";

/* Small shared chrome for the console's record pages (Payroll,
 * Directory, Departments, Analytics, Hire) — the same header, card
 * and pill language the Agents and Profile pages already use, kept in
 * one place so the new pages read as one product. */

import type { ReactNode } from "react";
import type { AgentStatus } from "../lib/floorData";

export function PageHeader({
  title,
  sub,
  children,
}: {
  title: string;
  sub: string;
  children?: ReactNode;
}) {
  return (
    <header className="flex items-start justify-between gap-4 border-b border-border px-6 py-4">
      <div>
        <h1 className="font-display text-2xl">{title}</h1>
        <p className="mt-0.5 max-w-3xl text-sm text-muted-foreground">{sub}</p>
      </div>
      {children}
    </header>
  );
}

export function PageBody({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto bg-background text-foreground">
      {children}
    </div>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-border bg-card p-5 ${className}`}>{children}</section>
  );
}

export function StatusPill({ status }: { status: AgentStatus }) {
  if (status === "fired")
    return (
      <span className="rounded-full bg-red-500/15 px-2 py-0.5 text-2xs font-semibold text-red-500">
        Fired
      </span>
    );
  if (status === "on-notice")
    return (
      <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-2xs font-semibold text-amber-500">
        On notice
      </span>
    );
  return (
    <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-2xs font-semibold text-emerald-500">
      Active
    </span>
  );
}

export function CustomPill() {
  return (
    <span className="rounded-full bg-violet-500/15 px-2 py-0.5 text-2xs font-semibold text-violet-500">
      Custom
    </span>
  );
}

export function GenPill({ generation }: { generation: number }) {
  if (generation <= 1) return null;
  return (
    <span className="rounded-full bg-sky-500/15 px-2 py-0.5 text-2xs font-semibold text-sky-500">
      Gen {generation}
    </span>
  );
}

export function ApiDown({ what }: { what: string }) {
  return (
    <main className="mx-auto max-w-6xl px-6 py-6">
      <Card>
        <p className="text-sm text-muted-foreground">
          The floor API is not answering, so {what} has nothing to show yet. Start the API and this
          page fills in from the live ledger, roster and event stream — it never invents numbers.
        </p>
      </Card>
    </main>
  );
}

export function Loading() {
  return (
    <main className="mx-auto max-w-6xl px-6 py-6">
      <p className="text-sm text-muted-foreground">Loading the floor's records…</p>
    </main>
  );
}
