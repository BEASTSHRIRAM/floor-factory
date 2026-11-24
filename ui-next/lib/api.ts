import type { Agent, Bid, FloorEvent, Job, LedgerRow } from "./types";

/* Shape-tolerant helpers — ported from the vanilla UI (ui/app.js).
   Unknown shapes normalise to empty values, never throw. */

export const API_BASE =
  process.env.NEXT_PUBLIC_FLOOR_API?.replace(/\/$/, "") || "http://localhost:8000";

export function pick(obj: Record<string, unknown> | null | undefined, ...names: string[]): unknown {
  if (!obj) return undefined;
  for (const n of names) {
    const v = obj[n];
    if (v !== undefined && v !== null) return v;
  }
  return undefined;
}

export function asArray(x: unknown, keys: string[]): unknown[] {
  if (Array.isArray(x)) return x;
  if (x && typeof x === "object") {
    const o = x as Record<string, unknown>;
    for (const k of keys) if (Array.isArray(o[k])) return o[k] as unknown[];
  }
  return [];
}

export function credits(n: unknown): string {
  const v = Number(n);
  if (!Number.isFinite(v)) return "₡0";
  return (v < 0 ? "−₡" : "₡") + Math.abs(v).toLocaleString("en-IN");
}

export function signedCredits(n: unknown): string {
  const v = Number(n);
  if (!Number.isFinite(v) || v === 0) return "₡0";
  return (v > 0 ? "+₡" : "−₡") + Math.abs(v).toLocaleString("en-IN");
}

function num(v: unknown, fallback = 0): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

export function normalizeAgent(raw: unknown): Agent {
  const a = (raw ?? {}) as Record<string, unknown>;
  const rep = Math.max(0, Math.min(100, num(pick(a, "reputation", "rep"))));
  return {
    ...a,
    id: String(pick(a, "id", "agent_id", "name") ?? ""),
    name: String(pick(a, "name") ?? "Agent"),
    status: String(pick(a, "status") ?? "idle"),
    reputation: rep,
    balance_credits: num(pick(a, "balance", "balance_credits", "credits")),
    generation: num(pick(a, "generation", "gen"), 1),
    tier: String(pick(a, "tier") ?? ""),
    model: (pick(a, "model") as string) ?? undefined,
    role: (pick(a, "role", "kind", "type") as string) ?? undefined,
    mutation_note: (pick(a, "mutation_note", "mutation") as string) ?? undefined,
    current_job: (pick(a, "current_job", "current_job_title", "job_title") as string) ?? undefined,
    last_tool: (pick(a, "last_tool", "last_tool_call", "current_tool") as string) ?? undefined,
    fired_at: (pick(a, "fired_at") as string) ?? null,
  };
}

export function isFired(a: Agent): boolean {
  const s = a.status.toLowerCase();
  return s === "fired" || s === "terminated" || !!a.fired_at;
}

export function isManagement(a: Agent): boolean {
  const role = String(a.role ?? "").toLowerCase();
  const tier = a.tier.toLowerCase();
  return /manager|review|reviewer|cfo/.test(role) || /manager|reviewer|cfo/.test(tier);
}

export function normalizeJob(raw: unknown): Job {
  const j = (raw ?? {}) as Record<string, unknown>;
  const bids = Array.isArray(j.bids) ? (j.bids as Bid[]) : [];
  // The snapshot carries no explicit winner; the winning work order's
  // agent_id joined to that agent's bid yields the winner's name.
  let winner = pick(j, "winner", "awarded_to", "assigned_to", "agent_name") as string | undefined;
  if (!winner && Array.isArray(j.work_orders)) {
    const orders = j.work_orders as Record<string, unknown>[];
    const wo =
      orders.find((o) => ["accepted", "appeal_accepted"].includes(String(o.status ?? ""))) ?? orders[0];
    const bid = wo
      ? bids.find((b) => String((b as Record<string, unknown>).agent_id) === String(wo.agent_id))
      : undefined;
    if (bid) winner = (bid as Record<string, unknown>).agent_name as string;
  }
  return {
    ...j,
    id: String(pick(j, "id", "job_id") ?? ""),
    title: String(pick(j, "title", "name") ?? "Job"),
    status: String(pick(j, "status") ?? "open"),
    budget_credits: (() => {
      const b = pick(j, "budget_credits", "budget", "budget_cap", "cap");
      return b === undefined ? undefined : num(b);
    })(),
    system: (pick(j, "system", "target_system", "target", "system_id") as string) ?? undefined,
    winner: winner ?? undefined,
    severity: (pick(j, "severity") as string) ?? undefined,
    bids,
  };
}

export type JobColumn = "open" | "bidding" | "progress" | "review" | "done";

export function jobColumn(j: Job): JobColumn {
  const s = j.status.toLowerCase();
  if (["draft", "open", "posted", "new"].includes(s)) return "open";
  if (["bidding", "auction"].includes(s)) return "bidding";
  if (["awarded", "executing", "working", "in_progress", "assigned"].includes(s)) return "progress";
  if (["in_review", "review", "appealed", "appeal", "submitted"].includes(s)) return "review";
  return "done";
}

export function payloadOf(ev: FloorEvent): Record<string, unknown> {
  if (ev.payload && typeof ev.payload === "object") return ev.payload;
  if (ev.data && typeof ev.data === "object") return ev.data;
  return ev as Record<string, unknown>;
}

export function eventText(ev: FloorEvent, p: Record<string, unknown>): string {
  return (
    (pick(p, "message", "text", "narration") as string) ||
    (pick(ev as unknown as Record<string, unknown>, "message", "text", "narration") as string) ||
    ""
  );
}

export async function fetchJSON(path: string): Promise<unknown> {
  const r = await fetch(`${API_BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function postJSON(path: string): Promise<unknown> {
  const r = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json().catch(() => ({}));
}

export function normalizeLedger(raw: unknown): LedgerRow {
  return (raw ?? {}) as LedgerRow;
}
