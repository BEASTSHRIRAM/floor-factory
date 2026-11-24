"use client";

import type { Agent, Job, Presence } from "../lib/types";
import { credits, isFired, jobColumn, pick } from "../lib/api";
import Avatar from "./Avatar";

/* Right inspector: detail for the selected job or agent, composed only
   from facts the data layer already carries (bids, winner, severity,
   reputation, balance, mutation). Collapsible — closing it returns the
   full width to the board. */

function Kv({ label, children, mono }: { label: string; children: React.ReactNode; mono?: boolean }) {
  return (
    <div className="kv">
      <dt>{label}</dt>
      <dd className={mono ? "insp-mono" : undefined}>{children}</dd>
    </div>
  );
}

export default function Inspector({
  job,
  agent,
  presence,
  onClose,
}: {
  job?: Job | null;
  agent?: Agent | null;
  presence?: Presence;
  onClose: () => void;
}) {
  if (!job && !agent) return null;
  return (
    <aside className="inspector fx-entrance" aria-label="Details">
      {job && (
        <>
          <div className="insp-head">
            <h2 className="insp-title">{job.title}</h2>
            <button type="button" className="insp-close" onClick={onClose} aria-label="Close details">
              ×
            </button>
          </div>
          <p className="insp-status" style={{ color: "var(--muted)" }}>
            Lane: {jobColumn(job)} · Status: {job.status}
          </p>
          <dl>
            {job.system && <Kv label="System">{job.system}</Kv>}
            {job.budget_credits !== undefined && <Kv label="Budget" mono>{credits(job.budget_credits)}</Kv>}
            {job.winner && <Kv label="Awarded to">{String(job.winner)}</Kv>}
            {job.severity && <Kv label="Review severity">{job.severity}</Kv>}
            <Kv label="Bids" mono>{(job.bids ?? []).length}</Kv>
          </dl>
          {(job.bids ?? []).length > 0 && (
            <>
              <h3 className="insp-section">Sealed bids</h3>
              <table className="insp-table">
                <thead>
                  <tr>
                    <th scope="col">Bidder</th>
                    <th scope="col" className="num">Price</th>
                    <th scope="col" className="num">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {(job.bids ?? []).map((b, i) => {
                    const who = String(
                      pick(b as Record<string, unknown>, "agent_name", "agent", "bidder", "agent_id") ?? "Agent"
                    );
                    const price = pick(b as Record<string, unknown>, "price_credits", "price", "amount");
                    const conf = pick(b as Record<string, unknown>, "confidence", "conf");
                    const win = !!job.winner && who === String(job.winner);
                    return (
                      <tr key={i} className={win ? "winner" : undefined}>
                        <td>{who}</td>
                        <td className="num">{price !== undefined ? credits(price) : "—"}</td>
                        <td className="num">{conf !== undefined ? Number(conf).toFixed(2) : "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </>
          )}
        </>
      )}
      {agent && (
        <>
          <div className="insp-head">
            <Avatar agent={agent} presence={isFired(agent) ? "fired" : presence?.state} size={38} />
            <h2 className="insp-title">{agent.name}</h2>
            <button type="button" className="insp-close" onClick={onClose} aria-label="Close details">
              ×
            </button>
          </div>
          <p className="insp-status" style={{ color: "var(--muted)" }}>
            {isFired(agent)
              ? "Fired by the CFO"
              : presence
                ? `Presence: ${presence.state}${presence.tool ? ` — running ${presence.tool}` : ""}`
                : `Status: ${agent.status}`}
          </p>
          <dl>
            {agent.role && <Kv label="Role">{agent.role}</Kv>}
            {agent.tier && <Kv label="Tier">{agent.tier}</Kv>}
            <Kv label="Generation" mono>{agent.generation}</Kv>
            {agent.model && <Kv label="Model">{agent.model}</Kv>}
            <Kv label="Reputation" mono>{Math.round(agent.reputation)} / 100</Kv>
            <Kv label="Balance" mono>{credits(agent.balance_credits)}</Kv>
            {agent.current_job && <Kv label="Current job">{agent.current_job}</Kv>}
            {agent.last_tool && <Kv label="Last tool">{agent.last_tool}</Kv>}
          </dl>
          {agent.mutation_note && (
            <>
              <h3 className="insp-section">Mutation</h3>
              <p className="insp-note mutation">{agent.mutation_note}</p>
            </>
          )}
        </>
      )}
    </aside>
  );
}
