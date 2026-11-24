"use client";

/* Connections — the OutboundAI flow, adapted to the floor
 * (OutboundAI: frontend/src/pages/Integrations.tsx):
 * a searchable, category-filtered CATALOG of apps; each card carries
 * its live status merged from the backend; Connect opens a
 * department picker, then the provider's real connect flow runs —
 * Composio returns an OAuth redirect URL, ExtDesk creates a real
 * localdesk connection. Connected apps sort first.
 *
 * Honesty rules, unchanged from the layer beneath:
 * - Composio without COMPOSIO_API_KEY answers a structured 422
 *   not_configured; the card shows that exact state. Nothing here
 *   fakes a connection, a redirect, or a success toast.
 * - ExtDesk is the SIMULATOR provider and is labelled as one on its
 *   card, its connection, and its activity — it is not Jira.
 * - The test-report form lives inside the ExtDesk connection's
 *   activity area, because that is the demo intake loop. */

import { useCallback, useEffect, useMemo, useState } from "react";
import { API_BASE, credits } from "../lib/api";

type CatalogConnection = {
  id: string;
  provider: string;
  app: string;
  label: string;
  status: string;
  department: string | null;
  test_only: boolean;
  created_at: string;
  remote_status?: string | null;
};

type CatalogApp = {
  slug: string;
  name: string;
  provider: string;
  category: string;
  blurb: string;
  simulator?: boolean;
  suggested_department: string;
  provider_configured: boolean;
  provider_detail: string;
  status: "connected" | "pending" | "available" | "not_configured";
  connection: CatalogConnection | null;
  reason?: string;
};

type Connection = {
  id: string;
  provider: string;
  app: string;
  label: string;
  status: string;
  test_only: boolean | number;
  department: string | null;
  created_at: string;
};

type Grant = { connection_id: string; department: string; tool_name: string };
type ToolSpec = { name: string; effect: string; description: string };

type IntakeEvent = {
  id: number;
  connection_id: string | null;
  provider: string;
  app: string;
  external_issue_id: string;
  title: string;
  department: string;
  job_id: number | null;
  winner: string | null;
  verdict: string | null;
  paid_credits: number | null;
  status: string;
  created_at: string;
};

const DEPT_LABELS: Record<string, string> = {
  support: "Support",
  qa: "QA triage",
  bookkeeping: "Bookkeeping",
  sdr: "SDR",
  engineering: "Engineering",
  hr: "HR",
  seo: "SEO",
};

const STATUS_ORDER: Record<CatalogApp["status"], number> = {
  connected: 0,
  pending: 1,
  available: 2,
  not_configured: 3,
};

