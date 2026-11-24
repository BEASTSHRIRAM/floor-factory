"use client";

/* Job Trace — the selected job's full life as one timeline, built
 * from the stored event stream (GET /state/events, paged in full)
 * filtered to events that reference this job or one of its work
 * orders: posted -> bids -> award -> harness -> gate decisions ->
 * tool calls -> submission -> review -> appeal -> payment.
 *
 * Coverage, honestly: events whose payload carries no job_id /
 * work_order_id (manager probes, floor-wide narration, mode changes)
 * cannot be attributed to a job and are not shown; the harness
 * context event is summarised (family + lessons applied), not dumped
 * in full. Runner state updates are collapsed to actual transitions.
 */

import { useEffect, useMemo, useState } from "react";
import { credits } from "../lib/api";
import { clockTime, fetchAllEvents, type RawEvent } from "../lib/floorData";
import type { Job } from "../lib/types";

interface TraceRow {
  seq: number;
  time: string;
  label: string;
  actor: string;
  detail: string;
  tone: "good" | "warn" | "bad" | "neutral";
}

const LABELS: Record<string, string> = {
  "job.posted": "Posted",
  "bid.placed": "Sealed bid",
  "job.awarded": "Awarded",
  "runner.work_order_created": "Work order",
  "harness.context": "Harness",
  "tool.confirmation_requested": "Gate decision",
  "confirmation.auto_approved": "Gate auto-approval",
  "tool.executed": "Tool call",
  "work.submitted": "Submitted",
  "review.completed": "Review",
  "appeal.filed": "Appeal filed",
  "appeal.decided": "Appeal decided",
  "payment.made": "Payment",
  "runner.work_order_updated": "State",
  "runner.work_order_terminated": "Terminated",
  "runner.finished": "Runner finished",
};

function num(v: unknown): number | undefined {
  const n = Number(v);
  return Number.isFinite(n) && v !== null && v !== undefined ? n : undefined;
}

