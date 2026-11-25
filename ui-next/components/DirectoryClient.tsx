"use client";

/* Employee Directory — the roster presented the way a company
 * directory presents people: avatar, role, department, status,
 * reputation and lifetime earnings, searchable and filterable.
 * Data: GET /state/agents + GET /agents/{id}/harness (role +
 * department) + GET /state/ledger (lifetime earnings) + the
 * cycle.closed verdicts behind the status pills. Clicking an entry
 * opens that agent's full profile on the Agents page. */

import { useEffect, useMemo, useState } from "react";
import { AgentAvatar } from "../vendor/ao/product-ui";
import { credits } from "../lib/api";
import {
  agentDepartment,
  deptLabel,
  earnedOf,
  fetchAgents,
  fetchAllEvents,
  fetchHarnesses,
  fetchLedger,
  groupBy,
  latestVerdicts,
  statusOfAgent,
  type HarnessLite,
  type RawAgent,
} from "../lib/floorData";
import { ApiDown, CustomPill, GenPill, Loading, PageBody, PageHeader, StatusPill } from "./floor-ui";

function AgentCard({
  agent,
  harness,
  verdicts,
  earned,
}: {
  agent: RawAgent;
  harness?: HarnessLite;
  verdicts: Map<number, string>;
  earned: number;
}) {
  const status = statusOfAgent(agent, verdicts);
  const dept = agentDepartment(agent, harness);
  return (
    <a
      href={`/console/agents?agent=${agent.id}`}
      className="block rounded-xl border border-border bg-card p-4 transition-colors hover:border-muted-foreground"
    >
      <div className="flex items-start gap-3">
        <AgentAvatar provider={agent.name} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="truncate text-sm font-semibold">{agent.name}</span>
            <StatusPill status={status} />
            <GenPill generation={agent.generation} />
            {agent.origin === "user-created" && <CustomPill />}
          </div>
          <div className="mt-0.5 truncate text-xs text-muted-foreground">
            {harness?.harness.role_label ?? agent.role} · {deptLabel(dept)}
          </div>
        </div>
      </div>
      <div className="mt-3">
        <div className="flex items-baseline justify-between text-2xs text-muted-foreground">
          <span>Reputation</span>
          <span className="tabular-nums">{Math.round(agent.reputation)}/100</span>
        </div>
        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-background">
          <div
            className="h-full rounded-full bg-primary"
            style={{ width: `${Math.max(0, Math.min(100, agent.reputation))}%` }}
          />
        </div>
      </div>
      <div className="mt-3 flex items-baseline justify-between text-xs">
        <span className="text-muted-foreground">
          Earned <span className="font-medium text-foreground">{credits(earned)}</span>
        </span>
        <span className="text-muted-foreground">
          Balance <span className="font-medium text-foreground">{credits(agent.balance_credits)}</span>
        </span>
        <span className="text-muted-foreground">
          Price <span className="font-medium text-foreground">×{agent.price_factor.toFixed(2)}</span>
        </span>
      </div>
    </a>
  );
}

export default function DirectoryClient() {
  const [agents, setAgents] = useState<RawAgent[]>([]);
  const [harnesses, setHarnesses] = useState<Record<number, HarnessLite>>({});
  const [verdicts, setVerdicts] = useState<Map<number, string>>(new Map());
  const [earned, setEarned] = useState<Map<number, number>>(new Map());
  const [apiUp, setApiUp] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [query, setQuery] = useState("");
  const [dept, setDept] = useState("all");
  const [status, setStatus] = useState("all");
  const [grouped, setGrouped] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [a, l, ev] = await Promise.all([fetchAgents(), fetchLedger(), fetchAllEvents()]);
        setAgents(a);
        setHarnesses(await fetchHarnesses(a));
        setVerdicts(latestVerdicts(ev));
        const byAgent = groupBy(l, (r) => r.agent_id);
        setEarned(
          new Map(
            [...byAgent.entries()].map(
              ([id, rows]) => [Number(id), earnedOf(rows)] as [number, number],
            ),
          ),
        );
        setApiUp(true);
      } catch {
        setApiUp(false);
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  const departments = useMemo(() => {
    const s = new Set<string>();
    for (const a of agents) s.add(agentDepartment(a, harnesses[a.id]));
    return [...s].sort();
  }, [agents, harnesses]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return agents.filter((a) => {
      const h = harnesses[a.id];
      const d = agentDepartment(a, h);
      if (dept !== "all" && d !== dept) return false;
      if (status !== "all" && statusOfAgent(a, verdicts) !== status) return false;
      if (!q) return true;
      const hay = `${a.name} ${h?.harness.role_label ?? a.role} ${deptLabel(d)}`.toLowerCase();
      return hay.includes(q);
    });
  }, [agents, harnesses, verdicts, query, dept, status]);

  const groups = useMemo(() => {
    const g = groupBy(filtered, (a) => agentDepartment(a, harnesses[a.id]));
    return [...g.entries()].sort(([x], [y]) => deptLabel(x).localeCompare(deptLabel(y)));
  }, [filtered, harnesses]);

  const card = (a: RawAgent) => (
    <AgentCard
      key={a.id}
      agent={a}
      harness={harnesses[a.id]}
      verdicts={verdicts}
      earned={earned.get(a.id) ?? 0}
    />
  );

  return (
    <PageBody>
      <PageHeader
        title="Directory"
        sub="Everyone the floor has hired — agents here are employees, so they get a directory, not a process list. Pick anyone to open their full profile."
      >
        <label className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={grouped}
            onChange={(e) => setGrouped(e.target.checked)}
            className="size-4 accent-[#cc785c]"
          />
          Group by department
        </label>
      </PageHeader>
      {!loaded ? (
        <Loading />
      ) : !apiUp ? (
        <ApiDown what="the directory" />
      ) : (
        <main className="mx-auto max-w-6xl px-6 py-6">
          <div className="flex flex-wrap items-center gap-3">
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by name, role or department…"
              aria-label="Search the directory"
              className="min-w-56 flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
            />
            <select
              aria-label="Filter by department"
              value={dept}
              onChange={(e) => setDept(e.target.value)}
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
            >
              <option value="all">All departments</option>
              {departments.map((d) => (
                <option key={d} value={d}>
                  {deptLabel(d)}
                </option>
              ))}
            </select>
            <select
              aria-label="Filter by status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
            >
              <option value="all">Any status</option>
              <option value="active">Active</option>
              <option value="on-notice">On notice</option>
              <option value="fired">Fired</option>
            </select>
          </div>

          <p className="mt-4 text-xs text-muted-foreground">
            {filtered.length} of {agents.length} people
          </p>

          {filtered.length === 0 && (
            <p className="mt-6 text-sm text-muted-foreground">
              Nobody matches that search and filter — clear one of them and the directory fills in
              again.
            </p>
          )}

          {grouped
            ? groups.map(([d, members]) => (
                <section key={d} className="mt-6">
                  <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                    {deptLabel(d)} · {members.length}
                  </h2>
                  <div className="mt-3 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                    {members.map(card)}
                  </div>
                </section>
              ))
            : filtered.length > 0 && (
                <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                  {filtered.map(card)}
                </div>
              )}
        </main>
      )}
    </PageBody>
  );
}
