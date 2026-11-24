"use client";

/* Department page — one department (or the StockRoom workplace) in
 * full: its job families, its crew, its tools, its recent jobs and
 * its totals. Everything is joined client-side from the catalogue,
 * the roster (+ harnesses), /state/jobs and the ledger; StockRoom
 * gets the honest workplace treatment — tools, health, the agents
 * whose allowlists include it, and its recent tool activity — rather
 * than a fake department record. */

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { AgentAvatar } from "../vendor/ao/product-ui";
import { credits, fetchJSON } from "../lib/api";
import {
  agentDepartment,
  clockTime,
  deptLabel,
  earnedOf,
  fetchAgents,
  fetchAllEvents,
  fetchCatalogue,
  fetchHarnesses,
  fetchJobs,
  fetchLedger,
  groupBy,
  latestVerdicts,
  statusOfAgent,
  type Catalogue,
  type HarnessLite,
  type RawAgent,
  type RawEvent,
  type RawJob,
  type RawLedgerRow,
} from "../lib/floorData";
import { ApiDown, Card, GenPill, Loading, PageBody, StatusPill } from "./floor-ui";
import { deptStats } from "./DepartmentsClient";

function ToolsList({ catalogue, servers }: { catalogue: Catalogue; servers: string[] }) {
  return (
    <div className="space-y-4">
      {servers.map((server) => {
        const wp = catalogue.workplaces.find((w) => w.server === server);
        if (!wp) return null;
        return (
          <div key={server}>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {wp.label} · {wp.tools.length} tools
            </h3>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {wp.tools.map((t) => (
                <span
                  key={t.name}
                  className={`rounded-full px-2 py-0.5 font-mono text-2xs ${
                    t.gated
                      ? "bg-primary/15 font-semibold text-primary"
                      : "bg-background text-muted-foreground"
                  }`}
                  title={t.gated ? "Write — passes the confirmation gate" : "Read"}
                >
                  {t.name}
                  {t.gated ? " · gated write" : ""}
                </span>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function DepartmentDetailClient() {
  const params = useParams();
  const slug = String(params?.slug ?? "");
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [agents, setAgents] = useState<RawAgent[]>([]);
  const [harnesses, setHarnesses] = useState<Record<number, HarnessLite>>({});
  const [jobs, setJobs] = useState<RawJob[]>([]);
  const [ledger, setLedger] = useState<RawLedgerRow[]>([]);
  const [events, setEvents] = useState<RawEvent[]>([]);
  const [targets, setTargets] = useState<Record<string, boolean>>({});
  const [apiUp, setApiUp] = useState(true);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [c, a, j, l, ev] = await Promise.all([
          fetchCatalogue(),
          fetchAgents(),
          fetchJobs(),
          fetchLedger(),
          fetchAllEvents(),
        ]);
        setCatalogue(c);
        setAgents(a);
        setJobs(j);
        setLedger(l);
        setEvents(ev);
        setHarnesses(await fetchHarnesses(a));
        try {
          const h = (await fetchJSON("/health")) as { targets?: Record<string, boolean> };
          setTargets(h.targets ?? {});
        } catch {
          setTargets({});
        }
        setApiUp(true);
      } catch {
        setApiUp(false);
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  const dept = catalogue?.departments.find((d) => d.key === slug) ?? null;
  const isStockroom = slug === "stockroom";
  const verdicts = useMemo(() => latestVerdicts(events), [events]);
  const earnedByAgent = useMemo(() => {
    const g = groupBy(ledger, (r) => r.agent_id);
    return new Map([...g.entries()].map(([id, rows]) => [id, earnedOf(rows)]));
  }, [ledger]);

  if (!loaded)
    return (
      <PageBody>
        <Loading />
      </PageBody>
    );
  if (!apiUp || !catalogue)
    return (
      <PageBody>
        <ApiDown what="this department page" />
      </PageBody>
    );

  /* ---------------- StockRoom: a workplace, honestly framed -------- */
  if (isStockroom) {
    const wp = catalogue.workplaces.find((w) => w.server === "stockroom");
    const toolNames = new Set(wp?.tools.map((t) => t.name) ?? []);
    const holders = agents.filter((a) => harnesses[a.id]?.harness.tools?.stockroom);
    const activity = events
      .filter(
        (e) =>
          e.type === "tool.executed" && toolNames.has(String(e.payload?.tool_name ?? "")),
      )
      .slice(-8)
      .reverse();
    return (
      <PageBody>
        <div className="border-b border-border px-6 py-4">
          <a href="/console/departments" className="text-xs text-primary hover:underline">
            ← All departments
          </a>
          <h1 className="mt-1 font-display text-2xl">StockRoom</h1>
          <p className="mt-0.5 max-w-3xl text-sm text-muted-foreground">
            A workplace, not a hiring department — its record is its tools and the work done with
            them.
          </p>
        </div>
        <main className="mx-auto max-w-6xl space-y-6 px-6 py-6">
          <Card>
            <p className="text-sm leading-relaxed text-muted-foreground">
              StockRoom is a workplace of the Support department. Support agents hold its tools in
              their allowlists and use them inside Support jobs; no job family is posted by
              StockRoom itself, so it has no crew, budget or payroll of its own. System status:{" "}
              <span className="font-medium text-foreground">
                {targets.stockroom ? "Online" : "Unreachable"}
              </span>
              .
            </p>
          </Card>
          <Card>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Tools
            </h2>
            <div className="mt-3">
              <ToolsList catalogue={catalogue} servers={["stockroom"]} />
            </div>
          </Card>
          <Card>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Agents whose allowlist includes StockRoom
            </h2>
            {holders.length === 0 ? (
              <p className="mt-2 text-sm text-muted-foreground">
                No current agent holds StockRoom tools.
              </p>
            ) : (
              <ul className="mt-3 space-y-2">
                {holders.map((a) => (
                  <li key={a.id}>
                    <a
                      href={`/console/agents?agent=${a.id}`}
                      className="flex items-center gap-2.5 text-sm hover:underline"
                    >
                      <AgentAvatar provider={a.name} />
                      <span className="font-medium">{a.name}</span>
                      <StatusPill status={statusOfAgent(a, verdicts)} />
                      <span className="text-xs text-muted-foreground">
                        {harnesses[a.id]?.harness.tools.stockroom.length} StockRoom tools
                      </span>
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Recent StockRoom tool activity
            </h2>
            {activity.length === 0 ? (
              <p className="mt-2 text-sm text-muted-foreground">
                No StockRoom tool calls in the stored event stream yet.
              </p>
            ) : (
              <ul className="mt-3 space-y-1.5 text-sm">
                {activity.map((e) => (
                  <li key={e.seq} className="flex items-baseline gap-3">
                    <span className="shrink-0 font-mono text-xs tabular-nums text-muted-foreground">
                      {clockTime(e.created_at)}
                    </span>
                    <span className="font-mono text-xs">{String(e.payload?.tool_name ?? "")}</span>
                    <span className="text-muted-foreground">
                      by {String(e.payload?.worker ?? "—")} · {String(e.payload?.status ?? "")}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </main>
      </PageBody>
    );
  }

  /* ---------------- A hiring department ------------------------------ */
  if (!dept)
    return (
      <PageBody>
        <main className="mx-auto max-w-6xl px-6 py-6">
          <Card>
            <p className="text-sm text-muted-foreground">
              There is no department called “{slug}” on this floor.{" "}
              <a href="/console/departments" className="text-primary hover:underline">
                Back to the departments index
              </a>
              .
            </p>
          </Card>
        </main>
      </PageBody>
    );

  const stats = deptStats(dept.key, jobs, ledger);
  const crew = agents.filter((a) => agentDepartment(a, harnesses[a.id]) === dept.key);
  const recent = jobs
    .filter((j) => j.department === dept.key)
    .sort((a, b) => b.id - a.id)
    .slice(0, 10);
  const agentName = (id: number) => agents.find((a) => a.id === id)?.name ?? `#${id}`;

  return (
    <PageBody>
      <div className="border-b border-border px-6 py-4">
        <a href="/console/departments" className="text-xs text-primary hover:underline">
          ← All departments
        </a>
        <h1 className="mt-1 font-display text-2xl">{dept.label}</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Budgets {credits(dept.budget_min)}–{credits(dept.budget_max)} per job · tool servers:{" "}
          {dept.servers.join(", ")} ·{" "}
          {dept.servers.map((s) => `${s} ${targets[s] ? "online" : "unreachable"}`).join(" · ")}
        </p>
      </div>
      <main className="mx-auto max-w-6xl space-y-6 px-6 py-6">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {[
            { label: "Jobs posted", value: String(stats.jobsTotal) },
            { label: "Jobs paid", value: String(stats.jobsPaid) },
            { label: "Credits paid out", value: credits(stats.creditsPaid) },
            { label: "Agents on the roster", value: String(crew.length) },
          ].map((s) => (
            <Card key={s.label} className="p-4">
              <div className="font-display text-2xl">{s.value}</div>
              <div className="mt-1 text-xs text-muted-foreground">{s.label}</div>
            </Card>
          ))}
        </div>

        <Card>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Job families
          </h2>
          <div className="mt-3 grid gap-4 md:grid-cols-2">
            {dept.families.map((f) => (
              <div key={f.key} className="rounded-lg border border-border bg-background p-4">
                <div className="flex items-baseline justify-between gap-2">
                  <h3 className="text-sm font-semibold">{f.title}</h3>
                  <span className="shrink-0 text-xs font-medium tabular-nums">
                    {credits(f.budget_credits)}
                  </span>
                </div>
                <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{f.brief}</p>
                <p className="mt-2 text-2xs text-muted-foreground">
                  {f.acceptance_criteria.length} acceptance checks · {f.tool_count} tools on{" "}
                  {f.server}
                </p>
              </div>
            ))}
          </div>
        </Card>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Crew
            </h2>
            {crew.length === 0 ? (
              <p className="mt-2 text-sm text-muted-foreground">
                No agents are homed in {dept.label} yet.
              </p>
            ) : (
              <ul className="mt-3 space-y-2.5">
                {crew.map((a) => (
                  <li key={a.id}>
                    <a
                      href={`/console/agents?agent=${a.id}`}
                      className="flex items-center gap-2.5 text-sm hover:underline"
                    >
                      <AgentAvatar provider={a.name} />
                      <span className="font-medium">{a.name}</span>
                      <StatusPill status={statusOfAgent(a, verdicts)} />
                      <GenPill generation={a.generation} />
                      <span className="ml-auto text-xs text-muted-foreground">
                        rep {Math.round(a.reputation)} · earned{" "}
                        {credits(earnedByAgent.get(a.id) ?? 0)}
                      </span>
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Tools
            </h2>
            <div className="mt-3">
              <ToolsList catalogue={catalogue} servers={dept.servers} />
            </div>
          </Card>
        </div>

        <Card>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Recent jobs
          </h2>
          {recent.length === 0 ? (
            <p className="mt-2 text-sm text-muted-foreground">
              No {dept.label} jobs have been posted yet — they arrive with the next shift.
            </p>
          ) : (
            <table className="mt-3 w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">Job</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 pr-3 font-medium">Worked by</th>
                  <th className="py-2 pr-3 font-medium">Agreed</th>
                  <th className="py-2 font-medium">Cycle</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((j) => {
                  const wo = j.work_orders[0];
                  return (
                    <tr key={j.id} className="border-b border-border/60 last:border-0">
                      <td className="py-2 pr-3">
                        <span className="text-muted-foreground">#{j.id}</span> {j.title}
                      </td>
                      <td className="py-2 pr-3">{j.status}</td>
                      <td className="py-2 pr-3">{wo ? agentName(wo.agent_id) : "—"}</td>
                      <td className="py-2 pr-3 tabular-nums">
                        {wo ? credits(wo.agreed_price_credits) : "—"}
                      </td>
                      <td className="py-2 tabular-nums">{j.created_cycle}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Card>
      </main>
    </PageBody>
  );
}
