"use client";

/* Agents — the roster as profiles. Everything on this page comes
 * from the real API: GET /state/agents for the roster, GET
 * /agents/{id}/harness for each agent's composed harness (charter,
 * tool allowlist, playbooks, lineage lessons), and the latest
 * cycle.closed event for payroll verdicts (ON-NOTICE). Nothing is
 * invented: an agent with no lessons shows none.
 *
 * The Create-agent form is wired the same way: its options come from
 * GET /agents/catalog (the real department/family registry, the model
 * tiers the harness supports, the price bounds suggest_bid honours)
 * and submitting POSTs /agents — the created agent appears in the
 * roster below with a Custom marker and its price, and bids on its
 * family's jobs from the next cycle. */

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
  price_factor: number;
  origin: string;
  department: string | null;
  family_key: string | null;
};

/* The create-agent catalogue: departments -> job families, model tiers
 * and price bounds, all served by GET /agents/catalog from the real
 * registries — the form offers nothing the backend cannot honour. */
type CatalogFamily = {
  key: string;
  title: string;
  budget_credits: number;
  server: string;
  tool_count: number;
};
type CatalogDepartment = { key: string; label: string; families: CatalogFamily[] };
type CatalogTier = {
  key: string;
  label: string;
  model: string;
  base_salary_credits: number;
  blurb: string;
};
type Catalog = {
  departments: CatalogDepartment[];
  model_tiers: CatalogTier[];
  price: { min: number; max: number; default: number; step: number; meaning: string };
  charter_addendum_max_chars: number;
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

function CustomPill() {
  return (
    <span className="rounded-full bg-violet-500/15 px-2 py-0.5 text-2xs font-semibold text-violet-500">
      Custom
    </span>
  );
}

const FIELD_LABEL = "mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground";
const FIELD_INPUT =
  "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground";

export default function AgentsClient() {
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [harnesses, setHarnesses] = useState<Record<number, HarnessData>>({});
  const [verdicts, setVerdicts] = useState<Record<number, string>>({});
  const [selected, setSelected] = useState<number | null>(null);
  const [apiUp, setApiUp] = useState(true);
  const [loaded, setLoaded] = useState(false);

  /* Create-agent form state. Department/family/tier/price options come
   * from GET /agents/catalog; the submit goes to POST /agents and the
   * new agent joins the roster below like any other hire. */
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [fName, setFName] = useState("");
  const [fDept, setFDept] = useState("");
  const [fFamily, setFFamily] = useState("");
  const [fTier, setFTier] = useState("balanced");
  const [fPrice, setFPrice] = useState(1);
  const [fAddendum, setFAddendum] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

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
    (async () => {
      try {
        setCatalog((await fetchJSON("/agents/catalog")) as Catalog);
      } catch {
        setCatalog(null);
      }
    })();
  }, []);

  useEffect(() => {
    if (selected === null && agents.length > 0) setSelected(agents[0].id);
  }, [agents, selected]);

  useEffect(() => {
    if (catalog && !fDept && catalog.departments.length > 0) {
      setFDept(catalog.departments[0].key);
      setFFamily(catalog.departments[0].families[0]?.key ?? "");
    }
  }, [catalog, fDept]);

  /* Deep links from the newer pages: the Directory points here with
   * ?agent=<id> to open that agent's profile, and the Hire gallery
   * with ?create=1&department=<key>&family=<key> to open the create
   * form on a preselected role. Both apply once the roster / catalogue
   * they depend on has loaded (declared after the default-selection
   * effects above so the explicit link wins). */
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const agentParam = params.get("agent");
    if (agentParam && agents.length > 0) {
      const id = Number(agentParam);
      if (agents.some((a) => a.id === id)) setSelected(id);
    }
  }, [agents]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("create") !== "1" || !catalog) return;
    const deptObjParam = catalog.departments.find((d) => d.key === params.get("department"));
    if (deptObjParam) {
      setFDept(deptObjParam.key);
      const famKey = params.get("family");
      if (famKey && deptObjParam.families.some((f) => f.key === famKey)) setFFamily(famKey);
      else if (deptObjParam.families.length > 0) setFFamily(deptObjParam.families[0].key);
    }
    setFormOpen(true);
  }, [catalog]);

  const deptObj = catalog?.departments.find((d) => d.key === fDept) ?? null;
  const famObj = deptObj?.families.find((f) => f.key === fFamily) ?? null;

  const onDeptChange = (key: string) => {
    setFDept(key);
    const d = catalog?.departments.find((x) => x.key === key);
    if (d && d.families.length > 0) setFFamily(d.families[0].key);
  };

  const createAgent = async () => {
    if (!deptObj || !famObj) return;
    setCreating(true);
    setCreateError(null);
    try {
      const r = await fetch(`${API_BASE}/agents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: fName.trim(),
          department: deptObj.key,
          job_family: famObj.key,
          model_tier: fTier,
          price: fPrice,
          charter_addendum: fAddendum.trim(),
        }),
      });
      const data = (await r.json().catch(() => ({}))) as {
        detail?: unknown;
        agent?: AgentRow;
      };
      if (!r.ok) {
        let msg = `Could not create the agent (${r.status}).`;
        if (typeof data.detail === "string") msg = data.detail;
        else if (data.detail && typeof data.detail === "object") {
          const d = data.detail as Record<string, unknown>;
          if (typeof d.error === "string") msg = d.error;
        }
        throw new Error(msg);
      }
      const newId = data.agent?.id;
      setFName("");
      setFAddendum("");
      setFormOpen(false);
      await refresh();
      if (newId != null) setSelected(newId);
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : "Could not create the agent.");
    } finally {
      setCreating(false);
    }
  };

  const priceNote =
    fPrice === 1
      ? "Prices its bids like a typical agent."
      : fPrice < 1
        ? `Bids about ${Math.round((1 - fPrice) * 100)}% cheaper than a typical agent — wins more work, earns less per job.`
        : `Bids about ${Math.round((fPrice - 1) * 100)}% dearer than a typical agent — wins less work, earns more per job.`;

  const familyTitleByKey = useMemo(() => {
    const m = new Map<string, string>();
    for (const d of catalog?.departments ?? [])
      for (const f of d.families) m.set(f.key, f.title);
    return m;
  }, [catalog]);

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
      <header className="flex items-start justify-between gap-4 border-b border-border px-6 py-4">
        <div>
          <h1 className="font-display text-2xl">Agents</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Everyone on the roster — their harness, their record, and what they have learned.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setFormOpen((o) => !o)}
          className="shrink-0 rounded-lg bg-primary px-3.5 py-2 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
        >
          {formOpen ? "Close form" : "Create agent"}
        </button>
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

        {formOpen && (
          <section className="mb-4 rounded-xl border border-border bg-card p-5">
            <h2 className="text-lg font-semibold">Create an agent</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Design a specialist: pick its department and role, choose a model tier, and set
              its price. It joins the roster at reputation 50 and bids on its role&apos;s jobs
              from the next cycle — reviewed, paid, and fired by the same rules as everyone
              else.
            </p>
            {catalog === null ? (
              <p className="mt-4 text-sm text-muted-foreground">
                The catalogue could not be loaded — the API is unreachable, so the form is
                unavailable.
              </p>
            ) : (
              <>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <div>
                    <label htmlFor="ca-name" className={FIELD_LABEL}>
                      Name
                    </label>
                    <input
                      id="ca-name"
                      className={FIELD_INPUT}
                      value={fName}
                      onChange={(e) => setFName(e.target.value)}
                      placeholder="e.g. Nova"
                      maxLength={40}
                    />
                  </div>
                  <div>
                    <label htmlFor="ca-tier" className={FIELD_LABEL}>
                      Model tier
                    </label>
                    <select
                      id="ca-tier"
                      className={FIELD_INPUT}
                      value={fTier}
                      onChange={(e) => setFTier(e.target.value)}
                    >
                      {catalog.model_tiers.map((t) => (
                        <option key={t.key} value={t.key}>
                          {t.label} — {t.blurb}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label htmlFor="ca-dept" className={FIELD_LABEL}>
                      Department
                    </label>
                    <select
                      id="ca-dept"
                      className={FIELD_INPUT}
                      value={deptObj?.key ?? ""}
                      onChange={(e) => onDeptChange(e.target.value)}
                    >
                      {catalog.departments.map((d) => (
                        <option key={d.key} value={d.key}>
                          {d.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label htmlFor="ca-family" className={FIELD_LABEL}>
                      Role (job family)
                    </label>
                    <select
                      id="ca-family"
                      className={FIELD_INPUT}
                      value={famObj?.key ?? ""}
                      onChange={(e) => setFFamily(e.target.value)}
                    >
                      {(deptObj?.families ?? []).map((f) => (
                        <option key={f.key} value={f.key}>
                          {f.title}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="mt-4">
                  <label htmlFor="ca-price" className={FIELD_LABEL}>
                    Price style — ×{fPrice.toFixed(2)}
                  </label>
                  <div className="flex items-center gap-3">
                    <span className="text-2xs text-muted-foreground">
                      Charges less, wins more work
                    </span>
                    <input
                      id="ca-price"
                      type="range"
                      min={catalog.price.min}
                      max={catalog.price.max}
                      step={catalog.price.step}
                      value={fPrice}
                      onChange={(e) => setFPrice(Number(e.target.value))}
                      className="flex-1"
                      style={{ accentColor: "#cc785c" }}
                    />
                    <span className="text-2xs text-muted-foreground">
                      Charges more, wins less
                    </span>
                    <input
                      type="number"
                      aria-label="Price multiplier"
                      min={catalog.price.min}
                      max={catalog.price.max}
                      step={catalog.price.step}
                      value={fPrice}
                      onChange={(e) => setFPrice(Number(e.target.value))}
                      className="w-20 rounded-lg border border-border bg-background px-2 py-1.5 text-sm text-foreground"
                    />
                  </div>
                  <p className="mt-1 text-2xs text-muted-foreground">
                    {catalog.price.meaning} {priceNote}
                  </p>
                </div>

                <div className="mt-4">
                  <label htmlFor="ca-addendum" className={FIELD_LABEL}>
                    Extra instructions for this agent (optional)
                  </label>
                  <textarea
                    id="ca-addendum"
                    className={FIELD_INPUT}
                    rows={3}
                    value={fAddendum}
                    onChange={(e) => setFAddendum(e.target.value)}
                    maxLength={catalog.charter_addendum_max_chars}
                    placeholder="Added to the agent's charter, on top of its role template."
                  />
                </div>

                {famObj && deptObj && (
                  <p className="mt-4 rounded-lg border border-border bg-background px-3 py-2 text-sm text-muted-foreground">
                    <span className="text-foreground">{fName.trim() || "Your agent"}</span>{" "}
                    will bid on {deptObj.label} · {famObj.title} jobs with{" "}
                    {famObj.tool_count} tools, pricing its bids at ×{fPrice.toFixed(2)} of a
                    typical agent.
                  </p>
                )}
                {createError && (
                  <p className="mt-3 rounded-lg border border-destructive/40 bg-background px-3 py-2 text-sm text-destructive">
                    {createError}
                  </p>
                )}
                <div className="mt-4 flex justify-end">
                  <button
                    type="button"
                    onClick={() => void createAgent()}
                    disabled={creating || !fName.trim() || !famObj}
                    className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {creating ? "Creating…" : "Create agent"}
                  </button>
                </div>
              </>
            )}
          </section>
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
                    {a.origin === "user-created" && <CustomPill />}
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
                    <span>price ×{(a.price_factor ?? 1).toFixed(2)}</span>
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
                  {sel.origin === "user-created" && <CustomPill />}
                  <span className="text-sm text-muted-foreground">
                    {DEPT_LABELS[selH.harness.department] ?? selH.harness.department} ·{" "}
                    {selH.harness.role_label} · {selH.harness.model_tier} tier · {sel.model}
                    {" · "}price ×{(sel.price_factor ?? 1).toFixed(2)}
                  </span>
                </div>

                {sel.origin === "user-created" && (
                  <p className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-muted-foreground">
                    Custom agent — created by the operator
                    {sel.family_key && familyTitleByKey.get(sel.family_key)
                      ? ` for ${familyTitleByKey.get(sel.family_key)}`
                      : ""}
                    . It bids only on that role&apos;s jobs, at ×
                    {(sel.price_factor ?? 1).toFixed(2)} of a typical agent&apos;s price, and
                    works with that desk&apos;s tools only.
                  </p>
                )}

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
