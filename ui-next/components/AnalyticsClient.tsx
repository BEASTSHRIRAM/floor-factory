"use client";

/* Analytics — the floor's numbers, all aggregated client-side from
 * the same records the other pages show: per-agent P&L from the
 * ledger (research gap G1), per-department totals, quality trends
 * per cycle from review events (G4: first-pass acceptance, severity
 * mix, appeal overturns), and the agent lineage view (G5) — placed
 * here, next to the numbers it explains, rather than on the profile.
 * Charts are hand-rolled divs/SVG in the console's tokens. */

import { useEffect, useMemo, useState } from "react";
import { AgentAvatar } from "../vendor/ao/product-ui";
import { credits, signedCredits } from "../lib/api";
import {
  COST_KINDS,
  FINE_KINDS,
  agentDepartment,
  deptLabel,
  fetchAgents,
  fetchAllEvents,
  fetchHarnesses,
  fetchJobs,
  fetchLedger,
  groupBy,
  latestVerdicts,
  statusOfAgent,
  sumKinds,
  type HarnessLite,
  type RawAgent,
  type RawEvent,
  type RawJob,
  type RawLedgerRow,
} from "../lib/floorData";
import { ApiDown, Card, GenPill, Loading, PageBody, PageHeader, StatusPill } from "./floor-ui";
import { deptStats } from "./DepartmentsClient";

const SEVERITIES = ["none", "P3", "P2", "P1", "P0"] as const;
const SEV_COLORS: Record<string, string> = {
  none: "#5db872",
  P3: "#5db8a6",
  P2: "#d4a017",
  P1: "#e8a55a",
  P0: "#c64545",
};

interface AgentPnl {
  agent: RawAgent;
  earned: number;
  reviewFees: number;
  costs: number;
  fines: number;
  net: number;
  won: number;
  done: number;
}

interface CycleQuality {
  cycle: number;
  primary: number;
  accepted: number;
  acceptance: number | null;
  severity: Record<string, number>;
  appealsFiled: number;
  appealsDecided: number;
  overturned: number;
}

function mutationText(note: string | null | undefined): string {
  return (note ?? "").replace(/^mutation:\s*/i, "");
}