async function fetchJSON(path: string): Promise<unknown> {
  const r = await fetch(`${API_BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

function detailText(data: Record<string, unknown>, fallback: string): string {
  const d = data.detail;
  if (typeof d === "string") return d;
  if (d && typeof d === "object") {
    const inner = (d as Record<string, unknown>).detail;
    if (typeof inner === "string") return inner;
  }
  return fallback;
}

async function sendJSON(path: string, method: string, body?: unknown): Promise<unknown> {
  const r = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = (await r.json().catch(() => ({}))) as Record<string, unknown>;
  if (!r.ok) throw new Error(detailText(data, `${path} -> ${r.status}`));
  return data;
}

function initials(name: string): string {
  return name.replace(/[^A-Za-z ]/g, "").split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();
}

function StatusPill({ app }: { app: CatalogApp }) {
  if (app.status === "connected") {
    return app.simulator ? (
      <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-2xs font-semibold text-amber-500">
        SIMULATOR · Connected
      </span>
    ) : (
      <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-2xs font-semibold text-emerald-500">
        Connected
      </span>
    );
  }
  if (app.status === "pending") {
    return (
      <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-2xs font-semibold text-amber-500">
        Pending — finish OAuth
      </span>
    );
  }
  if (app.status === "available") {
    return (
      <span className="rounded-full bg-sky-500/15 px-2 py-0.5 text-2xs font-semibold text-sky-500">
        Available
      </span>
    );
  }
  return (
    <span className="rounded-full bg-zinc-500/15 px-2 py-0.5 text-2xs font-semibold text-zinc-400">
      Needs setup
    </span>
  );
}

export default function ConnectionsClient() {
  const [apps, setApps] = useState<CatalogApp[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [departments, setDepartments] = useState<string[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [grants, setGrants] = useState<Grant[]>([]);
  const [events, setEvents] = useState<IntakeEvent[]>([]);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");
  const [selected, setSelected] = useState<string | null>(null);
  const [tools, setTools] = useState<ToolSpec[]>([]);
  const [grantDept, setGrantDept] = useState("engineering");
  const [picker, setPicker] = useState<{ app: CatalogApp; department: string } | null>(null);
  const [cardMsg, setCardMsg] = useState<Record<string, string>>({});
  const [busySlug, setBusySlug] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ text: string; error?: boolean } | null>(null);
  const [apiUp, setApiUp] = useState(true);
  const [bugTitle, setBugTitle] = useState("");
  const [bugBody, setBugBody] = useState("");
  const [bugSeverity, setBugSeverity] = useState("high");
  const [deptDraft, setDeptDraft] = useState("");

  const refresh = useCallback(async () => {
    try {
      const cat = (await fetchJSON("/connections/catalog")) as {
        apps: CatalogApp[];
        categories: string[];
        departments: string[];
      };
      setApps(cat.apps ?? []);
      setCategories(cat.categories ?? []);
      setDepartments(cat.departments ?? []);
      const d = (await fetchJSON("/connections")) as {
        connections: Connection[];
        grants: Grant[];
      };
      setConnections(d.connections ?? []);
      setGrants(d.grants ?? []);
      const ev = (await fetchJSON("/intake/events")) as { events: IntakeEvent[] };
      setEvents(ev.events ?? []);
      setApiUp(true);
    } catch {
      setApiUp(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const selectedConn = connections.find((c) => c.id === selected) ?? null;
  const selectedApp = selectedConn
    ? apps.find(
        (a) =>
          a.connection?.id === selectedConn.id ||
          (selectedConn.provider === "localdesk" && a.provider === "localdesk") ||
          (selectedConn.provider === "composio" && a.slug === selectedConn.app),
      ) ?? null
    : null;

  useEffect(() => {
    setDeptDraft(selectedConn?.department ?? "");
    if (!selected) {
      setTools([]);
      return;
    }
    void (async () => {
      try {
        const d = (await fetchJSON(`/connections/${selected}/tools`)) as { tools: ToolSpec[] };
        setTools(d.tools ?? []);
      } catch {
        setTools([]);
      }
    })();
  }, [selected, grants, selectedConn?.department]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return apps
      .filter((a) => category === "All" || a.category === category)
      .filter(
        (a) =>
          !q ||
          a.name.toLowerCase().includes(q) ||
          a.blurb.toLowerCase().includes(q),
      )
      .sort(
        (x, y) =>
          STATUS_ORDER[x.status] - STATUS_ORDER[y.status] ||
          x.name.localeCompare(y.name),
      );
  }, [apps, category, search]);

  const openPicker = (app: CatalogApp) => {
    setCardMsg((m) => ({ ...m, [app.slug]: "" }));
    setPicker({ app, department: app.connection?.department ?? app.suggested_department });
  };

  const runConnect = async () => {
    if (!picker) return;
    const { app, department } = picker;
    setPicker(null);
    setBusySlug(app.slug);
    setCardMsg((m) => ({ ...m, [app.slug]: "" }));
    try {
      if (app.provider === "localdesk") {
        const res = (await sendJSON("/connections", "POST", {
          provider: "localdesk",
          app: "jira",
          label: "ExtDesk (simulator)",
          department,
        })) as { connection: Connection };
        const conn = res.connection;
        // Connecting an app to a department grants that department the
        // app's tools — that grant is what lets its workers run the
        // intake loop through this connection.
        try {
          const t = (await fetchJSON(`/connections/${conn.id}/tools`)) as { tools: ToolSpec[] };
          for (const tool of t.tools ?? []) {
            await sendJSON(`/connections/${conn.id}/grants`, "POST", {
              department,
              tool_name: tool.name,
            });
          }
        } catch {
          /* grants stay manageable by hand in the detail panel */
        }
        await refresh();
        setSelected(conn.id);
        setMsg({ text: `ExtDesk connected to ${DEPT_LABELS[department] ?? department} (simulator — local data only).` });
      } else {
        const res = (await sendJSON("/connections/composio/connect", "POST", {
          app: app.slug,
          department,
        })) as { redirect_url?: string | null };
        if (res.redirect_url) {
          window.location.href = res.redirect_url;
          return;
        }
        await refresh();
        setCardMsg((m) => ({
          ...m,
          [app.slug]: "Composio did not return an OAuth redirect URL for this app.",
        }));
      }
    } catch (e) {
      setCardMsg((m) => ({
        ...m,
        [app.slug]: e instanceof Error ? e.message : String(e),
      }));
    } finally {
      setBusySlug(null);
    }
  };

  const act = useCallback(
    async (fn: () => Promise<unknown>, ok: string) => {
      setBusy(true);
      setMsg(null);
      try {
        await fn();
        setMsg({ text: ok });
        await refresh();
      } catch (e) {
        setMsg({ text: e instanceof Error ? e.message : String(e), error: true });
      } finally {
        setBusy(false);
      }
    },
    [refresh],
  );

  const selectedGrants = grants.filter((g) => g.connection_id === selected);
  const selectedEvents = events.filter((e) => e.connection_id === selected);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto bg-background text-foreground">
      <header className="border-b border-border px-6 py-4">
        <h1 className="font-display text-2xl">Connections</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Connect the tools your company already uses — work arrives here, and results go back.
        </p>
      </header>

      <main className="mx-auto max-w-6xl space-y-8 px-6 py-6">
        {!apiUp && (
          <div className="rounded-lg border border-destructive/40 bg-popover px-4 py-3 text-sm text-destructive">
            The floor API is not reachable at {API_BASE}. Connections need the API server running.
          </div>
        )}
        {msg && (
          <div
            className={`rounded-lg border px-4 py-3 text-sm ${
              msg.error
                ? "border-destructive/40 bg-popover text-destructive"
                : "border-border bg-popover text-popover-foreground"
            }`}
            role="status"
          >
            {msg.text}
          </div>
        )}

        {/* Search + category chips */}
        <section className="space-y-3">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search apps…"
            className="w-full rounded-md border border-border bg-card px-3 py-2 text-sm"
            aria-label="Search apps"
          />
          <div className="flex flex-wrap gap-2">
            {["All", ...categories].map((c) => {
              const n = c === "All" ? apps.length : apps.filter((a) => a.category === c).length;
              const active = category === c;
              return (
                <button
                  key={c}
                  type="button"
                  onClick={() => setCategory(c)}
                  aria-pressed={active}
                  className={`rounded-full border px-2.5 py-1 text-2xs font-medium transition-colors ${
                    active
                      ? "border-transparent bg-primary text-primary-foreground"
                      : "border-border text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {c}
                  <span className="ml-1.5 font-mono tabular-nums opacity-75">{n}</span>
                </button>
              );
            })}
          </div>
        </section>

        {/* Catalog grid */}
        <section>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((app) => (
              <div
                key={app.slug}
                className={`flex flex-col rounded-xl border bg-card p-4 ${
                  app.connection && selected === app.connection.id
                    ? "border-primary"
                    : "border-border"
                }`}
              >
                <div className="mb-3 flex items-start justify-between">
                  <span className="flex size-10 items-center justify-center rounded-lg bg-muted/60 text-sm font-bold">
                    {initials(app.name)}
                  </span>
                  <span className="rounded-full bg-zinc-500/15 px-2 py-0.5 text-2xs font-medium text-muted-foreground">
                    {app.category}
                  </span>
                </div>
                <h3 className="text-base font-semibold">{app.name}</h3>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{app.blurb}</p>
                <p className="mt-2 text-2xs text-muted-foreground">
                  Feeds{" "}
                  <span className="font-medium text-foreground">
                    {DEPT_LABELS[app.connection?.department ?? app.suggested_department] ??
                      app.suggested_department}
                  </span>
                  {app.provider === "composio" ? " · via Composio" : " · built-in simulator"}
                </p>

                <div className="mt-auto pt-4">
                  <div className="flex items-center gap-2">
                    <StatusPill app={app} />
                    <span className="ml-auto">
                      {app.connection ? (
                        <button
                          type="button"
                          onClick={() => setSelected(app.connection!.id)}
                          className="rounded-md border border-border px-3 py-1.5 text-xs font-medium hover:text-foreground"
                        >
                          Manage
                        </button>
                      ) : (
                        <button
                          type="button"
                          disabled={busySlug === app.slug}
                          onClick={() => openPicker(app)}
                          className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50"
                        >
                          {busySlug === app.slug ? "Connecting…" : "Connect"}
                        </button>
                      )}
                    </span>
                  </div>
                  {app.status === "not_configured" && app.provider === "composio" && (
                    <p className="mt-2 text-2xs leading-relaxed text-muted-foreground">
                      Live connect needs a Composio API key — add{" "}
                      <code className="font-mono">COMPOSIO_API_KEY</code> and this button goes live.
                    </p>
                  )}
                  {app.status === "not_configured" && app.provider === "localdesk" && app.reason && (
                    <p className="mt-2 text-2xs leading-relaxed text-muted-foreground">{app.reason}</p>
                  )}
                  {app.status === "pending" && (
                    <p className="mt-2 text-2xs leading-relaxed text-muted-foreground">
                      Finish the OAuth flow in Composio — this card flips to Connected on its own
                      once Composio reports the account ACTIVE.
                    </p>
                  )}
                  {cardMsg[app.slug] && (
                    <p className="mt-2 rounded-md border border-destructive/40 bg-popover px-2.5 py-2 text-2xs leading-relaxed text-destructive" role="alert">
                      {cardMsg[app.slug]}
                    </p>
                  )}
                </div>
              </div>
            ))}
            {filtered.length === 0 && (
              <div className="text-sm text-muted-foreground">
                <p>
                  No apps match
                  {search.trim() ? ` “${search.trim()}”` : " these filters"}
                  {category !== "All" ? ` in ${category}` : ""}.
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setSearch("");
                    setCategory("All");
                  }}
                  className="mt-2 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-interactive-hover"
                >
                  Clear search & filters
                </button>
              </div>
            )}
          </div>
        </section>

        {/* Selected connection detail */}
        {selectedConn && (
          <section className="space-y-4 rounded-xl border border-border bg-card p-5">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-semibold capitalize">
                {selectedApp?.name ?? selectedConn.app} — {selectedConn.label}
              </h2>
              <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-2xs font-semibold text-emerald-500">
                {selectedConn.status}
              </span>
              <span className="text-2xs text-muted-foreground">via {selectedConn.provider}</span>
              {Boolean(selectedConn.test_only) && (
                <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-2xs font-semibold uppercase tracking-wide text-amber-500">
                  Simulator — local data only
                </span>
              )}
              <span className="ml-auto">
                <button
                  type="button"
                  disabled={busy}
                  className="rounded-md border border-destructive/40 px-3 py-1.5 text-xs font-medium text-destructive disabled:opacity-50"
                  onClick={() =>
                    void act(async () => {
                      await sendJSON(`/connections/${selectedConn.id}`, "DELETE");
                      setSelected(null);
                    }, "Connection disconnected.")
                  }
                >
                  Disconnect
                </button>
              </span>
            </div>

            {selectedApp?.provider_detail && (
              <p className="text-sm text-muted-foreground">{selectedApp.provider_detail}</p>
            )}

            {/* Department mapping */}
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <label htmlFor="conn-dept" className="font-medium">
                Feeds department
              </label>
              <select
                id="conn-dept"
                value={deptDraft}
                onChange={(e) => setDeptDraft(e.target.value)}
                className="rounded-md border border-border bg-background px-2 py-1.5"
              >
                <option value="">Routed per item (COO router)</option>
                {departments.map((d) => (
                  <option key={d} value={d}>
                    {DEPT_LABELS[d] ?? d}
                  </option>
                ))}
              </select>
              <button
                type="button"
                disabled={busy || deptDraft === (selectedConn.department ?? "")}
                className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50"
                onClick={() =>
                  void act(
                    () => sendJSON(`/connections/${selectedConn.id}`, "PATCH", { department: deptDraft }),
                    "Department mapping saved.",
                  )
                }
              >
                Save
              </button>
              <span className="text-2xs text-muted-foreground">
                Incoming work on this connection is posted to this department.
              </span>
            </div>

            {/* Tools & grants */}
            <div>
              <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Tools & department grants
              </h3>
              <div className="mb-3 flex items-center gap-2 text-sm">
                <label htmlFor="grant-dept">Grant to department</label>
                <select
                  id="grant-dept"
                  value={grantDept}
                  onChange={(e) => setGrantDept(e.target.value)}
                  className="rounded-md border border-border bg-background px-2 py-1"
                >
                  {departments.map((d) => (
                    <option key={d} value={d}>
                      {DEPT_LABELS[d] ?? d}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                {tools.map((t) => {
                  const granted = selectedGrants.some(
                    (g) => g.tool_name === t.name && g.department === grantDept,
                  );
                  return (
                    <div
                      key={t.name}
                      className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-background p-3"
                    >
                      <code className="font-mono text-sm">{t.name}</code>
                      <span
                        className={`rounded-full px-2 py-0.5 text-2xs font-semibold ${
                          t.effect === "write"
                            ? "bg-amber-500/15 text-amber-500"
                            : "bg-sky-500/15 text-sky-500"
                        }`}
                      >
                        {t.effect}
                      </span>
                      <span className="text-sm text-muted-foreground">{t.description}</span>
                      <span className="ml-auto">
                        {granted ? (
                          <button
                            type="button"
                            disabled={busy}
                            className="text-sm text-destructive disabled:opacity-50"
                            onClick={() =>
                              void act(
                                () =>
                                  sendJSON(
                                    `/connections/${selectedConn.id}/grants?department=${grantDept}&tool_name=${t.name}`,
                                    "DELETE",
                                  ),
                                `Revoked ${t.name} from ${grantDept}.`,
                              )
                            }
                          >
                            Revoke from {grantDept}
                          </button>
                        ) : (
                          <button
                            type="button"
                            disabled={busy}
                            className="rounded-md bg-primary px-3 py-1 text-sm font-medium text-primary-foreground disabled:opacity-50"
                            onClick={() =>
                              void act(
                                () =>
                                  sendJSON(`/connections/${selectedConn.id}/grants`, "POST", {
                                    department: grantDept,
                                    tool_name: t.name,
                                  }),
                                `Granted ${t.name} to ${grantDept}.`,
                              )
                            }
                          >
                            Grant to {grantDept}
                          </button>
                        )}
                      </span>
                    </div>
                  );
                })}
                {tools.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    No tool catalog available for this connection
                    {selectedConn.provider === "composio"
                      ? " — Composio is unconfigured, so its catalog cannot be fetched."
                      : "."}
                  </p>
                )}
              </div>
              {selectedGrants.length > 0 && (
                <p className="mt-3 text-sm text-muted-foreground">
                  Active grants:{" "}
                  {selectedGrants.map((g) => `${g.department}:${g.tool_name}`).join(" · ")}
                </p>
              )}
            </div>

            {/* Intake activity for this connection */}
            <div>
              <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Intake activity — work that arrived through this connection
              </h3>

              {selectedConn.provider === "localdesk" && (
                <div className="mb-4 rounded-lg border border-border bg-background p-4">
                  <p className="text-sm text-muted-foreground">
                    Send a test report through ExtDesk. It becomes a job in the mapped
                    department, runs through bidding, execution (through the granted
                    connection tools), review and payment — and on completion the
                    ExtDesk issue is moved to Done with a resolution comment. The loop
                    is real; the data is the simulator's.
                  </p>
                  <div className="mt-3 grid gap-2">
                    <input
                      value={bugTitle}
                      onChange={(e) => setBugTitle(e.target.value)}
                      placeholder="Report title — e.g. Checkout page goes blank after payment"
                      className="rounded-md border border-border bg-card px-3 py-2 text-sm"
                    />
                    <textarea
                      value={bugBody}
                      onChange={(e) => setBugBody(e.target.value)}
                      placeholder="What happens? Steps to reproduce…"
                      rows={3}
                      className="rounded-md border border-border bg-card px-3 py-2 text-sm"
                    />
                    <div className="flex items-center gap-2">
                      <label htmlFor="bug-severity" className="text-sm">
                        Severity
                      </label>
                      <select
                        id="bug-severity"
                        value={bugSeverity}
                        onChange={(e) => setBugSeverity(e.target.value)}
                        className="rounded-md border border-border bg-card px-2 py-1.5 text-sm"
                      >
                        {["critical", "high", "medium", "low"].map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        disabled={busy || !bugTitle.trim()}
                        onClick={() =>
                          void act(async () => {
                            await sendJSON(`/intake/${selectedConn.id}`, "POST", {
                              title: bugTitle.trim(),
                              body: bugBody,
                              severity: bugSeverity,
                            });
                            setBugTitle("");
                            setBugBody("");
                          }, "Report ran through the floor — see the activity list below.")
                        }
                        className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-50"
                      >
                        {busy ? "Running the job…" : "Send test report"}
                      </button>
                    </div>
                  </div>
                </div>
              )}

              <div className="space-y-2">
                {selectedEvents.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    No intake activity on this connection yet.
                  </p>
                )}
                {selectedEvents.map((e) => (
                  <div key={e.id} className="rounded-lg border border-border bg-background p-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{e.title}</span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-2xs font-semibold ${
                          e.status === "completed"
                            ? "bg-emerald-500/15 text-emerald-500"
                            : e.status === "failed"
                              ? "bg-red-500/15 text-red-500"
                              : "bg-amber-500/15 text-amber-500"
                        }`}
                      >
                        {e.status}
                      </span>
                      <span className="text-2xs text-muted-foreground">
                        issue #{e.external_issue_id} → {DEPT_LABELS[e.department] ?? e.department}
                        {e.job_id ? ` · job #${e.job_id}` : ""}
                        {e.winner ? ` · ${e.winner}` : ""}
                        {e.verdict ? ` · ${e.verdict}` : ""}
                        {e.paid_credits != null ? ` · paid ${credits(e.paid_credits)}` : ""}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}
      </main>

      {/* Department picker dialog */}
      {picker && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4"
          role="dialog"
          aria-modal="true"
          aria-label={`Connect ${picker.app.name}`}
          onClick={() => setPicker(null)}
        >
          <div
            className="w-full max-w-md rounded-xl border border-border bg-card p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-lg font-semibold">Connect {picker.app.name}</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Which department should {picker.app.name} feed? Incoming work is posted
              there; you can change this later.
            </p>
            <div className="mt-4 space-y-1.5">
              {departments.map((d) => (
                <label
                  key={d}
                  className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
                    picker.department === d
                      ? "border-primary bg-background"
                      : "border-border hover:bg-background"
                  }`}
                >
                  <input
                    type="radio"
                    name="picker-department"
                    checked={picker.department === d}
                    onChange={() => setPicker({ ...picker, department: d })}
                    className="accent-[#cc785c]"
                  />
                  <span className="font-medium">{DEPT_LABELS[d] ?? d}</span>
                  {d === picker.app.suggested_department && (
                    <span className="ml-auto text-2xs text-muted-foreground">suggested</span>
                  )}
                </label>
              ))}
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setPicker(null)}
                className="rounded-md border border-border px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void runConnect()}
                className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground"
              >
                Connect {picker.app.name}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
