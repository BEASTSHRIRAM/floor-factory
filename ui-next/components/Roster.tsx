"use client";

import { useLayoutEffect, useRef } from "react";
import gsap from "gsap";
import type { Agent, Presence, PresenceState } from "../lib/types";
import { credits, isFired } from "../lib/api";
import Avatar from "./Avatar";
import LottieBadge from "./fx/LottieBadge";

/* Roster sidebar — AO-style compact rows in one shared list. Each agent
   reads as a little employee: avatar tile (identity tint + monogram),
   presence dot on the tile corner, and one live presence line under
   the name. Presence is driven by FloorClient from the real event
   stream — working shows the tool that is actually running. */

function statusOf(a: Agent): string {
  if (isFired(a)) return "fired";
  const s = a.status.toLowerCase().replace(/\s+/g, "_");
  return s === "inreview" ? "in_review" : s;
}

function statusLabel(st: string): string {
  return st.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

/** Effective presence: durable facts (fired) win, then the live event
 *  presence, then the snapshot status, then idle. */
function effectivePresence(a: Agent, live?: Presence): PresenceState {
  if (isFired(a)) return "fired";
  if (live) return live.state;
  const st = statusOf(a);
  if (st === "working" || st === "executing") return "working";
  if (st === "bidding") return "bidding";
  if (st === "in_review" || st === "review") return "review";
  if (st === "appealed" || st === "appeal") return "appealing";
  return "idle";
}

function PresenceLine({ agent, live }: { agent: Agent; live?: Presence }) {
  const st = effectivePresence(agent, live);
  if (st === "fired") return <span>Fired by the CFO</span>;
  if (st === "working") {
    const tool = live?.tool;
    if (tool) {
      return (
        <span className="tool-line">
          running {tool}
          <span className="tdot">.</span>
          <span className="tdot">.</span>
          <span className="tdot">.</span>
          <span className="scan" aria-hidden="true" />
        </span>
      );
    }
    return <span className="presence-label working">Working</span>;
  }
  if (st === "bidding") return <span className="presence-label bidding">Bidding</span>;
  if (st === "review") return <span className="presence-label review">Under review</span>;
  if (st === "appealing") return <span className="presence-label appealing">Appealing</span>;
  if (agent.current_job) {
    return (
      <span>
        {agent.current_job}
        {agent.last_tool && (
          <>
            {" · "}
            <code>{agent.last_tool}</code>
          </>
        )}
      </span>
    );
  }
  return <span>{statusLabel(statusOf(agent))}</span>;
}

function RosterRow({
  agent,
  live,
  paidFlash,
  selected,
  onSelect,
  justFired,
  justHired,
}: {
  agent: Agent;
  live?: Presence;
  paidFlash?: boolean;
  selected?: boolean;
  onSelect?: (a: Agent) => void;
  justFired?: boolean;
  justHired?: boolean;
}) {
  const rowRef = useRef<HTMLDivElement>(null);
  const fired = isFired(agent);
  const rep = agent.reputation;
  const repCls = rep >= 60 ? "" : rep >= 35 ? " mid" : " low";
  const bal = agent.balance_credits;
  const presence = effectivePresence(agent, live);

  // GSAP state transitions, kept subtle: fired = short shake,
  // hired = drop-in with an indigo edge that fades (transform/opacity).
  useLayoutEffect(() => {
    const el = rowRef.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (justFired) {
      gsap.fromTo(
        el,
        { x: 0 },
        { keyframes: [{ x: -5 }, { x: 5 }, { x: -3 }, { x: 3 }, { x: 0 }], duration: 0.5, ease: "power1.inOut" }
      );
    } else if (justHired) {
      gsap.fromTo(
        el,
        { y: -8, opacity: 0, boxShadow: "inset 0 0 0 0 rgba(99,102,241,0)" },
        {
          y: 0, opacity: 1, boxShadow: "inset 2px 0 0 0 rgba(99,102,241,0.95)", duration: 0.6, ease: "power3.out",
          onComplete: () => gsap.to(el, { boxShadow: "inset 0 0 0 0 rgba(99,102,241,0)", duration: 0.9 }),
        }
      );
    }
  }, [justFired, justHired]);

  return (
    <div
      ref={rowRef}
      className={`roster-row${fired ? " fired" : ""}${selected ? " selected" : ""}`}
      data-agent={agent.id}
      onClick={onSelect ? () => onSelect(agent) : undefined}
      role={onSelect ? "button" : undefined}
      tabIndex={onSelect ? 0 : undefined}
      onKeyDown={
        onSelect
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect(agent);
              }
            }
          : undefined
      }
    >
      <div className="rr-main">
        <Avatar agent={agent} presence={presence} size={30} />
        <span className="rr-name">{agent.name}</span>
        <span className="rr-meta">
          {agent.tier ? `${agent.tier} · ` : ""}Gen {agent.generation}
        </span>
        {fired && <span className="rr-term">Terminated</span>}
        {justHired && <LottieBadge kind="hired" size={16} />}
        {fired && <LottieBadge kind="fired" size={16} />}
        <span className="bal-wrap">
          <span className={`bal-hl${paidFlash ? " on" : ""}`} aria-hidden="true" />
          <span className={`rr-bal ${bal < 0 ? "neg" : bal > 0 ? "pos" : ""}`}>{credits(bal)}</span>
        </span>
      </div>
      <div className="rr-sub">
        <span className="rr-status">
          <PresenceLine agent={agent} live={live} />
        </span>
        <span className="rep-wrap" title={`Reputation ${Math.round(rep)}`}>
          <span className="rep-bar">
            <span className={`rep-fill${repCls}`} style={{ width: `${rep}%`, display: "block" }} />
          </span>
          <span className="rep-num">{Math.round(rep)}</span>
        </span>
      </div>
      {agent.mutation_note && <div className="rr-mut">{agent.mutation_note}</div>}
      {!fired && agent.model && <div className="rr-mut" style={{ color: "var(--faint)" }}>{agent.model}</div>}
    </div>
  );
}

export default function Roster({
  management,
  workers,
  fired,
  firedIds,
  hireIds,
  presence,
  paidFlash,
  selectedId,
  onSelect,
}: {
  management: Agent[];
  workers: Agent[];
  fired: Agent[];
  firedIds: Set<string>;
  hireIds: Set<string>;
  presence: Record<string, Presence>;
  paidFlash: Set<string>;
  selectedId?: string | null;
  onSelect?: (a: Agent) => void;
}) {
  const row = (a: Agent, fx = false) => (
    <RosterRow
      key={a.id}
      agent={a}
      live={presence[a.id]}
      paidFlash={paidFlash.has(a.id)}
      selected={selectedId === a.id}
      onSelect={onSelect}
      justFired={fx ? firedIds.has(a.id) : false}
      justHired={fx ? hireIds.has(a.id) : false}
    />
  );
  return (
    <aside className="sidebar fx-entrance" aria-label="Agent roster">
      {management.length > 0 && (
        <>
          <h2 className="side-label">Management</h2>
          <div>{management.map((a) => row(a))}</div>
        </>
      )}
      <h2 className="side-label">Workers</h2>
      <div>
        {workers.length ? (
          workers.map((a) => row(a, true))
        ) : (
          <div className="roster-row">
            <span className="empty">No workers on the floor yet.</span>
          </div>
        )}
      </div>
      <h2 className="side-label">The Graveyard</h2>
      <div>
        {fired.length ? (
          fired.map((a) => row(a, true))
        ) : (
          <div className="roster-row">
            <span className="empty">No pink slips yet.</span>
          </div>
        )}
      </div>
    </aside>
  );
}
