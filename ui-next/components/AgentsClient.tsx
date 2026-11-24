"use client";

/* Agents — the roster as profiles. Everything on this page comes
 * from the real API: GET /state/agents for the roster, GET
 * /agents/{id}/harness for each agent's composed harness (charter,
 * tool allowlist, playbooks, lineage lessons), and the latest
 * cycle.closed event for payroll verdicts (ON-NOTICE). Nothing is
 * invented: an agent with no lessons shows none. */

import { useCallback, useEffect, useMemo, useState } from "react";
import { API_BASE, credits } from "../lib/api";

type AgentRow = {
  id: number;
  name: string;
  role: string;
  tier: string;
  model: string;
  status: string;
  reputation: number;
  generation: number;
  parent_agent_id: number | null;
  mutation_note: string | null;
  balance_credits: number;
  fire_reason: string | null;
};

type Lesson = {
  lesson: string;
  source: string;
  cycle_no: number | null;
  caught_by: string | null;
  family_key: string | null;
  created_at: string;
  agent_name: string;
};

type HarnessData = {
  agent: { id: number; name: string; status: string; generation: number; parent_agent_id: number | null; mutation_note: string | null; reputation: number };
  harness: {
    department: string;
    role_label: string;
    charter: string;
    charter_summary: string;
    hard_rules: string[];
    model_tier: string;
    tools: Record<string, string[]>;
    tool_count: number;
    write_tools: string[];
    playbooks: Record<string, string>;
  };
  lessons: { count: number; latest: Lesson[] };
};