export default function AnalyticsClient() {
  const [agents, setAgents] = useState<RawAgent[]>([]);
  const [harnesses, setHarnesses] = useState<Record<number, HarnessLite>>({});
  const [jobs, setJobs] = useState<RawJob[]>([]);
  const [ledger, setLedger] = useState<RawLedgerRow[]>([]);
  const [events, setEvents] = useState<RawEvent[]>([]);
  const [apiUp, setApiUp] = useState(true);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [a, j, l, ev] = await Promise.all([
          fetchAgents(),
          fetchJobs(),
          fetchLedger(),
          fetchAllEvents(),
        ]);
        setAgents(a);
        setJobs(j);
        setLedger(l);
        setEvents(ev);
        setHarnesses(await fetchHarnesses(a));
        setApiUp(true);
      } catch {
        setApiUp(false);
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  const verdicts = useMemo(() => latestVerdicts(events), [events]);

  const pnl = useMemo<AgentPnl[]>(() => {
    const byAgent = groupBy(ledger, (r) => r.agent_id);
    return agents
      .map((agent) => {
        const rows = byAgent.get(agent.id) ?? [];
        const wos = jobs.flatMap((j) => j.work_orders).filter((w) => w.agent_id === agent.id);
        return {
          agent,
          earned: sumKinds(rows, ["earning", "bonus"]),
          reviewFees: sumKinds(rows, ["review_fee"]),
          costs: Math.abs(sumKinds(rows, COST_KINDS)),
          fines: Math.abs(sumKinds(rows, FINE_KINDS)),
          net: rows.reduce((s, r) => s + r.amount_credits, 0),
          won: wos.length,
          done: wos.filter((w) => ["accepted", "appeal_accepted"].includes(w.status)).length,
        };
      })
      .sort((a, b) => b.net - a.net);
  }, [agents, jobs, ledger]);

  const maxAbsNet = Math.max(1, ...pnl.map((p) => Math.abs(p.net)));

  const deptRows = useMemo(() => {
    const keys = [...new Set(jobs.map((j) => j.department))].sort();
    return keys.map((key) => ({
      key,
      label: deptLabel(key),
      agents: agents.filter((a) => agentDepartment(a, harnesses[a.id]) === key).length,
      ...deptStats(key, jobs, ledger),
    }));
  }, [agents, harnesses, jobs, ledger]);

  const quality = useMemo<CycleQuality[]>(() => {
    const woCycle = new Map<number, number>();
    for (const j of jobs) for (const w of j.work_orders) woCycle.set(w.id, w.cycle_no);
    const byCycle = new Map<number, CycleQuality>();
    const blank = (cycle: number): CycleQuality => ({
      cycle,
      primary: 0,
      accepted: 0,
      acceptance: null,
      severity: {},
      appealsFiled: 0,
      appealsDecided: 0,
      overturned: 0,
    });
    const get = (cycle: number) => {
      let q = byCycle.get(cycle);
      if (!q) {
        q = blank(cycle);
        byCycle.set(cycle, q);
      }
      return q;
    };
    for (const e of events) {
      const woId = Number(e.payload?.work_order_id);
      if (!Number.isFinite(woId)) continue;
      const cycle = woCycle.get(woId);
      if (cycle === undefined) continue;
      if (e.type === "review.completed") {
        const q = get(cycle);
        if (e.payload?.kind === "appeal") {
          q.appealsDecided += 1;
          if (e.payload?.verdict === "accept") q.overturned += 1;
        } else {
          q.primary += 1;
          if (e.payload?.verdict === "accept") q.accepted += 1;
          const sev = String(e.payload?.severity ?? "none");
          q.severity[sev] = (q.severity[sev] ?? 0) + 1;
        }
      } else if (e.type === "appeal.filed") {
        get(cycle).appealsFiled += 1;
      }
    }
    const out = [...byCycle.values()].sort((a, b) => a.cycle - b.cycle);
    for (const q of out) q.acceptance = q.primary > 0 ? q.accepted / q.primary : null;
    return out;
  }, [events, jobs]);

  /* Lineage chains: roots first, each followed down parent_agent_id. */
  const chains = useMemo(() => {
    const byId = new Map(agents.map((a) => [a.id, a]));
    const children = new Map<number, RawAgent[]>();
    for (const a of agents) {
      if (a.parent_agent_id && byId.has(a.parent_agent_id)) {
        const arr = children.get(a.parent_agent_id) ?? [];
        arr.push(a);
        children.set(a.parent_agent_id, arr);
      }
    }
    const roots = agents.filter((a) => !a.parent_agent_id || !byId.has(a.parent_agent_id));
    const paths: RawAgent[][] = [];
    const walk = (node: RawAgent, path: RawAgent[]) => {
      const next = [...path, node];
      const kids = children.get(node.id) ?? [];
      if (kids.length === 0) paths.push(next);
      else for (const k of kids) walk(k, next);
    };
    for (const r of roots) walk(r, []);
    return paths;
  }, [agents]);

  const mutatedEvents = useMemo(() => {
    const m = new Map<string, Record<string, unknown>>();
    for (const e of events)
      if (e.type === "harness.mutated") m.set(String(e.payload?.agent ?? ""), e.payload);
    return m;
  }, [events]);

  const chartPoints = quality.filter((q) => q.acceptance !== null);
  const chartPath = chartPoints
    .map((q, i) => {
      const x = chartPoints.length === 1 ? 300 : 40 + (i * 520) / (chartPoints.length - 1);
      const y = 130 - (q.acceptance ?? 0) * 110;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <PageBody>
      <PageHeader
        title="Analytics"
        sub="The floor's books, opened: what each agent earns and costs, what each department produces, whether the review bar is holding — and how the generations descend."
      />
      {!loaded ? (
        <Loading />
      ) : !apiUp ? (
        <ApiDown what="analytics" />
      ) : (
        <main className="mx-auto max-w-6xl space-y-6 px-6 py-6">
          {/* Per-agent P&L */}
          <Card>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Per-agent profit & loss
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Internal credits (₡) from the ledger — earnings and review fees in, running and tool
              costs and fines out. The bar is each agent's net against the best on the floor.
            </p>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground">
                    <th className="py-2 pr-3 font-medium">Agent</th>
                    <th className="py-2 pr-3 font-medium">Earned</th>
                    <th className="py-2 pr-3 font-medium">Review fees</th>
                    <th className="py-2 pr-3 font-medium">Costs</th>
                    <th className="py-2 pr-3 font-medium">Fines</th>
                    <th className="py-2 pr-3 font-medium">Net</th>
                    <th className="py-2 pr-3 font-medium">Jobs won / done</th>
                    <th className="py-2 font-medium">Net bar</th>
                  </tr>
                </thead>
                <tbody>
                  {pnl.map((p) => (
                    <tr key={p.agent.id} className="border-b border-border/60 last:border-0">
                      <td className="py-2 pr-3">
                        <span className="flex items-center gap-2">
                          <AgentAvatar provider={p.agent.name} />
                          <span className="font-medium">{p.agent.name}</span>
                          <StatusPill status={statusOfAgent(p.agent, verdicts)} />
                        </span>
                      </td>
                      <td className="py-2 pr-3 tabular-nums">{credits(p.earned)}</td>
                      <td className="py-2 pr-3 tabular-nums">{credits(p.reviewFees)}</td>
                      <td className="py-2 pr-3 tabular-nums">{credits(p.costs)}</td>
                      <td className="py-2 pr-3 tabular-nums">{credits(p.fines)}</td>
                      <td className="py-2 pr-3 font-medium tabular-nums">{signedCredits(p.net)}</td>
                      <td className="py-2 pr-3 tabular-nums">
                        {p.won} / {p.done}
                      </td>
                      <td className="py-2">
                        <div className="h-2.5 w-36 overflow-hidden rounded-full bg-background">
                          <div
                            className={`h-full rounded-full ${p.net >= 0 ? "bg-primary" : "bg-destructive"}`}
                            style={{ width: `${(Math.abs(p.net) / maxAbsNet) * 100}%` }}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Per-department totals */}
          <Card>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Per-department totals
            </h2>
            <div className="mt-3 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {deptRows.map((d) => (
                <a
                  key={d.key}
                  href={`/console/departments/${d.key}`}
                  className="block rounded-lg border border-border bg-background p-4 transition-colors hover:border-muted-foreground"
                >
                  <div className="flex items-baseline justify-between">
                    <span className="text-sm font-semibold">{d.label}</span>
                    <span className="text-xs text-muted-foreground">{d.agents} agents</span>
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    {d.jobsPaid}/{d.jobsTotal} jobs paid · {credits(d.creditsPaid)} paid out
                  </div>
                </a>
              ))}
            </div>
          </Card>

          {/* Quality trends */}
          <Card>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Quality trends by cycle
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">
              From the review record: first-pass acceptance is primary reviews accepted on the
              first pass; the severity mix counts primary-review findings (P0 worst); an appeal is
              overturned when the blind second review accepts work the first review rejected.
            </p>
            {chartPoints.length > 0 && (
              <div className="mt-4">
                <svg viewBox="0 0 600 150" className="w-full" role="img" aria-label="First-pass acceptance by cycle">
                  <line x1="40" y1="20" x2="560" y2="20" stroke="#3d3d3a" strokeDasharray="3 4" />
                  <line x1="40" y1="130" x2="560" y2="130" stroke="#3d3d3a" />
                  <text x="8" y="24" fill="#8e8b82" fontSize="10">100%</text>
                  <text x="16" y="134" fill="#8e8b82" fontSize="10">0%</text>
                  <path d={chartPath} fill="none" stroke="#cc785c" strokeWidth="2" />
                  {chartPoints.map((q, i) => {
                    const x = chartPoints.length === 1 ? 300 : 40 + (i * 520) / (chartPoints.length - 1);
                    const y = 130 - (q.acceptance ?? 0) * 110;
                    return (
                      <g key={q.cycle}>
                        <circle cx={x} cy={y} r="4" fill="#cc785c" />
                        <text x={x} y={y - 10} fill="#faf9f5" fontSize="11" textAnchor="middle">
                          {Math.round((q.acceptance ?? 0) * 100)}%
                        </text>
                        <text x={x} y="148" fill="#8e8b82" fontSize="10" textAnchor="middle">
                          C{q.cycle}
                        </text>
                      </g>
                    );
                  })}
                </svg>
              </div>
            )}
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground">
                    <th className="py-2 pr-3 font-medium">Cycle</th>
                    <th className="py-2 pr-3 font-medium">Primary reviews</th>
                    <th className="py-2 pr-3 font-medium">First-pass acceptance</th>
                    <th className="py-2 pr-3 font-medium">Severity mix</th>
                    <th className="py-2 font-medium">Appeals</th>
                  </tr>
                </thead>
                <tbody>
                  {quality.map((q) => (
                    <tr key={q.cycle} className="border-b border-border/60 last:border-0">
                      <td className="py-2.5 pr-3 font-medium">Cycle {q.cycle}</td>
                      <td className="py-2.5 pr-3 tabular-nums">{q.primary}</td>
                      <td className="py-2.5 pr-3 tabular-nums">
                        {q.acceptance === null ? "—" : `${Math.round(q.acceptance * 100)}%`}
                      </td>
                      <td className="py-2.5 pr-3">
                        <div className="flex h-3 w-52 overflow-hidden rounded-full bg-background">
                          {SEVERITIES.map((sev) => {
                            const n = q.severity[sev] ?? 0;
                            if (!n || q.primary === 0) return null;
                            return (
                              <div
                                key={sev}
                                style={{
                                  width: `${(n / q.primary) * 100}%`,
                                  backgroundColor: SEV_COLORS[sev],
                                }}
                                title={`${sev}: ${n}`}
                              />
                            );
                          })}
                        </div>
                        <div className="mt-1 text-2xs text-muted-foreground">
                          {SEVERITIES.filter((s) => (q.severity[s] ?? 0) > 0)
                            .map((s) => `${s} ×${q.severity[s]}`)
                            .join(" · ") || "no findings"}
                        </div>
                      </td>
                      <td className="py-2.5 text-xs text-muted-foreground">
                        {q.appealsFiled} filed · {q.appealsDecided} decided · {q.overturned}{" "}
                        overturned
                        {q.appealsDecided > 0 &&
                          ` (${Math.round((q.overturned / q.appealsDecided) * 100)}%)`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Lineage */}
          <Card>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Lineage — who replaced whom
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">
              When the CFO fires an agent, its replacement is a mutated hire of the same line: one
              trait changes, and the predecessor's lessons carry over. The diff shown is the one
              recorded on the mutation event.
            </p>
            <div className="mt-4 space-y-5">
              {chains
                .filter((path) => path.length > 1)
                .map((path) => (
                  <div key={path.map((a) => a.id).join("-")} className="flex flex-wrap items-stretch gap-2">
                    {path.map((a, i) => {
                      const ev = mutatedEvents.get(a.name);
                      const diff = (ev?.diff ?? {}) as { hard_rules_added?: string[] };
                      return (
                        <div key={a.id} className="flex items-stretch gap-2">
                          {i > 0 && (
                            <div className="flex max-w-52 flex-col justify-center text-2xs text-muted-foreground">
                              <span className="text-primary">→ mutated:</span>
                              <span>{mutationText(a.mutation_note) || "trait changed"}</span>
                              {typeof ev?.inherited_lessons === "number" && (
                                <span>{ev.inherited_lessons} lessons inherited</span>
                              )}
                              {(diff.hard_rules_added?.length ?? 0) > 0 && (
                                <span>+{diff.hard_rules_added?.length} hard rule(s)</span>
                              )}
                            </div>
                          )}
                          <div className="rounded-lg border border-border bg-background p-3">
                            <div className="flex items-center gap-2">
                              <AgentAvatar provider={a.name} />
                              <span className="text-sm font-semibold">{a.name}</span>
                              <GenPill generation={a.generation} />
                              <StatusPill status={statusOfAgent(a, verdicts)} />
                            </div>
                            <div className="mt-1.5 text-2xs text-muted-foreground">
                              rep {Math.round(a.reputation)} · balance {credits(a.balance_credits)}{" "}
                              · {harnesses[a.id]?.lessons.count ?? 0} lessons on file
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ))}
              {chains.every((p) => p.length === 1) && (
                <p className="text-sm text-muted-foreground">
                  No replacements yet — every agent on the roster is an original hire.
                </p>
              )}
              <p className="text-xs text-muted-foreground">
                First-generation originals with no descendants:{" "}
                {chains
                  .filter((p) => p.length === 1)
                  .map((p) => p[0].name)
                  .join(", ") || "none"}
                .
              </p>
            </div>
          </Card>
        </main>
      )}
    </PageBody>
  );
}
