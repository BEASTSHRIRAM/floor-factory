"use client";

import { useLayoutEffect, useRef } from "react";
import gsap from "gsap";
import type { Agent } from "../lib/types";
import { credits, isFired } from "../lib/api";
import LottieBadge from "./fx/LottieBadge";

function statusOf(a: Agent): string {
  if (isFired(a)) return "fired";
  const s = a.status.toLowerCase().replace(/\s+/g, "_");
  return s === "inreview" ? "in_review" : s;
}

export function AgentCard({
  agent,
  justFired,
  justHired,
}: {
  agent: Agent;
  justFired?: boolean;
  justHired?: boolean;
}) {
  const cardRef = useRef<HTMLDivElement>(null);
  const fired = isFired(agent);
  const rep = agent.reputation;
  const repCls = rep >= 60 ? "" : rep >= 35 ? " mid" : " low";
  const bal = agent.balance_credits;
  const st = statusOf(agent);

  // GSAP state transitions: fired = shake, hired = drop-in.
  useLayoutEffect(() => {
    const el = cardRef.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (justFired) {
      gsap.fromTo(
        el,
        { x: 0 },
        { keyframes: [{ x: -7 }, { x: 7 }, { x: -5 }, { x: 5 }, { x: 0 }], duration: 0.6, ease: "power1.inOut" }
      );
    } else if (justHired) {
      gsap.fromTo(
        el,
        { y: -14, opacity: 0, boxShadow: "0 0 0 0 rgba(236,125,171,0)" },
        { y: 0, opacity: 1, boxShadow: "0 0 0 3px rgba(236,125,171,0.9)", duration: 0.7, ease: "power3.out",
          onComplete: () => gsap.to(el, { boxShadow: "0 0 0 0 rgba(236,125,171,0)", duration: 0.9 }) }
      );
    }
  }, [justFired, justHired]);

  return (
    <div
      ref={cardRef}
      className={`agent-card${fired ? " fired" : ""}`}
      data-agent={agent.id}
    >
      {fired && <span className="stamp">TERMINATED</span>}
      <div className="row1">
        <span className="agent-name">{agent.name}</span>
        {agent.tier && <span className="badge tier">{agent.tier}</span>}
        <span className="badge">Gen {agent.generation}</span>
        {justHired && <LottieBadge kind="hired" size={22} />}
        {fired && <LottieBadge kind="fired" size={22} />}
      </div>
      {agent.model && <div className="agent-meta">{agent.model}</div>}
      <div className="rep-wrap">
        <div className="rep-bar">
          <div className={`rep-fill${repCls}`} style={{ width: `${rep}%` }} />
        </div>
        <span className="rep-num">{Math.round(rep)}</span>
      </div>
      <div className="agent-foot">
        <span className={`balance ${bal < 0 ? "neg" : bal > 0 ? "pos" : ""}`}>{credits(bal)}</span>
        <span className={`chip ${st}`}>{st.replace("_", " ")}</span>
      </div>
      {agent.current_job && (
        <div className="current-job">
          Working: {agent.current_job}
          {agent.last_tool && (
            <>
              {" · "}
              <code>{agent.last_tool}</code>
            </>
          )}
        </div>
      )}
      {agent.mutation_note && <div className="mutation-note">{agent.mutation_note}</div>}
    </div>
  );
}

export default function OrgChart({
  management,
  workers,
  fired,
  firedIds,
  hireIds,
}: {
  management: Agent[];
  workers: Agent[];
  fired: Agent[];
  firedIds: Set<string>;
  hireIds: Set<string>;
}) {
  return (
    <section className="panel fx-entrance" aria-labelledby="org-title">
      <h2 className="panel-title" id="org-title">
        The Floor — Org Chart
      </h2>
      {management.length > 0 && (
        <div className="mgmt-row">
          {management.map((a) => (
            <AgentCard key={a.id} agent={a} />
          ))}
        </div>
      )}
      <div className="agent-grid">
        {workers.length ? (
          workers.map((a) => (
            <AgentCard
              key={a.id}
              agent={a}
              justFired={firedIds.has(a.id)}
              justHired={hireIds.has(a.id)}
            />
          ))
        ) : (
          <span className="empty">No workers on the floor yet.</span>
        )}
      </div>
      <h3 className="sub-title" id="graveyard-title">
        The Graveyard
      </h3>
      <div className="graveyard" aria-labelledby="graveyard-title">
        {fired.length ? (
          fired.map((a) => <AgentCard key={a.id} agent={a} justFired={firedIds.has(a.id)} />)
        ) : (
          <span className="empty">No pink slips yet.</span>
        )}
      </div>
    </section>
  );
}
