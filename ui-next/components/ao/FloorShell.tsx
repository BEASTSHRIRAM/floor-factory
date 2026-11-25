"use client";

/* The console shell, structured after agent-orchestrator's app shell
 * (frontend/src/renderer/routes/_shell.tsx + Sidebar + PageTopbar):
 * a left rail with brand header, grouped list and footer totals; a
 * 48px topbar with title, stat chips and the primary actions; the
 * board in the centre; the inspector as a right rail. All surfaces
 * and type come from their theme tokens (Claude-recoloured); the
 * content is THE FLOOR's roster, ledger and event stream. */

import { useState, type ReactNode } from "react";
import { AgentAvatar } from "../../vendor/ao/product-ui";
import Mascot, { type MascotState } from "../Mascot";
import { Button } from "../../vendor/ao/button";
import { API_BASE, credits, pick, signedCredits } from "../../lib/api";
import type { Agent, LedgerRow, NarrationItem, Presence } from "../../lib/types";
import { presenceLabel, type TickerItem } from "./adapter";

export type ConsoleMode = "live" | "demo";
export type DemoPhase = "idle" | "playing" | "ended";
export type FloorTrustMode = "manual" | "auto";
export interface AutoRunStatus {
  status: string;
  budget_cap_credits: number | null;
  spent_credits: number;
  cycles_completed: number;
  current_cycle: number | null;
  stop_reason: string | null;
  last_error: string | null;
}
export interface ShellStats {
  cycle: number | null;
  paidOut: number;
  done: number;
  failed: number;
  activeAgents: number;
}

function AgentRow({
  agent,
  presence,
  paidFlash,
  flashKind,
  selected,
  onSelect,
}: {
  agent: Agent;
  presence?: Presence;
  paidFlash: boolean;
  flashKind: "fired" | "hired" | null;
  selected: boolean;
  onSelect: () => void;
}) {
  const p = presenceLabel(agent, presence);
  const fired = p.text.startsWith("Fired");
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={selected || undefined}
      className={`group relative flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left transition-colors ${
        selected ? "bg-interactive-hover" : "hover:bg-interactive-hover"
      } ${fired ? "opacity-55" : ""} ${
        flashKind === "fired" ? "bg-destructive/15" : flashKind === "hired" ? "bg-success/15" : ""
      }`}
    >
      <span className={`relative shrink-0 rounded-full ${paidFlash ? "ring-2 ring-success ring-offset-2 ring-offset-sidebar" : ""}`}>
        <AgentAvatar provider={agent.name} />
        <span className={`absolute -bottom-0.5 -right-0.5 size-2.5 rounded-full border-2 border-sidebar ${p.dotClass}`} aria-hidden="true" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline gap-1.5">
          <span className="truncate text-sm font-medium text-foreground">{agent.name}</span>
          {agent.generation > 1 && <span className="shrink-0 text-2xs font-medium text-brand-logo-text">Gen {agent.generation}</span>}
        </span>
        <span className="block truncate text-2xs text-muted-foreground">{p.text}</span>
      </span>
      <span className="shrink-0 text-right">
        <span className="block font-mono text-xs tabular-nums text-foreground">{credits(agent.balance_credits)}</span>
        <span className="block text-2xs tabular-nums text-passive">rep {agent.reputation}</span>
      </span>
    </button>
  );
}

function RosterGroup({
  title,
  agents,
  presence,
  paidFlash,
  firedIds,
  hireIds,
  selectedId,
  onSelect,
  emptyText,
}: {
  title: string;
  agents: Agent[];
  presence: Record<string, Presence>;
  paidFlash: Set<string>;
  firedIds: Set<string>;
  hireIds: Set<string>;
  selectedId: string | null;
  onSelect: (a: Agent) => void;
  emptyText: string;
}) {
  return (
    <div className="px-2 pb-1">
      <div className="px-2 pb-1 pt-3 text-2xs font-semibold uppercase tracking-[0.08em] text-passive">{title}</div>
      {agents.length ? (
        agents.map((a) => (
          <AgentRow
            key={a.id}
            agent={a}
            presence={presence[a.id]}
            paidFlash={paidFlash.has(a.id)}
            flashKind={firedIds.has(a.id) ? "fired" : hireIds.has(a.id) ? "hired" : null}
            selected={selectedId === a.id}
            onSelect={() => onSelect(a)}
          />
        ))
      ) : (
        <p className="px-2 py-1 text-2xs text-passive">{emptyText}</p>
      )}
    </div>
  );
}

