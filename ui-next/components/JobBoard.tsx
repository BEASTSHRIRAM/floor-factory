"use client";

import { useEffect, useRef } from "react";
import gsap from "gsap";
import type { Job } from "../lib/types";
import { credits, jobColumn, pick, type JobColumn } from "../lib/api";

export interface TickerItem {
  key: number;
  who: string;
  text: string;
}

const COLUMNS: { key: JobColumn; label: string }[] = [
  { key: "open", label: "Open" },
  { key: "bidding", label: "Bidding" },
  { key: "progress", label: "In Progress" },
  { key: "review", label: "In Review" },
  { key: "done", label: "Done" },
];

function JobCard({ job }: { job: Job }) {
  const bids = job.bids ?? [];
  return (
    <div className="job-card">
      <div className="job-title">{job.title}</div>
      {(job.system || job.budget_credits !== undefined) && (
        <div className="job-meta">
          {job.system}
          {job.system && job.budget_credits !== undefined ? " · " : ""}
          {job.budget_credits !== undefined && (
            <span className="job-budget">{credits(job.budget_credits)}</span>
          )}
        </div>
      )}
      {bids.length > 0 ? (
        <div className="bid-stack">
          {bids.map((b, i) => {
            const who = String(pick(b as Record<string, unknown>, "agent_name", "agent", "bidder", "agent_id") ?? "Agent");
            const price = pick(b as Record<string, unknown>, "price_credits", "price", "amount");
            const conf = pick(b as Record<string, unknown>, "confidence", "conf");
            const isWin = !!job.winner && who === String(job.winner);
            return (
              <div key={i} className={`bid-line${isWin ? " winner" : ""}`}>
                <span className="who">{who}</span>
                <span className="amt">
                  {price !== undefined ? credits(price) : ""}
                  {conf !== undefined ? ` · conf ${Number(conf).toFixed(2)}` : ""}
                </span>
              </div>
            );
          })}
        </div>
      ) : job.winner ? (
        <div className="job-status-note">Awarded to {String(job.winner)}</div>
      ) : null}
      {job.severity && (
        <div className="job-status-note">
          Review severity: <span className={`sev ${job.severity}`}>{job.severity}</span>
        </div>
      )}
    </div>
  );
}

/** Bid ticker: GSAP-driven infinite scroll (transform only), pauses on
 *  hover/focus, static under reduced motion. */
function Ticker({ items }: { items: TickerItem[] }) {
  const trackRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;
    if (items.length < 4) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    // Duplicate the track content once so the -50% loop is seamless.
    const tween = gsap.to(track, {
      xPercent: -50,
      ease: "none",
      duration: Math.max(18, items.length * 4),
      repeat: -1,
    });
    const pause = () => tween.pause();
    const play = () => tween.play();
    const wrap = track.parentElement;
    wrap?.addEventListener("mouseenter", pause);
    wrap?.addEventListener("mouseleave", play);
    wrap?.addEventListener("focusin", pause);
    wrap?.addEventListener("focusout", play);
    return () => {
      tween.kill();
      gsap.set(track, { xPercent: 0 });
      wrap?.removeEventListener("mouseenter", pause);
      wrap?.removeEventListener("mouseleave", play);
      wrap?.removeEventListener("focusin", pause);
      wrap?.removeEventListener("focusout", play);
    };
  }, [items]);

  const renderItems = (ariaHidden: boolean) =>
    items.map((it) => (
      <span className="ticker-item" key={`${ariaHidden ? "dup-" : ""}${it.key}`} aria-hidden={ariaHidden || undefined}>
        <b>{it.who}</b> {it.text}
      </span>
    ));

  return (
    <div className="ticker" aria-hidden="true">
      <div className="ticker-track" ref={trackRef}>
        {items.length ? (
          <>
            {renderItems(false)}
            {items.length >= 4 && renderItems(true)}
          </>
        ) : (
          <span className="ticker-item muted">Bid ticker idle — waiting for the auction.</span>
        )}
      </div>
    </div>
  );
}

export default function JobBoard({ jobs, ticker }: { jobs: Job[]; ticker: TickerItem[] }) {
  const cols: Record<JobColumn, Job[]> = { open: [], bidding: [], progress: [], review: [], done: [] };
  jobs.forEach((j) => cols[jobColumn(j)].push(j));
  return (
    <section className="panel fx-entrance" aria-labelledby="jobs-title">
      <h2 className="panel-title" id="jobs-title">
        Job Board
      </h2>
      {/* Ticker duplicates bids that also appear on job cards and in the
          narration log, so it is hidden from assistive tech. */}
      <Ticker items={ticker} />
      <div className="job-board">
        {COLUMNS.map((c) => (
          <div className="job-col" key={c.key}>
            <h3>{c.label}</h3>
            <div className="col-body">
              {cols[c.key].length ? (
                cols[c.key].map((j) => <JobCard key={j.id || j.title} job={j} />)
              ) : (
                <span className="empty">—</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
