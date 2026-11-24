"use client";

import CountUp from "./CountUp";
import { credits } from "../lib/api";

const fmtInt = (n: number) => String(Math.round(n));
const fmtCredits = (n: number) => credits(n);

export interface HeaderStats {
  cycle: number | null;
  paidOut: number;
  done: number;
  failed: number;
  activeAgents: number;
}

/* Slim topbar in the AO shell sense: brand and orientation on the left,
   a compact run of shift totals in the middle, and the two shift
   actions on the right. Nothing here duplicates the center surface. */
export default function Header({
  stats,
  connected,
  running,
  onRun,
  onReset,
}: {
  stats: HeaderStats;
  connected: boolean;
  running: boolean;
  onRun: () => void;
  onReset: () => void;
}) {
  return (
    <header id="topbar" className="fx-entrance">
      <div className="brand">
        <h1 className="logo">THE FLOOR</h1>
        <p className="tagline">Every agent has a price. Every price has a consequence.</p>
      </div>
      <dl className="stats" aria-label="Shift totals">
        <div className="stat hideable">
          <dt className="stat-label">Cycle</dt>
          <dd className="stat-value">{stats.cycle === null ? "—" : stats.cycle}</dd>
        </div>
        <div className="stat">
          <dt className="stat-label">Paid out</dt>
          <dd className="stat-value">
            <CountUp value={stats.paidOut} format={fmtCredits} />
          </dd>
        </div>
        <div className="stat">
          <dt className="stat-label">Jobs done</dt>
          <dd className="stat-value">
            <CountUp value={stats.done} format={fmtInt} />
          </dd>
        </div>
        <div className="stat hideable">
          <dt className="stat-label">Jobs failed</dt>
          <dd className="stat-value">
            <CountUp value={stats.failed} format={fmtInt} />
          </dd>
        </div>
        <div className="stat hideable">
          <dt className="stat-label">Active agents</dt>
          <dd className="stat-value">
            <CountUp value={stats.activeAgents} format={fmtInt} />
          </dd>
        </div>
        <div className="stat">
          <dt className="stat-label">Connection</dt>
          <dd className={`stat-value conn${connected ? " ok" : ""}`}>
            {connected ? "Live" : "Offline — retrying"}
          </dd>
        </div>
      </dl>
      <div className="actions">
        <button type="button" className="btn btn-primary" onClick={onRun} disabled={running}>
          {running ? "Shift running…" : "Run shift"}
        </button>
        <button type="button" className="btn btn-ghost" onClick={onReset}>
          Reset demo
        </button>
      </div>
    </header>
  );
}