export default function JobTrace({ job }: { job: Job }) {
  const [events, setEvents] = useState<RawEvent[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    setEvents(null);
    setFailed(false);
    (async () => {
      try {
        const ev = await fetchAllEvents();
        if (live) setEvents(ev);
      } catch {
        if (live) setFailed(true);
      }
    })();
    return () => {
      live = false;
    };
  }, [job.id]);

  const rows = useMemo<TraceRow[]>(() => {
    if (!events) return [];
    const woIds = new Set(
      ((job.work_orders as { id?: unknown }[] | undefined) ?? []).map((w) => String(w.id)),
    );
    const nameById = new Map<string, string>();
    for (const b of job.bids ?? []) {
      if (b.agent_id !== undefined && b.agent_name) nameById.set(String(b.agent_id), b.agent_name);
    }
    if (job.winner) {
      const winBid = (job.bids ?? []).find((b) => b.agent_name === job.winner);
      if (winBid?.agent_id !== undefined) nameById.set(String(winBid.agent_id), job.winner);
    }
    const nameOf = (p: Record<string, unknown>): string | undefined => {
      if (typeof p.agent_name === "string") return p.agent_name;
      if (typeof p.name === "string") return p.name;
      if (p.agent_id !== undefined) return nameById.get(String(p.agent_id));
      if (typeof p.agent === "string") return p.agent;
      if (typeof p.worker === "string" && p.worker !== "manager") return p.worker;
      return undefined;
    };

    const out: TraceRow[] = [];
    let lastTransition = "";
    for (const e of events) {
      const p = e.payload ?? {};
      const jobRef = p.job_id !== undefined && String(p.job_id) === String(job.id);
      const woRef = p.work_order_id !== undefined && woIds.has(String(p.work_order_id));
      if (!jobRef && !woRef) continue;
      if (!(e.type in LABELS)) continue;

      let actor = nameOf(p) ?? "";
      let detail = "";
      let tone: TraceRow["tone"] = "neutral";
      switch (e.type) {
        case "job.posted":
          actor = actor || "Manager";
          detail = `Posted with a ${credits(num(p.budget_credits))} budget`;
          break;
        case "bid.placed":
          detail = `${credits(num(p.price_credits))}${p.confidence !== undefined ? ` · confidence ${Number(p.confidence).toFixed(2)}` : ""}`;
          break;
        case "job.awarded":
          detail = `Won at ${credits(num(p.price_credits))}${p.score !== undefined ? ` · award score ${Number(p.score).toFixed(3)}` : ""}`;
          tone = "good";
          break;
        case "runner.work_order_created":
          actor = actor || "Runner";
          detail = `Work order #${String(p.work_order_id)} created → ${String(p.to ?? "queued")}`;
          break;
        case "harness.context":
          detail = `Context assembled — ${String(p.family ?? "")} family, ${String(p.lessons_applied ?? 0)} lesson(s) applied`;
          break;
        case "tool.confirmation_requested":
          actor = actor || "Gate";
          detail = `${String(p.tool_name ?? "write")} — ${
            p.approved ? `approved${p.confirmed_by ? ` by ${String(p.confirmed_by)}` : ""}` : "denied"
          }`;
          tone = p.approved ? "neutral" : "bad";
          break;
        case "confirmation.auto_approved":
          actor = actor || "Gate";
          detail = `${String(p.tool_name ?? "write")} auto-approved in auto mode — logged, no human at the gate`;
          break;
        case "tool.executed":
          detail = `${String(p.tool_name ?? "tool")} · ${String(p.effect ?? "")} · ${String(p.status ?? "")}`;
          if (p.status === "error") tone = "bad";
          break;
        case "work.submitted":
          detail = "Work submitted for review";
          break;
        case "review.completed": {
          const appeal = p.kind === "appeal";
          actor = actor || (appeal ? "Second reviewer (blind)" : "Reviewer");
          detail = `${appeal ? "Appeal review" : "Primary review"} — ${String(p.verdict ?? "")}${
            p.severity && p.severity !== "none" ? ` · severity ${String(p.severity)}` : ""
          }`;
          tone = p.verdict === "accept" ? "good" : "bad";
          break;
        }
        case "appeal.filed":
          detail = `Appeal filed · fee ${credits(num(p.fee_credits))}`;
          tone = "warn";
          break;
        case "appeal.decided":
          actor = actor || "Second reviewer (blind)";
          detail = p.verdict === "accept" ? "Appeal upheld — rejection overturned" : "Appeal denied";
          tone = p.verdict === "accept" ? "good" : "bad";
          break;
        case "payment.made":
          detail = `Paid ${credits(num(p.amount_credits))}${p.via ? ` via ${String(p.via)}` : ""}`;
          tone = "good";
          break;
        case "runner.work_order_updated": {
          const transition = `${String(p.from ?? "—")} → ${String(p.to ?? "—")}`;
          if (transition === lastTransition) continue;
          lastTransition = transition;
          actor = actor || "Runner";
          detail = `${transition}${p.reason ? ` · ${String(p.reason)}` : ""}`;
          break;
        }
        case "runner.work_order_terminated":
          actor = actor || "Runner";
          detail = `Work order terminated${p.reason ? ` — ${String(p.reason)}` : ""}`;
          tone = "warn";
          break;
        case "runner.finished":
          actor = actor || "Runner";
          detail = `Runner finished${p.status ? ` — ${String(p.status)}` : ""}`;
          break;
        default:
          detail = e.type;
      }
      out.push({
        seq: e.seq,
        time: clockTime(e.created_at),
        label: LABELS[e.type] ?? e.type,
        actor,
        detail,
        tone,
      });
    }
    return out;
  }, [events, job]);

  if (failed)
    return (
      <p className="text-xs text-muted-foreground">
        The trace could not load — the API did not answer. The job's summary and reviews above are
        unaffected.
      </p>
    );
  if (events === null)
    return <p className="text-xs text-muted-foreground">Loading the stored event stream…</p>;
  if (rows.length === 0)
    return (
      <p className="text-xs text-muted-foreground">
        No stored events reference this job yet — the trace fills in as the floor works it.
      </p>
    );

  return (
    <div>
      <ol className="relative ml-1 border-l border-border">
        {rows.map((r) => (
          <li key={r.seq} className="relative pb-3 pl-4 last:pb-0">
            <span
              className={`absolute -left-[5px] top-1 size-2.5 rounded-full ${
                r.tone === "good"
                  ? "bg-emerald-500"
                  : r.tone === "bad"
                    ? "bg-red-500"
                    : r.tone === "warn"
                      ? "bg-amber-500"
                      : "bg-muted-foreground"
              }`}
            />
            <div className="flex flex-wrap items-baseline gap-x-2">
              <span className="font-mono text-2xs tabular-nums text-muted-foreground">{r.time}</span>
              <span className="text-xs font-semibold">{r.label}</span>
              {r.actor && <span className="text-xs text-muted-foreground">{r.actor}</span>}
            </div>
            <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{r.detail}</p>
          </li>
        ))}
      </ol>
      <p className="mt-3 text-2xs leading-relaxed text-muted-foreground">
        From the stored event stream, filtered to this job and its work orders. Events that carry
        no job reference (manager probes, floor-wide events) cannot be attributed and are not
        shown; the harness context is summarised rather than dumped in full.
      </p>
    </div>
  );
}
