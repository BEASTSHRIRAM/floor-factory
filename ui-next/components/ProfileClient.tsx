"use client";

/* Profile — the operator + workspace page. Operator identity comes
 * from the local session (lib/session.ts); the display name is
 * editable and saved back to that session. Everything else is live
 * floor state from real endpoints: GET /mode (mode + auto cap),
 * GET /state/ledger (jobs paid + credits paid out, computed from the
 * append-only ledger), GET /state/agents (active roster) and
 * GET /health (department systems online). The reset button calls
 * the real POST /reset; there is no other destructive control here. */

import { useCallback, useEffect, useState } from "react";
import { API_BASE, credits } from "../lib/api";
import {
  getSession,
  operatorInitial,
  setSession,
  type FloorSession,
} from "../lib/session";

async function fetchJSON(path: string): Promise<unknown> {
  const r = await fetch(`${API_BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

async function postJSON(path: string): Promise<unknown> {
  const r = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  const data = (await r.json().catch(() => ({}))) as Record<string, unknown>;
  if (!r.ok) throw new Error(String(data.detail ?? `${path} -> ${r.status}`));
  return data;
}

type Stats = {
  jobsPaid: number;
  totalPaidOut: number;
  activeAgents: number;
  totalAgents: number;
  systemsOnline: number;
  systemsTotal: number;
};

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-2xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 font-mono text-2xl tabular-nums">{value}</p>
      {sub && <p className="mt-0.5 text-2xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

export default function ProfileClient() {
  const [session, setSessionState] = useState<FloorSession | null>(null);
  const [nameDraft, setNameDraft] = useState("");
  const [mode, setMode] = useState<{ mode: string; cap: number | null; autoStatus: string } | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [apiUp, setApiUp] = useState(true);
  const [msg, setMsg] = useState<{ text: string; error?: boolean } | null>(null);
  const [resetting, setResetting] = useState(false);

  useEffect(() => {
    const s = getSession();
    setSessionState(s);
    if (s) setNameDraft(s.displayName);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const m = (await fetchJSON("/mode")) as {
        mode: string;
        auto_run: { status: string; budget_cap_credits: number | null };
      };
      setMode({
        mode: m.mode,
        cap: m.auto_run?.budget_cap_credits ?? null,
        autoStatus: m.auto_run?.status ?? "stopped",
      });
      const ledger = (await fetchJSON("/state/ledger?limit=1000")) as {
        ledger: { kind: string; amount_credits: number; ref_type: string | null; ref_id: number | null }[];
      };
      const rows = ledger.ledger ?? [];
      const paidJobs = new Set(
        rows
          .filter((r) => r.kind === "earning" && r.ref_type === "work_order" && r.ref_id != null)
          .map((r) => r.ref_id),
      );
      const totalPaidOut = rows
        .filter((r) => r.amount_credits > 0)
        .reduce((sum, r) => sum + r.amount_credits, 0);
      const agents = (await fetchJSON("/state/agents")) as {
        agents: { status: string }[];
      };
      const health = (await fetchJSON("/health")) as {
        targets: Record<string, boolean>;
      };
      const targets = Object.values(health.targets ?? {});
      setStats({
        jobsPaid: paidJobs.size,
        totalPaidOut,
        activeAgents: (agents.agents ?? []).filter((a) => a.status === "active").length,
        totalAgents: (agents.agents ?? []).length,
        systemsOnline: targets.filter(Boolean).length,
        systemsTotal: targets.length,
      });
      setApiUp(true);
    } catch {
      setApiUp(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const saveName = () => {
    if (!session) return;
    const name = nameDraft.trim();
    if (!name) {
      setMsg({ text: "Display name cannot be empty.", error: true });
      return;
    }
    const next = { ...session, displayName: name };
    setSession(next);
    setSessionState(next);
    setMsg({ text: "Display name saved to this browser's session." });
  };

  const doReset = async () => {
    setResetting(true);
    setMsg(null);
    try {
      await postJSON("/reset");
      setMsg({ text: "Floor reset to its demo-start state. Connections were kept." });
      await refresh();
    } catch (e) {
      setMsg({ text: e instanceof Error ? e.message : String(e), error: true });
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="min-h-0 flex-1 overflow-y-auto bg-background text-foreground">
      <header className="border-b border-border px-6 py-4">
        <h1 className="font-display text-2xl">Profile</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          You, your workspace, and the floor&apos;s numbers.
        </p>
      </header>

      <main className="mx-auto max-w-4xl space-y-6 px-6 py-6">
        {!apiUp && (
          <div className="rounded-lg border border-destructive/40 bg-popover px-4 py-3 text-sm text-destructive">
            The floor API is not reachable at {API_BASE}. Workspace stats need the API server running.
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

        {/* Operator */}
        <section className="rounded-xl border border-border bg-card p-5">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Operator
          </h2>
          {session ? (
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <span
                  className="flex size-11 items-center justify-center rounded-full bg-primary text-lg font-semibold text-primary-foreground"
                  aria-hidden="true"
                >
                  {operatorInitial(session)}
                </span>
                <div>
                  <p className="font-medium leading-tight">{session.displayName}</p>
                  <p className="text-sm leading-tight text-muted-foreground">{session.email}</p>
                </div>
              </div>
              <div className="flex flex-wrap items-end gap-2">
                <div className="min-w-56 flex-1">
                  <label htmlFor="display-name" className="mb-1 block text-sm font-medium">
                    Display name
                  </label>
                  <input
                    id="display-name"
                    value={nameDraft}
                    onChange={(e) => setNameDraft(e.target.value)}
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  />
                </div>
                <button
                  type="button"
                  onClick={saveName}
                  disabled={nameDraft.trim() === session.displayName}
                  className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
                >
                  Save
                </button>
              </div>
              <p className="text-2xs text-muted-foreground">
                Signed in {session.signedInAt ? new Date(session.signedInAt).toLocaleString() : ""}
                {" · "}local demo session — identity lives in this browser only.
              </p>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No session found.</p>
          )}
        </section>

        {/* Workspace */}
        <section className="rounded-xl border border-border bg-card p-5">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Workspace
          </h2>
          <dl className="grid gap-3 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-muted-foreground">Name</dt>
              <dd className="mt-0.5 font-medium">{session?.workspace ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Floor mode</dt>
              <dd className="mt-0.5 font-medium capitalize">
                {mode ? mode.mode : "—"}
                {mode?.mode === "manual" && (
                  <span className="block text-2xs font-normal normal-case text-muted-foreground">
                    writes wait for a human at the confirmation gate
                  </span>
                )}
                {mode?.mode === "auto" && (
                  <span className="block text-2xs font-normal normal-case text-muted-foreground">
                    writes auto-approve, logged in the audit stream
                  </span>
                )}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Auto-run cap</dt>
              <dd className="mt-0.5 font-medium">
                {mode?.cap != null ? credits(mode.cap) : "Not set"}
                {mode && (
                  <span className="block text-2xs font-normal text-muted-foreground">
                    auto-run is {mode.autoStatus}
                  </span>
                )}
              </dd>
            </div>
          </dl>
        </section>

        {/* Floor stats */}
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Floor stats — live from the ledger
          </h2>
          {stats ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard label="Jobs paid" value={String(stats.jobsPaid)} sub="work orders with an earning in the ledger" />
              <StatCard label="Credits paid out" value={credits(stats.totalPaidOut)} sub="earnings, review & appeal fees, bonuses" />
              <StatCard label="Active agents" value={`${stats.activeAgents} / ${stats.totalAgents}`} sub="of the roster not fired" />
              <StatCard label="Department systems" value={`${stats.systemsOnline} / ${stats.systemsTotal}`} sub="workplaces answering their health check" />
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              {apiUp ? "Loading…" : "Stats unavailable while the API is down."}
            </p>
          )}
        </section>

        {/* Danger zone */}
        <section className="rounded-xl border border-destructive/40 bg-card p-5">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-destructive">
            Reset the floor
          </h2>
          <p className="text-sm text-muted-foreground">
            Restore the demo-start state: roster, jobs and ledger are reset and every
            department system is reseeded. Connections are kept.
          </p>
          <button
            type="button"
            disabled={resetting}
            onClick={() => void doReset()}
            className="mt-3 rounded-md border border-destructive/40 px-3 py-1.5 text-sm font-medium text-destructive disabled:opacity-50"
          >
            {resetting ? "Resetting…" : "Reset floor"}
          </button>
        </section>
      </main>
    </div>
  );
}
