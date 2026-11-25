"use client";

/* Hire — the gallery of work this floor can actually take: the 23
 * registered job families, grouped by department, each card showing
 * what the job is, its budget, how it is verified and how many tools
 * it runs on. Every card's action deep-links into the Agents page's
 * create form with that role preselected — the gallery lists only
 * families that run end-to-end today (research G3's honesty rule),
 * because it renders the live registry (GET /state/catalogue over
 * engine.JOB_FAMILIES), not a roadmap. */

import { useEffect, useState } from "react";
import { credits } from "../lib/api";
import { fetchCatalogue, type Catalogue } from "../lib/floorData";
import { ApiDown, Card, Loading, PageBody, PageHeader } from "./floor-ui";

export default function HireClient() {
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [apiUp, setApiUp] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [openChecks, setOpenChecks] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setCatalogue(await fetchCatalogue());
        setApiUp(true);
      } catch {
        setApiUp(false);
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  const total = catalogue?.departments.reduce((s, d) => s + d.families.length, 0) ?? 0;

  return (
    <PageBody>
      <PageHeader
        title="Hire"
        sub="The work this floor can take today. Every role below is a job family that actually runs — it is posted, bid on, worked through MCP tools, reviewed and paid. Create an agent in any role and it joins the roster at once."
      />
      {!loaded ? (
        <Loading />
      ) : !apiUp || !catalogue ? (
        <ApiDown what="the hiring gallery" />
      ) : (
        <main className="mx-auto max-w-6xl px-6 py-6">
          <p className="text-xs text-muted-foreground">
            {total} roles across {catalogue.departments.length} departments — this is the live
            registry, so a role appears here only when the floor can really run it.
          </p>
          {catalogue.departments.map((d) => (
            <section key={d.key} className="mt-8">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="font-display text-xl">{d.label}</h2>
                <span className="text-xs text-muted-foreground">
                  {d.families.length} roles · budgets {credits(d.budget_min)}–
                  {credits(d.budget_max)} per job
                </span>
              </div>
              <div className="mt-3 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {d.families.map((f) => {
                  const checkKey = `${d.key}:${f.key}`;
                  const open = openChecks === checkKey;
                  return (
                    <Card key={f.key} className="flex flex-col p-4">
                      <div className="flex items-baseline justify-between gap-2">
                        <h3 className="text-sm font-semibold leading-snug">{f.title}</h3>
                        <span className="shrink-0 text-sm font-medium tabular-nums">
                          {credits(f.budget_credits)}
                        </span>
                      </div>
                      <p className="mt-1.5 line-clamp-3 text-xs leading-relaxed text-muted-foreground">
                        {f.brief}
                      </p>
                      <div className="mt-3 flex items-center gap-3 text-2xs text-muted-foreground">
                        <span>{f.tool_count} tools · {f.server}</span>
                        <button
                          type="button"
                          onClick={() => setOpenChecks(open ? null : checkKey)}
                          className="text-primary hover:underline"
                          aria-expanded={open}
                        >
                          {f.acceptance_criteria.length} acceptance checks {open ? "▴" : "▾"}
                        </button>
                      </div>
                      {open && (
                        <ul className="mt-2 list-disc space-y-1 px-4 text-xs leading-relaxed text-muted-foreground">
                          {f.acceptance_criteria.map((c, i) => (
                            <li key={i}>{c}</li>
                          ))}
                        </ul>
                      )}
                      <a
                        href={`/console/agents?create=1&department=${d.key}&family=${f.key}`}
                        className="mt-4 block rounded-lg bg-primary px-3.5 py-2 text-center text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
                      >
                        Create agent in this role
                      </a>
                    </Card>
                  );
                })}
              </div>
            </section>
          ))}
        </main>
      )}
    </PageBody>
  );
}