function StatChip({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-2xs text-muted-foreground">
      {label}
      <span className="font-mono font-medium tabular-nums text-foreground">{value}</span>
    </span>
  );
}

export default function FloorShell(props: {
  mascotState: MascotState;
  management: Agent[];
  workers: Agent[];
  fired: Agent[];
  stats: ShellStats;
  presence: Record<string, Presence>;
  paidFlash: Set<string>;
  firedIds: Set<string>;
  hireIds: Set<string>;
  selectedAgentId: string | null;
  onSelectAgent: (a: Agent) => void;
  connected: boolean;
  mode: ConsoleMode;
  demoPhase: DemoPhase;
  floorMode: FloorTrustMode | null;
  autoStatus: AutoRunStatus | null;
  onFloorModeChange: (m: FloorTrustMode) => void;
  onAutoStart: (cap: number) => void;
  onAutoPause: () => void;
  onAutoStop: () => void;
  running: boolean;
  onRun: () => void;
  onReset: () => void;
  showHero: boolean;
  onStartReplay: () => void;
  apiUp: boolean;
  onEnterLive: () => void;
  banner: boolean;
  ledger: LedgerRow[];
  narration: NarrationItem[];
  ticker: TickerItem[];
  pinkSlips: { key: number; text: string }[];
  board: ReactNode;
  inspector: ReactNode;
}) {
  const {
    stats, connected, mode, demoPhase, running, showHero, banner, apiUp,
    ledger, narration, ticker, pinkSlips,
    floorMode, autoStatus, onFloorModeChange, onAutoStart, onAutoPause, onAutoStop,
  } = props;
  const demo = mode === "demo";
  const [capDraft, setCapDraft] = useState("3000");
  const autoRunning = autoStatus?.status === "running";
  const autoPaused = autoStatus?.status === "paused";
  const nameById = new Map<string, string>();
  [...props.management, ...props.workers, ...props.fired].forEach((a) => nameById.set(a.id, a.name));

  return (
    <div className="ao-root flex h-dvh w-full overflow-hidden bg-background font-sans text-foreground">
      {/* ── Left rail: roster, totals (their Sidebar structure; brand lives in the app shell) ── */}
      <aside className="flex w-[280px] shrink-0 flex-col border-r border-border bg-sidebar" aria-label="Agent roster">
        <div className="min-h-0 flex-1 overflow-y-auto pb-2 pt-1">
          <RosterGroup
            title="Management"
            agents={props.management}
            presence={props.presence}
            paidFlash={props.paidFlash}
            firedIds={props.firedIds}
            hireIds={props.hireIds}
            selectedId={props.selectedAgentId}
            onSelect={props.onSelectAgent}
            emptyText="No management online."
          />
          <RosterGroup
            title="Workers"
            agents={props.workers}
            presence={props.presence}
            paidFlash={props.paidFlash}
            firedIds={props.firedIds}
            hireIds={props.hireIds}
            selectedId={props.selectedAgentId}
            onSelect={props.onSelectAgent}
            emptyText="No workers on the floor yet."
          />
          <RosterGroup
            title="The Graveyard"
            agents={props.fired}
            presence={props.presence}
            paidFlash={props.paidFlash}
            firedIds={props.firedIds}
            hireIds={props.hireIds}
            selectedId={props.selectedAgentId}
            onSelect={props.onSelectAgent}
            emptyText="No pink slips yet."
          />
        </div>

        <div className="shrink-0 border-t border-border px-4 py-3">
          <div className="flex items-baseline justify-between">
            <span className="text-2xs uppercase tracking-[0.08em] text-passive">Paid out</span>
            <span className="font-mono text-sm font-medium tabular-nums text-foreground">{credits(stats.paidOut)}</span>
          </div>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-2xs uppercase tracking-[0.08em] text-passive">Jobs done</span>
            <span className="font-mono text-sm tabular-nums text-foreground">
              {stats.done}
              {stats.failed > 0 && <span className="text-destructive"> · {stats.failed} failed</span>}
            </span>
          </div>
          <p className="mt-2 text-2xs leading-relaxed text-passive">Every agent has a price. Every price has a consequence.</p>
        </div>
      </aside>

      {/* ── Centre: topbar, board, feeds ── */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center gap-3 border-b border-border px-4">
          <div className="flex min-w-0 items-baseline gap-2">
            <h1 className="truncate text-sm font-semibold text-foreground">Mission control</h1>
            <span className="hidden truncate text-2xs text-passive lg:block">Bids · Synapse work · Review · Payroll</span>
          </div>

          <div className="ml-2 hidden items-center gap-1.5 md:flex">
            <StatChip label="Cycle" value={stats.cycle !== null ? String(stats.cycle) : "—"} />
            <StatChip label="Paid out" value={credits(stats.paidOut)} />
            <StatChip label="Jobs done" value={String(stats.done)} />
            <StatChip label="Agents" value={String(stats.activeAgents)} />
          </div>

          {!demo && floorMode && (
            <div
              className="ml-2 flex shrink-0 items-center rounded-full border border-border p-0.5"
              role="group"
              aria-label="Trust mode: manual gate or auto run"
              title="Manual: every write waits for a human at the confirmation gate. Auto: writes are auto-approved and logged, and the floor runs itself up to a budget cap."
            >
              {(["manual", "auto"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => onFloorModeChange(m)}
                  aria-pressed={floorMode === m}
                  className={`rounded-full px-2.5 py-1 text-2xs font-medium capitalize transition-colors ${
                    floorMode === m ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
          )}

          <div className="ml-auto flex shrink-0 items-center gap-2">
            {demo ? (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-destructive/15 px-2.5 py-1 text-2xs font-medium text-destructive" role="status">
                <span className={`size-1.5 rounded-full bg-destructive ${demoPhase === "playing" ? "animate-status-pulse" : ""}`} aria-hidden="true" />
                {demoPhase === "ended" ? "Recorded demo — shift complete" : "Recorded demo — replaying a real shift"}
              </span>
            ) : (
              <span className="hidden items-center gap-1.5 text-2xs text-muted-foreground sm:inline-flex" role="status">
                <span className={`size-1.5 rounded-full ${connected ? "bg-status-working" : "bg-passive"}`} aria-hidden="true" />
                {connected ? "Live" : "Offline — retrying"}
              </span>
            )}
            <Button variant="primary" size="sm" onClick={props.onRun} disabled={running}>
              {demo ? (demoPhase === "playing" ? "Replaying…" : "Replay shift") : running ? "Running…" : "Run shift"}
            </Button>
            <Button variant="outline" size="sm" onClick={props.onReset}>
              Reset
            </Button>
          </div>
        </header>

        <div className="flex min-h-0 flex-1">
          <main className="flex min-w-0 flex-1 flex-col" id="main">
            {!demo && floorMode === "auto" && (
              <div className="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-2 border-b border-border bg-card px-4 py-2" role="region" aria-label="Auto run controls">
                <span className="text-2xs font-semibold uppercase tracking-[0.08em] text-passive">Auto run</span>
                {autoStatus ? (
                  <span className="text-xs text-muted-foreground">
                    {autoRunning
                      ? `Running${autoStatus.current_cycle ? ` — cycle ${autoStatus.current_cycle}` : ""}`
                      : autoPaused
                        ? "Paused — takes effect at the cycle boundary"
                        : `Stopped${autoStatus.stop_reason ? ` (${autoStatus.stop_reason.replace(/_/g, " ")})` : ""}`}
                    {" · "}
                    <span className="font-mono tabular-nums text-foreground">
                      {credits(autoStatus.spent_credits)}
                    </span>{" "}
                    spent
                    {autoStatus.budget_cap_credits !== null && (
                      <>
                        {" "}of{" "}
                        <span className="font-mono tabular-nums text-foreground">
                          {credits(autoStatus.budget_cap_credits)}
                        </span>{" "}
                        cap
                      </>
                    )}
                    {" · "}
                    {autoStatus.cycles_completed} cycle{autoStatus.cycles_completed === 1 ? "" : "s"} done
                    {autoStatus.last_error && <span className="text-destructive"> · {autoStatus.last_error}</span>}
                  </span>
                ) : (
                  <span className="text-xs text-passive">Reading auto-run state…</span>
                )}
                <span className="ml-auto flex items-center gap-2">
                  {!autoRunning && (
                    <>
                      <label className="flex items-center gap-1.5 text-2xs text-muted-foreground">
                        Cap ₡
                        <input
                          type="number"
                          min={1}
                          value={capDraft}
                          onChange={(e) => setCapDraft(e.target.value)}
                          className="w-20 rounded-md border border-border bg-background px-2 py-1 font-mono text-xs tabular-nums text-foreground"
                          aria-label="Budget cap in credits"
                        />
                      </label>
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => {
                          const cap = Number(capDraft);
                          if (Number.isFinite(cap) && cap > 0) onAutoStart(cap);
                        }}
                      >
                        {autoPaused ? "Resume" : "Start"}
                      </Button>
                    </>
                  )}
                  {autoRunning && (
                    <Button variant="outline" size="sm" onClick={onAutoPause}>
                      Pause
                    </Button>
                  )}
                  {(autoRunning || autoPaused) && (
                    <Button variant="outline" size="sm" onClick={onAutoStop}>
                      Stop
                    </Button>
                  )}
                </span>
              </div>
            )}
            {banner && (
              <div className="shrink-0 border-b border-border bg-success/10 px-4 py-2 text-xs font-medium text-success" role="alert">
                Payroll — cycle closed. Net pay, costs and verdicts are in the payroll statement.
              </div>
            )}
            {demo && apiUp && (
              <div className="flex shrink-0 items-center gap-3 border-b border-border bg-brand-logo/10 px-4 py-2 text-xs text-foreground" role="status">
                <span>The live factory API is reachable now.</span>
                <span className="ml-auto" />
                <Button variant="primary" size="xs" onClick={props.onEnterLive}>
                  Switch to live
                </Button>
              </div>
            )}
            {demo && demoPhase === "ended" && (
              <div className="flex shrink-0 items-center gap-3 border-b border-border bg-card px-4 py-2 text-xs text-foreground" role="status">
                <span>
                  Recorded shift complete — <b>11/11 jobs paid · ₡738 disbursed · appeal upheld · 1 PinkSlip</b>
                </span>
                <span className="ml-auto" />
                {apiUp ? (
                  <Button variant="primary" size="xs" onClick={props.onEnterLive}>
                    Switch to live
                  </Button>
                ) : (
                  <Button variant="outline" size="xs" onClick={props.onStartReplay}>
                    Replay again
                  </Button>
                )}
              </div>
            )}

            {showHero ? (
              <div className="flex min-h-0 flex-1 items-center justify-center overflow-y-auto p-8">
                <div className="w-full max-w-[720px] rounded-xl border border-border bg-card p-8 shadow-lg">
                  <div className="flex items-start gap-6">
                    <Mascot state={props.mascotState} size={168} className="hidden shrink-0 sm:block" />
                    <div className="min-w-0">
                  <p className="text-2xs font-semibold uppercase tracking-[0.14em] text-brand-logo-text">Live API offline</p>
                  <h2 className="font-display mt-3 text-[34px] leading-[1.12] text-foreground">
                    The floor is quiet <span className="text-primary">here</span> — watch it work.
                  </h2>
                  <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                    This console is hosted, but the factory API runs on the presenter&apos;s machine, so there is no live
                    floor to connect to from this page. The board wakes up on its own if the API starts.
                  </p>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    Until then, watch a <b className="text-foreground">real 2-cycle shift, recorded from the live system</b> —
                    11 jobs posted, bid on, worked through Synapse MCP tools, audited and paid. ₡738 disbursed, one appeal
                    upheld, one agent fired and replaced by a mutated hire.
                  </p>
                  <div className="mt-6 flex items-center gap-3">
                    <Button variant="primary" onClick={props.onStartReplay}>
                      Watch the recorded shift
                    </Button>
                    <span className="font-mono text-2xs text-passive">{API_BASE}</span>
                  </div>
                  <p className="mt-4 text-2xs leading-relaxed text-passive">
                    The replay is labelled “Recorded demo” for as long as it is on screen — it is never presented as live.
                  </p>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <>
                <div className="min-h-0 flex-1">{props.board}</div>
                <section className="flex h-[168px] shrink-0 border-t border-border" aria-label="Ledger and event stream">
                  <div className="flex min-w-0 flex-1 flex-col border-r border-border">
                    <h2 className="shrink-0 px-4 pb-1 pt-2.5 text-2xs font-semibold uppercase tracking-[0.08em] text-passive">
                      Ledger
                    </h2>
                    <div className="board-scrollbar min-h-0 flex-1 overflow-y-auto px-4 pb-3">
                      {pinkSlips.map((s) => (
                        <div key={s.key} className="flex items-center gap-2 py-1 text-xs text-destructive">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img src="/mascot/pinkslip.webp" alt="" aria-hidden="true" className="size-5 shrink-0 rounded object-cover" />
                          <span className="min-w-0 truncate">{s.text}</span>
                        </div>
                      ))}
                      {ledger.length === 0 && pinkSlips.length === 0 && (
                        <p className="py-1 text-xs text-passive">No credit movements yet.</p>
                      )}
                      {ledger.slice(0, 60).map((row, i) => {
                        const amt = Number(pick(row as Record<string, unknown>, "amount_credits", "amount"));
                        const rawWho = pick(row as Record<string, unknown>, "agent_name", "agent_id");
                        const who = rawWho !== undefined ? (nameById.get(String(rawWho)) ?? String(rawWho)) : "";
                        const note = String(pick(row as Record<string, unknown>, "note", "reason", "kind") ?? "");
                        return (
                          <div key={String(row.id ?? i)} className="flex items-baseline justify-between gap-3 py-1 text-xs">
                            <span className="min-w-0 truncate text-muted-foreground">
                              {who && <span className="font-medium text-foreground">{who} </span>}
                              {note}
                            </span>
                            <span
                              className={`shrink-0 font-mono tabular-nums ${Number.isFinite(amt) && amt < 0 ? "text-destructive" : "text-success"}`}
                            >
                              {signedCredits(amt)}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  <div className="flex min-w-0 flex-1 flex-col">
                    <h2 className="shrink-0 px-4 pb-1 pt-2.5 text-2xs font-semibold uppercase tracking-[0.08em] text-passive">
                      Event stream
                    </h2>
                    <div className="board-scrollbar min-h-0 flex-1 overflow-y-auto px-4 pb-3">
                      {ticker.slice(-6).map((t) => (
                        <p key={t.key} className="py-1 text-xs leading-snug text-muted-foreground">
                          <span className="font-medium text-foreground">{t.who}</span> {t.text}
                        </p>
                      ))}
                      {narration.length === 0 && ticker.length === 0 && (
                        <p className="flex items-center gap-2 py-1 text-xs text-passive">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img src="/mascot/working.webp" alt="" aria-hidden="true" className="size-7 shrink-0 rounded-md object-cover" />
                          The floor is staffed and idle. Run a shift to put the crew to work.
                        </p>
                      )}
                      {narration.map((n) => (
                        <p
                          key={n.key}
                          className={`py-1 text-xs leading-snug ${
                            n.cls === "pinkslip"
                              ? "text-destructive"
                              : n.cls === "appeal"
                                ? "text-status-in-review"
                                : n.cls === "hire"
                                  ? "text-success"
                                  : "text-muted-foreground"
                          }`}
                        >
                          {n.cls === "pinkslip" && (
                            /* eslint-disable-next-line @next/next/no-img-element */
                            <img src="/mascot/pinkslip.webp" alt="" aria-hidden="true" className="mr-1.5 inline-block size-4 rounded-sm object-cover align-[-3px]" />
                          )}
                          {n.text}
                        </p>
                      ))}
                    </div>
                  </div>
                </section>
              </>
            )}
          </main>

          {props.inspector}
        </div>
      </div>
    </div>
  );
}
