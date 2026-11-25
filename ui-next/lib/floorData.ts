/* Shared data layer for the console's record pages (Payroll,
 * Directory, Departments, Analytics, Hire, job Trace).
 *
 * Everything here reads the floor's real endpoints — /state/agents,
 * /state/jobs, /state/ledger, /state/events, /agents/{id}/harness,
 * /state/catalogue — and aggregates client-side. Nothing is invented:
 * where the API's shape differs from an assumption, the helpers below
 * normalise to empty values rather than fabricating rows. */

import { fetchJSON } from "./api";

/* ------------------------------------------------------------------ */
/* Raw shapes (as served by api/main.py)                               */
/* ------------------------------------------------------------------ */

export interface RawAgent {
  id: number;
  name: string;
  role: string;
  tier: string;
  model: string;
  status: string; // active | fired
  reputation: number;
  generation: number;
  parent_agent_id: number | null;
  mutation_note: string | null;
  balance_credits: number;
  fire_reason: string | null;
  price_factor: number;
  origin: string; // seeded | mutation | user-created
  department: string | null;
  family_key: string | null;
  base_salary_credits?: number;
  hired_cycle?: number;
  created_at?: string;
  fired_at?: string | null;
}

export interface RawLedgerRow {
  id: number;
  agent_id: number;
  agent_name: string;
  kind: string; // earning|review_fee|appeal_fee|running_cost|tool_cost|bonus|penalty
  amount_credits: number; // signed
  balance_after: number;
  ref_type: string | null;
  ref_id: number | null;
  cycle_no: number;
  note: string;
  created_at: string;
}

