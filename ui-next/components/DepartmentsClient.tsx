"use client";

/* Departments — the index of the floor's departments and workplaces.
 * One card per hiring department (from GET /state/catalogue, joined
 * with the live jobs/ledger/roster) plus the StockRoom workplace,
 * which is presented as what it is: a workplace of Support, not a
 * hiring department. */

import { useEffect, useMemo, useState } from "react";
import { credits } from "../lib/api";
import {
  agentDepartment,
  fetchAgents,
  fetchCatalogue,
  fetchHarnesses,
  fetchJobs,
  fetchLedger,
  type Catalogue,
  type HarnessLite,
  type RawAgent,
  type RawJob,
  type RawLedgerRow,
} from "../lib/floorData";
import { ApiDown, Card, Loading, PageBody, PageHeader } from "./floor-ui";

export function deptStats(
  dept: string,
  jobs: RawJob[],
  ledger: RawLedgerRow[],
): { jobsTotal: number; jobsPaid: number; creditsPaid: number } {
  const mine = jobs.filter((j) => j.department === dept);
  const woToJob = new Map<number, RawJob>();
  for (const j of jobs) for (const w of j.work_orders) woToJob.set(w.id, j);
  let creditsPaid = 0;
  for (const r of ledger) {
    if (r.kind !== "earning" || r.ref_id === null) continue;
    const job = woToJob.get(r.ref_id);
    if (job && job.department === dept) creditsPaid += r.amount_credits;
  }
  return {
    jobsTotal: mine.length,
    jobsPaid: mine.filter((j) => j.status === "paid").length,
    creditsPaid,
  };
}

export default function DepartmentsClient() {
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [agents, setAgents] = useState<RawAgent[]>([]);
  const [harnesses, setHarnesses] = useState<Record<number, HarnessLite>>({});
  const [jobs, setJobs] = useState<RawJob[]>([]);
  const [ledger, setLedger] = useState<RawLedgerRow[]>([]);
  const [apiUp, setApiUp] = useState(true);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [c, a, j, l] = await Promise.all([
          fetchCatalogue(),
          fetchAgents(),
          fetchJobs(),
          fetchLedger(),
        ]);
        setCatalogue(c);
        setAgents(a);
        setJobs(j);
        setLedger(l);
        setHarnesses(await fetchHarnesses(a));
        setApiUp(true);
      } catch {
        setApiUp(false);
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  const agentsByDept = useMemo(() => {
    const m = new Map<string, number>();
    for (const a of agents) {
      const d = agentDepartment(a, harnesses[a.id]);
      m.set(d, (m.get(d) ?? 0) + 1);
    }
    return m;
  }, [agents, harnesses]);

  const stockroom = catalogue?.workplaces.find((w) => w.server === "stockroom");

  return (
    <PageBody>
      <PageHeader
        title="Departments"
        sub="Each department is a workplace with its own tool server, job families and crew. Open one for its families, its people, its tools and its record."
      />
      {!loaded ? (
        <Loading />
      ) : !apiUp || !catalogue ? (
        <ApiDown what="the departments index" />
      ) : (
        <main className="mx-auto max-w-6xl px-6 py-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {catalogue.departments.map((d) => {
              const s = deptStats(d.key, jobs, ledger);
              return (
                <a
                  key={d.key}
                  href={`/console/departments/${d.key}`}
                  className="block rounded-xl border border-border bg-card p-5 transition-colors hover:border-muted-foreground"
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <h2 className="font-display text-xl">{d.label}</h2>
                    <span className="text-xs text-muted-foreground">
                      {d.families.length} job families
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Budgets {credits(d.budget_min)}–{credits(d.budget_max)} per job · tools via{" "}
                    {d.servers.join(", ")}
                  </p>
                  <div className="mt-4 grid grid-cols-3 gap-3 text-center">
                    <div>
                      <div className="font-display text-lg">{agentsByDept.get(d.key) ?? 0}</div>
                      <div className="text-2xs text-muted-foreground">Agents</div>
                    </div>
                    <div>
                      <div className="font-display text-lg">
                        {s.jobsPaid}/{s.jobsTotal}
                      </div>
                      <div className="text-2xs text-muted-foreground">Jobs paid</div>
                    </div>
                    <div>
                      <div className="font-display text-lg">{credits(s.creditsPaid)}</div>
                      <div className="text-2xs text-muted-foreground">Credits paid</div>
                    </div>
                  </div>
                </a>
              );
            })}
            {stockroom && (
              <a
                href="/console/departments/stockroom"
                className="block rounded-xl border border-dashed border-border bg-card p-5 transition-colors hover:border-muted-foreground"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <h2 className="font-display text-xl">StockRoom</h2>
                  <span className="rounded-full bg-background px-2 py-0.5 text-2xs font-semibold text-muted-foreground">
                    Workplace
                  </span>
                </div>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  Not a hiring department — a workplace of Support. Support agents hold its{" "}
                  {stockroom.tools.length} tools in their allowlists and use them inside Support
                  jobs; no job family is posted by StockRoom itself.
                </p>
                <div className="mt-4 text-xs text-muted-foreground">
                  {stockroom.tools.filter((t) => t.gated).length} gated writes ·{" "}
                  {stockroom.tools.filter((t) => !t.gated).length} reads
                </div>
              </a>
            )}
          </div>
        </main>
      )}
    </PageBody>
  );
}
