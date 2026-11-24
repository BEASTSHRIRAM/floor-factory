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
  { key: "progress", label: "In progress" },
  { key: "review", label: "In review" },
  { key: "done", label: "Done" },
];

/** One derived status line per card, computed from the job's durable
 *  facts (status, bids, winner, severity) — never invented prose. */
function statusLine(job: Job, col: JobColumn): string {
  const s = job.status.toLowerCase();
  const bids = job.bids ?? [];
  if (s === "appealed" || s === "appeal") return "Appeal — blind review";
  if (s === "rejected") return "Rejected";
  if (s === "failed") return "Failed verification";
  switch (col) {
    case "open":
      return "Awaiting bids";
    case "bidding": {
      if (!bids.length) return "Auction open";
      const prices = bids
        .map((b) => Number(pick(b as Record<string, unknown>, "price_credits", "price", "amount")))
        .filter((n) => Number.isFinite(n));
      return prices.length
        ? `${bids.length} bid${bids.length === 1 ? "" : "s"} · leading ${credits(Math.min(...prices))}`
        : `${bids.length} bids`;
    }
    case "progress":
      return job.winner ? `Awarded to ${String(job.winner)}` : "In progress";
    case "review":
      return job.severity ? `In review · ${job.severity}` : "In review";
    case "done":
      return job.winner ? `Settled — ${String(job.winner)}` : "Settled";
  }
}

/** Attention first: appeals, rejections and P0/P1 severities float to
 *  the top of their lane; everything else keeps arrival order. */
function attentionRank(job: Job): number {
  const s = job.status.toLowerCase();
  if (s === "appealed" || s === "appeal" || s === "rejected" || s === "failed") return 0;
  if (job.severity === "P0" || job.severity === "P1") return 1;
  return 2;
}

function JobCard({
  job,
  selected,
  onSelect,
}: {
  job: Job;
  selected?: boolean;
  onSelect?: (j: Job) => void;
}) {
  const bids = job.bids ?? [];
  const col = jobColumn(job);
  return (
    <div
      className={`job-card${selected ? " selected" : ""}`}
      onClick={onSelect ? () => onSelect(job) : undefined}
      role={onSelect ? "button" : undefined}
      tabIndex={onSelect ? 0 : undefined}
      onKeyDown={
        onSelect
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect(job);
              }
            }
          : undefined
      }
    >
      <div className="job-title">{job.title}</div>
      <div className={`job-status ${col}`}>{statusLine(job, col)}</div>
      {bids.length > 0 && (
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
                  {conf !== undefined ? ` · ${Number(conf).toFixed(2)}` : ""}
                </span>
              </div>
            );
          })}
        </div>
      )}
      <div className="job-foot">
        <span>
          {job.budget_credits !== undefined ? (
            <>
              Budget <span className="job-budget">{credits(job.budget_credits)}</span>
            </>
          ) : (
            (job.system ?? "")
          )}
        </span>
        <span>
          {job.system && job.budget_credits !== undefined ? `${job.system} · ` : ""}
          {bids.length} bid{bids.length === 1 ? "" : "s"}
        </span>
      </div>
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

export default function JobBoard({
  jobs,
  ticker,
  selectedId,
  onSelect,
}: {
  jobs: Job[];
  ticker: TickerItem[];
  selectedId?: string | null;
  onSelect?: (j: Job) => void;
}) {
  const cols: Record<JobColumn, Job[]> = { open: [], bidding: [], progress: [], review: [], done: [] };
  jobs.forEach((j) => cols[jobColumn(j)].push(j));
  (Object.keys(cols) as JobColumn[]).forEach((k) => {
    cols[k] = cols[k]
      .map((j, i) => ({ j, i }))
      .sort((a, b) => attentionRank(a.j) - attentionRank(b.j) || a.i - b.i)
      .map(({ j }) => j);
  });
  return (
    <section className="panel fx-entrance" aria-labelledby="jobs-title">
      <h2 className="panel-title" id="jobs-title">
        Job board
      </h2>
      {/* Ticker duplicates bids that also appear on job cards and in the
          narration log, so it is hidden from assistive tech. */}
      <Ticker items={ticker} />
      <div className="job-board">
        {COLUMNS.map((c) => (
          <div className="job-col" key={c.key}>
            <h3 className="lane-head">
              <span className={`lane-dot ${c.key}`} aria-hidden="true" />
              {c.label}
              <span className="col-count">{cols[c.key].length}</span>
            </h3>
            <div className="col-body">
              {cols[c.key].length ? (
                cols[c.key].map((j) => (
                  <JobCard key={j.id || j.title} job={j} selected={selectedId === j.id} onSelect={onSelect} />
                ))
              ) : (
                <span className="empty">No jobs</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
