"use client";

/* Connections page (DESIGN_NOTES §2 + §3): external app connections,
   per-department tool grants, and the intake activity list.
   Honesty rules baked into the UI:
   - the composio provider shows "Composio API key required" until the
     API server reports it configured — no fake connect state;
   - the local_test provider and its connections are badged TEST in
     every place they appear, because their data lives in a local store
     and no real Jira/Slack/Gmail is ever touched. */

import { useCallback, useEffect, useState } from "react";
import { API_BASE, credits } from "../lib/api";

type ProviderStatus = {
  name: string;
  configured: boolean;
  detail: string;
  test_only: boolean;
  apps: string[];
};

type Connection = {
  id: string;
  provider: string;
  app: string;
  label: string;
  status: string;
  test_only: boolean | number;
  created_at: string;
};

type Grant = { connection_id: string; department: string; tool_name: string };

type ToolSpec = { name: string; effect: string; description: string };

type IntakeEvent = {
  id: number;
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

const DEPARTMENTS = ["support", "qa", "bookkeeping", "sdr", "engineering", "hr"];

async function fetchJSON(path: string): Promise<unknown> {
  const r = await fetch(`${API_BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

async function sendJSON(path: string, method: string, body?: unknown): Promise<unknown> {
  const r = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = (await r.json().catch(() => ({}))) as Record<string, unknown>;
  if (!r.ok) throw new Error(String(data.detail ?? `${path} -> ${r.status}`));
  return data;
}

function TestBadge() {
  return (
    <span className="ml-2 rounded-full bg-amber-500/15 px-2 py-0.5 text-2xs font-semibold uppercase tracking-wide text-amber-500">
      Test connection — local data only
    </span>
  );
}

export default function ConnectionsClient() {
  const [providers, setProviders] = useState<ProviderStatus[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [grants, setGrants] = useState<Grant[]>([]);
  const [events, setEvents] = useState<IntakeEvent[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [tools, setTools] = useState<ToolSpec[]>([]);
  const [dept, setDept] = useState("engineering");
  const [bugTitle, setBugTitle] = useState("");
  const [bugBody, setBugBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ text: string; error?: boolean } | null>(null);
  const [apiUp, setApiUp] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const d = (await fetchJSON("/connections")) as {
        providers: ProviderStatus[];
        connections: Connection[];
        grants: Grant[];
      };
      setProviders(d.providers ?? []);
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

  useEffect(() => {
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
  }, [selected, grants]);

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

  const composio = providers.find((p) => p.name === "composio");
  const selectedConn = connections.find((c) => c.id === selected) ?? null;
  const selectedGrants = grants.filter((g) => g.connection_id === selected);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border px-6 py-4">
        <div className="flex flex-wrap items-baseline gap-3">
          <a href="/console" className="text-sm text-muted-foreground hover:text-foreground">
            ← Console
          </a>
          <h1 className="font-display text-2xl">Connections</h1>
          <span className="text-sm text-muted-foreground">
            External apps the floor can work in — and the intake loop that turns reports into jobs.
          </span>
        </div>
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

        {/* Providers */}
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Providers
          </h2>
          <div className="grid gap-3 md:grid-cols-2">
            {providers.map((p) => (
              <div key={p.name} className="rounded-lg border border-border bg-card p-4">
                <div className="flex items-center justify-between">
                  <span className="font-medium capitalize">{p.name.replace("_", " ")}</span>
                  {p.test_only ? (
                    <TestBadge />
                  ) : p.configured ? (
                    <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-2xs font-semibold text-emerald-500">
                      Configured
                    </span>
                  ) : (
                    <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-2xs font-semibold text-amber-500">
                      Composio API key required
                    </span>
                  )}
                </div>
                <p className="mt-2 text-sm text-muted-foreground">{p.detail}</p>
                {p.name === "composio" && !p.configured && (
                  <p className="mt-2 text-sm">
                    To connect real apps: create a Composio account, connect Jira / Slack /
                    Gmail / GitHub there (OAuth), then set{" "}
                    <code className="font-mono text-xs">COMPOSIO_API_KEY</code> on the API server
                    and restart it. Until then this provider refuses to connect — nothing is
                    simulated.
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Connections */}
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Connections
            </h2>
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                void act(
                  () => sendJSON("/connections", "POST", { provider: "local_test", app: "jira" }),
                  "Test Jira connection created (local store only).",
                )
              }
              className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              Connect test Jira (local_test)
            </button>
          </div>
          {connections.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No connections yet.
              {composio && !composio.configured
                ? " Real apps need the Composio API key (above); the test provider works now."
                : ""}
            </p>
          )}
          <div className="space-y-2">
            {connections.map((c) => (
              <div
                key={c.id}
                className={`flex flex-wrap items-center gap-2 rounded-lg border p-3 ${
                  selected === c.id ? "border-primary bg-card" : "border-border bg-card"
                }`}
              >
                <button
                  type="button"
                  className="font-medium capitalize"
                  onClick={() => setSelected(c.id)}
                >
                  {c.app} · {c.label}
                </button>
                <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-2xs font-semibold text-emerald-500">
                  {c.status}
                </span>
                <span className="text-2xs text-muted-foreground">via {c.provider}</span>
                {Boolean(c.test_only) && <TestBadge />}
                <span className="ml-auto flex gap-2">
                  <button
                    type="button"
                    className="text-sm text-muted-foreground hover:text-foreground"
                    onClick={() => setSelected(c.id)}
                  >
                    Tools & grants
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    className="text-sm text-destructive disabled:opacity-50"
                    onClick={() =>
                      void act(
                        () => sendJSON(`/connections/${c.id}`, "DELETE"),
                        "Connection deleted.",
                      )
                    }
                  >
                    Delete
                  </button>
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* Tools & grants for the selected connection */}
        {selectedConn && (
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Tools & department grants — {selectedConn.app} via {selectedConn.provider}
              {Boolean(selectedConn.test_only) && <TestBadge />}
            </h2>
            <div className="mb-3 flex items-center gap-2 text-sm">
              <label htmlFor="dept">Grant to department</label>
              <select
                id="dept"
                value={dept}
                onChange={(e) => setDept(e.target.value)}
                className="rounded-md border border-border bg-background px-2 py-1"
              >
                {DEPARTMENTS.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              {tools.map((t) => {
                const granted = selectedGrants.some(
                  (g) => g.tool_name === t.name && g.department === dept,
                );
                return (
                  <div
                    key={t.name}
                    className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-card p-3"
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
                                  `/connections/${selectedConn.id}/grants?department=${dept}&tool_name=${t.name}`,
                                  "DELETE",
                                ),
                              `Revoked ${t.name} from ${dept}.`,
                            )
                          }
                        >
                          Revoke from {dept}
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
                                  department: dept,
                                  tool_name: t.name,
                                }),
                              `Granted ${t.name} to ${dept}.`,
                            )
                          }
                        >
                          Grant to {dept}
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
                Active grants on this connection:{" "}
                {selectedGrants.map((g) => `${g.department}:${g.tool_name}`).join(" · ")}
              </p>
            )}
          </section>
        )}

        {/* Intake */}
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Intake — reports become jobs
          </h2>
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">
              Send a bug report through the selected connection. It becomes an Engineering job,
              runs through bidding, execution (through the granted connection tools), review and
              payment — and on completion the source issue is moved to Done with a comment.
              {selectedConn && Boolean(selectedConn.test_only)
                ? " The selected connection is the TEST provider: the loop is real, the data is local."
                : ""}
            </p>
            <div className="mt-3 grid gap-2">
              <input
                value={bugTitle}
                onChange={(e) => setBugTitle(e.target.value)}
                placeholder="Bug title — e.g. Checkout button does nothing"
                className="rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
              <textarea
                value={bugBody}
                onChange={(e) => setBugBody(e.target.value)}
                placeholder="What happens? Steps to reproduce…"
                rows={3}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
              <div>
                <button
                  type="button"
                  disabled={busy || !selected || !bugTitle.trim()}
                  onClick={() =>
                    void act(async () => {
                      await sendJSON("/intake/events", "POST", {
                        connection_id: selected,
                        event_type: "issue_created",
                        title: bugTitle.trim(),
                        body: bugBody,
                        budget_credits: 150,
                      });
                      setBugTitle("");
                      setBugBody("");
                    }, "Intake job completed — see the activity list below.")
                  }
                  className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-50"
                >
                  {busy ? "Running the job…" : "Send test bug report"}
                </button>
                {!selected && (
                  <span className="ml-2 text-sm text-muted-foreground">
                    Select a connection first.
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="mt-4 space-y-2">
            {events.length === 0 && (
              <p className="text-sm text-muted-foreground">No intake events yet.</p>
            )}
            {events.map((e) => (
              <div key={e.id} className="rounded-lg border border-border bg-card p-3 text-sm">
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
                    {e.app} issue #{e.external_issue_id} → {e.department}
                    {e.job_id ? ` · job #${e.job_id}` : ""}
                    {e.winner ? ` · ${e.winner}` : ""}
                    {e.verdict ? ` · ${e.verdict}` : ""}
                    {e.paid_credits != null ? ` · paid ${credits(e.paid_credits)}` : ""}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