const DEPT_LABELS: Record<string, string> = {
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

async function fetchJSON(path: string): Promise<unknown> {
  const r = await fetch(`${API_BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

type AgentStatus = "active" | "on-notice" | "fired";

/* Stored mutation notes already carry a "mutation:" prefix in the
 * economy's wording; strip it where the UI adds its own label. */
function mutationText(note: string | null | undefined): string {
  return (note ?? "").replace(/^mutation:\s*/i, "");
}

function StatusPill({ status }: { status: AgentStatus }) {
  if (status === "fired") {
    return (
      <span className="rounded-full bg-red-500/15 px-2 py-0.5 text-2xs font-semibold text-red-500">
        Fired
      </span>
    );
  }
  if (status === "on-notice") {
    return (
      <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-2xs font-semibold text-amber-500">
        On notice
      </span>
    );
  }
  return (
    <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-2xs font-semibold text-emerald-500">
      Active
    </span>
  );
}

export default function AgentsClient() {
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [harnesses, setHarnesses] = useState<Record<number, HarnessData>>({});
  const [verdicts, setVerdicts] = useState<Record<number, string>>({});
  const [selected, setSelected] = useState<number | null>(null);
  const [apiUp, setApiUp] = useState(true);
  const [loaded, setLoaded] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const d = (await fetchJSON("/state/agents")) as { agents: AgentRow[] };
      const roster = d.agents ?? [];
      setAgents(roster);
      const hs = await Promise.all(
        roster.map(async (a) => {
          try {
            return [a.id, (await fetchJSON(`/agents/${a.id}/harness`)) as HarnessData] as const;
          } catch {
            return null;
          }
        }),
      );
      const map: Record<number, HarnessData> = {};
      for (const h of hs) if (h) map[h[0]] = h[1];
      setHarnesses(map);
      try {
        const ev = (await fetchJSON("/state/events?after_seq=0&limit=2000")) as {
          events: { type: string; payload: Record<string, unknown> }[];
        };
        const v: Record<number, string> = {};
        for (const e of ev.events ?? []) {
          if (e.type !== "cycle.closed") continue;
          const rows = (e.payload?.payroll ?? []) as { agent_id: number; verdict: string }[];
          // Events arrive in seq order; later cycles overwrite earlier
          // verdicts, leaving each agent's LATEST payroll verdict.
          for (const row of rows) v[row.agent_id] = row.verdict;
        }
        setVerdicts(v);
      } catch {
        setVerdicts({});
      }
      setApiUp(true);
    } catch {
      setApiUp(false);
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (selected === null && agents.length > 0) setSelected(agents[0].id);
  }, [agents, selected]);

  const byId = useMemo(() => new Map(agents.map((a) => [a.id, a])), [agents]);
  const childOf = useMemo(() => {
    const m = new Map<number, AgentRow>();
    for (const a of agents) if (a.parent_agent_id) m.set(a.parent_agent_id, a);
    return m;
  }, [agents]);

  const statusOf = (a: AgentRow): AgentStatus => {
    if (a.status === "fired") return "fired";
    if (verdicts[a.id] === "ON-NOTICE") return "on-notice";
    return "active";
  };

  const sel = selected !== null ? byId.get(selected) ?? null : null;
  const selH = sel ? harnesses[sel.id] : undefined;

  return (
    <div className="min-h-0 flex-1 overflow-y-auto bg-background text-foreground">
      <header className="border-b border-border px-6 py-4">
        <h1 className="font-display text-2xl">Agents</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Everyone on the roster — their harness, their record, and what they have learned.
        </p>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-6">
        {!apiUp && (
          <div className="rounded-lg border border-destructive/40 bg-popover px-4 py-3 text-sm text-destructive">
            The floor API is not reachable at {API_BASE}. The roster needs the API server running.
          </div>
        )}
        {loaded && apiUp && agents.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No agents on the roster yet — reset the floor or run a shift from the Floor page.
          </p>
        )}

        <div className="grid gap-4 lg:grid-cols-[minmax(280px,380px)_1fr]">
          {/* Roster cards */}
          <div className="space-y-2">
            {agents.map((a) => {
              const h = harnesses[a.id];
              const st = statusOf(a);
              const child = childOf.get(a.id);
              const active = selected === a.id;
              return (
                <button
                  key={a.id}
                  type="button"
                  onClick={() => setSelected(a.id)}
                  aria-current={active || undefined}
                  className={`w-full rounded-xl border p-4 text-left transition-colors ${
                    active ? "border-primary bg-card" : "border-border bg-card hover:border-muted-foreground"
                  } ${st === "fired" ? "opacity-70" : ""}`}
                >
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">{a.name}</span>
                    <StatusPill status={st} />
                    {a.generation > 1 && (
                      <span className="rounded-full bg-sky-500/15 px-2 py-0.5 text-2xs font-semibold text-sky-500">
                        Gen {a.generation}
                      </span>
                    )}
                    <span className="ml-auto font-mono text-sm tabular-nums">
                      {Math.round(a.reputation)}
                    </span>
                  </div>
                  <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-2xs text-muted-foreground">
                    <span>
                      {h ? DEPT_LABELS[h.harness.department] ?? h.harness.department : a.role}
                      {" · "}
                      {h?.harness.role_label ?? a.role}
                    </span>
                    <span>reputation {Math.round(a.reputation)}/100</span>
                    <span>balance {credits(a.balance_credits)}</span>
                    <span>
                      {h ? `${h.lessons.count} lesson${h.lessons.count === 1 ? "" : "s"}` : "… lessons"}
                    </span>
                  </div>
                  {child && (
                    <p className="mt-1.5 text-2xs text-muted-foreground">
                      Replaced by {child.name}
                      {child.mutation_note ? ` — mutation: ${mutationText(child.mutation_note)}` : ""}
                    </p>
                  )}
                </button>
              );
            })}
          </div>

          {/* Profile panel */}
          <div>
            {sel && selH ? (
              <section className="space-y-5 rounded-xl border border-border bg-card p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-xl font-semibold">{sel.name}</h2>
                  <StatusPill status={statusOf(sel)} />
                  <span className="text-sm text-muted-foreground">
                    {DEPT_LABELS[selH.harness.department] ?? selH.harness.department} ·{" "}
                    {selH.harness.role_label} · {selH.harness.model_tier} tier · {sel.model}
                  </span>
                </div>

                {sel.parent_agent_id && (
                  <p className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-muted-foreground">
                    Generation {sel.generation} — mutated replacement of{" "}
                    {byId.get(sel.parent_agent_id)?.name ?? `agent #${sel.parent_agent_id}`}
                    {sel.mutation_note ? (
                      <>
                        . Mutation: <span className="text-foreground">{mutationText(sel.mutation_note)}</span>
                      </>
                    ) : (
                      "."
                    )}{" "}
                    It inherits its lineage&apos;s lessons below.
                  </p>
                )}
                {sel.status === "fired" && sel.fire_reason && (
                  <p className="rounded-lg border border-destructive/40 bg-background px-3 py-2 text-sm text-destructive">
                    PinkSlip: {sel.fire_reason}
                  </p>
                )}

                <div>
                  <h3 className="mb-1 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                    Charter
                  </h3>
                  <p className="text-sm leading-relaxed">{selH.harness.charter_summary}</p>
                  {selH.harness.hard_rules.length > 0 && (
                    <ul className="mt-2 list-inside list-disc space-y-0.5 text-sm text-muted-foreground">
                      {selH.harness.hard_rules.map((r) => (
                        <li key={r}>{r}</li>
                      ))}
                    </ul>
                  )}
                </div>

                <div>
                  <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                    Tool allowlist — {selH.harness.tool_count} tools
                    {selH.harness.write_tools.length > 0
                      ? `, ${selH.harness.write_tools.length} gated writes`
                      : ", read-only"}
                  </h3>
                  <div className="space-y-1.5">
                    {Object.entries(selH.harness.tools).map(([server, names]) => (
                      <div key={server} className="flex flex-wrap items-baseline gap-1.5 text-sm">
                        <span className="font-mono text-xs text-muted-foreground">{server}:</span>
                        {names.map((n) => (
                          <code
                            key={n}
                            className={`rounded px-1.5 py-0.5 font-mono text-2xs ${
                              selH.harness.write_tools.includes(`${server}:${n}`)
                                ? "bg-amber-500/15 text-amber-500"
                                : "bg-sky-500/10 text-sky-500"
                            }`}
                          >
                            {n}
                          </code>
                        ))}
                      </div>
                    ))}
                    {selH.harness.tool_count === 0 && (
                      <p className="text-sm text-muted-foreground">No tools in this harness.</p>
                    )}
                  </div>
                </div>

                <div>
                  <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                    Playbooks
                  </h3>
                  <div className="space-y-1.5">
                    {Object.entries(selH.harness.playbooks).map(([fam, text]) => (
                      <p key={fam} className="text-sm">
                        <span className="font-mono text-xs text-muted-foreground">{fam}: </span>
                        {String(text).split("\n")[0]}
                      </p>
                    ))}
                    {Object.keys(selH.harness.playbooks).length === 0 && (
                      <p className="text-sm text-muted-foreground">No playbooks for this harness.</p>
                    )}
                  </div>
                </div>

                <div>
                  <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                    Lessons — {selH.lessons.count} held by this lineage
                  </h3>
                  <div className="space-y-2">
                    {selH.lessons.latest.map((l, i) => (
                      <div key={i} className="rounded-lg border border-border bg-background p-3 text-sm">
                        <p className="leading-relaxed">{l.lesson}</p>
                        <p className="mt-1 text-2xs text-muted-foreground">
                          {l.source}
                          {l.cycle_no != null ? ` · cycle ${l.cycle_no}` : ""}
                          {l.caught_by ? ` · caught by ${l.caught_by}` : ""}
                          {l.agent_name !== sel.name ? ` · learned by ${l.agent_name}` : ""}
                        </p>
                      </div>
                    ))}
                    {selH.lessons.count === 0 && (
                      <p className="text-sm text-muted-foreground">
                        No lessons yet — lessons are written when work fails review or a cycle
                        closes negative.
                      </p>
                    )}
                    {selH.lessons.count > selH.lessons.latest.length && (
                      <p className="text-2xs text-muted-foreground">
                        Showing the {selH.lessons.latest.length} most relevant of{" "}
                        {selH.lessons.count}.
                      </p>
                    )}
                  </div>
                </div>
              </section>
            ) : sel ? (
              <section className="rounded-xl border border-border bg-card p-5 text-sm text-muted-foreground">
                {apiUp
                  ? `Loading ${sel.name}'s harness…`
                  : "The harness could not be loaded — the API is unreachable."}
              </section>
            ) : (
              <section className="rounded-xl border border-border bg-card p-5 text-sm text-muted-foreground">
                Select an agent to see its profile.
              </section>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