export interface RawEvent {
  seq: number;
  type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface RawBid {
  id: number;
  job_id: number;
  agent_id: number;
  agent_name: string;
  price_credits: number;
  confidence: number;
  rationale: string;
  created_at: string;
}

export interface RawWorkOrder {
  id: number;
  job_id: number;
  agent_id: number;
  agreed_price_credits: number;
  plan: string | null;
  status: string; // working|submitted|accepted|rejected|appeal_accepted|appeal_rejected
  cycle_no: number;
  started_at: string;
  finished_at: string | null;
}

export interface RawJob {
  id: number;
  title: string;
  brief: string;
  status: string;
  budget_credits: number;
  department: string;
  department_label: string;
  created_cycle: number;
  created_at: string;
  acceptance_criteria: string[];
  bids: RawBid[];
  work_orders: RawWorkOrder[];
}

export interface HarnessLite {
  agent: {
    id: number;
    name: string;
    status: string;
    generation: number;
    parent_agent_id: number | null;
    mutation_note: string | null;
    reputation: number;
  };
  harness: {
    department: string;
    role_label: string;
    charter_summary: string;
    model_tier: string;
    tools: Record<string, string[]>;
    tool_count: number;
  };
  lessons: { count: number; latest: unknown[] };
}

export interface CatalogueFamily {
  key: string;
  title: string;
  brief: string;
  budget_credits: number;
  acceptance_criteria: string[];
  server: string;
  tool_count: number;
}

export interface CatalogueDepartment {
  key: string;
  label: string;
  servers: string[];
  budget_min: number;
  budget_max: number;
  families: CatalogueFamily[];
}

export interface CatalogueWorkplace {
  server: string;
  label: string;
  department: string | null;
  tools: { name: string; effect: string; gated: boolean }[];
}

export interface Catalogue {
  departments: CatalogueDepartment[];
  workplaces: CatalogueWorkplace[];
}

/* ------------------------------------------------------------------ */
/* Fetchers                                                            */
/* ------------------------------------------------------------------ */

export async function fetchAgents(): Promise<RawAgent[]> {
  const d = (await fetchJSON("/state/agents")) as { agents: RawAgent[] };
  return d.agents ?? [];
}

export async function fetchJobs(): Promise<RawJob[]> {
  const d = (await fetchJSON("/state/jobs")) as { jobs: RawJob[] };
  return d.jobs ?? [];
}

/* The ledger endpoint caps at 1000 rows; the floor's whole history is
 * far below that today, and the payroll/analytics pages say so if the
 * cap is ever hit (rows.length === 1000 is detectable). */
export async function fetchLedger(): Promise<RawLedgerRow[]> {
  const d = (await fetchJSON("/state/ledger?limit=1000")) as { ledger: RawLedgerRow[] };
  return d.ledger ?? [];
}

/* /state/events is a window (after_seq + limit, max 2000); page through
 * it so the trace and the trend charts see the whole stream, not the
 * first window. */
export async function fetchAllEvents(maxPages = 12): Promise<RawEvent[]> {
  const out: RawEvent[] = [];
  let after = 0;
  for (let page = 0; page < maxPages; page++) {
    const d = (await fetchJSON(`/state/events?after_seq=${after}&limit=2000`)) as {
      events: RawEvent[];
    };
    const batch = d.events ?? [];
    if (batch.length === 0) break;
    out.push(...batch);
    after = batch[batch.length - 1].seq;
    if (batch.length < 2000) break;
  }
  return out;
}

export async function fetchHarnesses(agents: RawAgent[]): Promise<Record<number, HarnessLite>> {
  const map: Record<number, HarnessLite> = {};
  const rows = await Promise.all(
    agents.map(async (a) => {
      try {
        return [a.id, (await fetchJSON(`/agents/${a.id}/harness`)) as HarnessLite] as const;
      } catch {
        return null;
      }
    }),
  );
  for (const r of rows) if (r) map[r[0]] = r[1];
  return map;
}

export async function fetchCatalogue(): Promise<Catalogue> {
  return (await fetchJSON("/state/catalogue")) as Catalogue;
}

/* ------------------------------------------------------------------ */
/* Derivations (the same rules the Agents page already uses)           */
/* ------------------------------------------------------------------ */

export type AgentStatus = "active" | "on-notice" | "fired";

/* Latest payroll verdict per agent, from cycle.closed events in seq
 * order (later cycles overwrite earlier ones). */
export function latestVerdicts(events: RawEvent[]): Map<number, string> {
  const v = new Map<number, string>();
  for (const e of events) {
    if (e.type !== "cycle.closed") continue;
    const rows = (e.payload?.payroll ?? []) as { agent_id: number; verdict: string }[];
    for (const row of rows) v.set(row.agent_id, row.verdict);
  }
  return v;
}

export function statusOfAgent(a: RawAgent, verdicts: Map<number, string>): AgentStatus {
  if (a.status === "fired") return "fired";
  if (verdicts.get(a.id) === "ON-NOTICE") return "on-notice";
  return "active";
}

/* An agent's home department: the harness knows it (persona defs);
 * operator-created agents also carry it on the roster row. */
export function agentDepartment(a: RawAgent, harness?: HarnessLite): string {
  return harness?.harness.department ?? a.department ?? (a.role === "reviewer" ? "review" : "support");
}

export const DEPT_LABELS: Record<string, string> = {
  support: "Support",
  qa: "QA triage",
  bookkeeping: "Bookkeeping",
  sdr: "SDR",
  engineering: "Engineering",
  hr: "HR",
  seo: "SEO",
  review: "Review",
  management: "Management",
};

export function deptLabel(key: string): string {
  return DEPT_LABELS[key] ?? key;
}

/* Ledger kinds, grouped the way payroll talks about them. */
export const EARN_KINDS = ["earning", "review_fee", "bonus"];
export const COST_KINDS = ["running_cost", "tool_cost"];
export const FINE_KINDS = ["penalty", "appeal_fee"];

export const KIND_LABELS: Record<string, string> = {
  earning: "Job earnings",
  review_fee: "Review fee",
  bonus: "Bonus",
  running_cost: "Running cost",
  tool_cost: "Tool cost",
  penalty: "Penalty",
  appeal_fee: "Appeal fee",
};

export function sumKinds(rows: RawLedgerRow[], kinds: string[]): number {
  return rows.filter((r) => kinds.includes(r.kind)).reduce((s, r) => s + r.amount_credits, 0);
}

/* Money an agent was paid for work (positive inflows from working and
 * reviewing — the "total earned" a directory entry shows). */
export function earnedOf(rows: RawLedgerRow[]): number {
  return sumKinds(rows, EARN_KINDS);
}

export function groupBy<T, K extends string | number>(rows: T[], key: (r: T) => K): Map<K, T[]> {
  const m = new Map<K, T[]>();
  for (const r of rows) {
    const k = key(r);
    const arr = m.get(k);
    if (arr) arr.push(r);
    else m.set(k, [r]);
  }
  return m;
}

export function clockTime(iso: string): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "";
  return new Date(t).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function dayTime(iso: string): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "";
  return new Date(t).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}
