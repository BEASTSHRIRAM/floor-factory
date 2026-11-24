/* Floor → agent-orchestrator adapter.
 *
 * Mirrors the role of the AO renderer's own SessionsBoardAdapters: it
 * translates the host app's domain objects into the portable
 * @aoagents/product-ui presentation models (BoardSessionPresentation,
 * InspectorReviewGroup, InspectorTimelineEvent) so the vendored views
 * render Floor data with zero changes to their code.
 *
 * Mapping (also in console_v3_report.md):
 *   AO session        → Floor job (a unit of work with a lifecycle)
 *   AO kanban column  → Floor lane: open/bidding/working share
 *                       "building" (displayStatus carries the phase),
 *                       review → "needs_review", paid → "ready",
 *                       rejected → "archive"
 *   AO displayStatus  → Floor phase phrase ("Bidding — 3 sealed bids",
 *                       "Paid ₡80"), rendered verbatim by their card
 *   AO provider       → the job's winning agent (avatar identity)
 *   AO review run     → a Floor review pass (reviewer = harness);
 *                       an appeal is a second run by a second reviewer
 *   AO activity feed  → Floor event stream for that job
 */

import type {
  BoardSessionPresentation,
  InspectorReviewGroup,
  InspectorReviewRun,
  InspectorTimelineEvent,
} from "../../vendor/ao/product-ui";
import { credits, jobColumn, pick } from "../../lib/api";
import type { Agent, Job, Presence } from "../../lib/types";

/* Bid ticker entries (the board's live bid feed in the old console;
   rendered at the head of the event-stream panel in the AO shell). */
export interface TickerItem {
  key: number;
  who: string;
  text: string;
}

/* One entry of the per-job event log FloorClient maintains from the
   SSE/replay stream (the live equivalent of AO's session activity). */
export interface FloorEventLogItem {
  key: number;
  type: string;
  jobId?: string;
  agentName?: string;
  text: string;
  tone: "now" | "good" | "warn" | "neutral";
}

export function relTime(iso: string): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "";
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function clockTime(iso: string): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "";
  return new Date(t).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

const PAID = ["paid", "done", "completed", "closed", "accepted"];
const FAILED = ["failed", "rejected"];

export function jobToBoardSession(job: Job): BoardSessionPresentation {
  const raw = job.status.toLowerCase();
  const col = jobColumn(job);
  const bids = job.bids ?? [];
  const updatedAt =
    (pick(job as Record<string, unknown>, "updated_at", "created_at") as string) ||
    new Date().toISOString();
  const base: BoardSessionPresentation = {
    id: job.id,
    title: job.title,
    provider: job.winner ?? "Manager",
    status: "idle",
    updatedAt,
    activity: { state: "idle", lastActivityAt: updatedAt },
  };
  if (FAILED.includes(raw)) {
    return {
      ...base,
      status: "exited",
      kanbanColumn: "archive",
      displayStatus: "Rejected — unpaid",
      isTerminated: true,
      activity: { state: "exited", lastActivityAt: updatedAt },
    };
  }
  if (PAID.includes(raw)) {
    return {
      ...base,
      status: "approved",
      kanbanColumn: "ready",
      displayStatus: "Paid",
      isTerminated: true,
      activity: { state: "idle", lastActivityAt: updatedAt },
    };
  }
  switch (col) {
    case "open":
      return { ...base, kanbanColumn: "building", displayStatus: "Open — awaiting bids" };
    case "bidding":
      return {
        ...base,
        kanbanColumn: "building",
        displayStatus: bids.length ? `Bidding — ${bids.length} sealed bid${bids.length === 1 ? "" : "s"}` : "Bidding",
        activity: { state: "active", lastActivityAt: updatedAt },
      };
    case "progress":
      return {
        ...base,
        status: "working",
        kanbanColumn: "building",
        displayStatus: "Working",
        activity: { state: "active", lastActivityAt: updatedAt },
      };
    case "review":
      if (raw === "appealed" || raw === "appeal") {
        return {
          ...base,
          status: "changes_requested",
          kanbanColumn: "needs_review",
          displayStatus: "Appeal — second review",
          statusPresentation: {
            label: "Appeal — second review",
            className: "text-status-needs-you",
            indicatorClassName: "bg-status-needs-you",
          },
          activity: { state: "blocked", lastActivityAt: updatedAt },
        };
      }
      return {
        ...base,
        status: "review_pending",
        kanbanColumn: "needs_review",
        displayStatus: "Awaiting review",
        activity: { state: "waiting_input", lastActivityAt: updatedAt },
      };
    default:
      return base;
  }
}

/* The card's footer strip: the auction facts AO's PR footer slot
   carries in their app. */
export function jobCardFooter(job: Job): string {
  const bids = job.bids ?? [];
  const parts: string[] = [];
  if (job.winner) {
    const orders = (job.work_orders as Record<string, unknown>[] | undefined) ?? [];
    const agreed = orders[0] ? pick(orders[0], "agreed_price_credits", "price_credits") : undefined;
    parts.push(`Awarded to ${job.winner}${agreed !== undefined ? ` · ${credits(agreed)} agreed` : ""}`);
  }
  if (bids.length) {
    const prices = bids
      .map((b) => Number(pick(b as Record<string, unknown>, "price_credits", "price")))
      .filter((n) => Number.isFinite(n));
    if (prices.length) parts.push(`${bids.length} bids · best ${credits(Math.min(...prices))}`);
    else parts.push(`${bids.length} bids`);
  }
  if (job.budget_credits !== undefined) parts.push(`cap ${credits(job.budget_credits)}`);
  return parts.join("  ·  ");
}

export function jobTimeline(events: FloorEventLogItem[], jobId: string, limit = 40): InspectorTimelineEvent[] {
  return events
    .filter((e) => e.jobId === jobId)
    .slice(-limit)
    .reverse()
    .map((e, i) => ({
      content: e.text,
      tone: i === 0 ? "now" : e.tone,
      timestamp: null,
    }));
}

export function agentTimeline(events: FloorEventLogItem[], agentName: string, limit = 40): InspectorTimelineEvent[] {
  return events
    .filter((e) => e.agentName === agentName)
    .slice(-limit)
    .reverse()
    .map((e, i) => ({
      content: e.text,
      tone: i === 0 ? "now" : e.tone,
      timestamp: null,
    }));
}

/* Review passes for a job, from its event log: each review.completed
   is one run by its reviewer; an appeal decision is the blind second
   run. Severity rides in the verdict label (P0–P3 in Floor terms). */
export function jobReviewGroups(job: Job, events: FloorEventLogItem[]): InspectorReviewGroup[] {
  const mine = events.filter((e) => e.jobId === job.id);
  const runs: InspectorReviewRun[] = [];
  mine.forEach((e) => {
    if (e.type === "review.completed") {
      const rejected = /reject/i.test(e.text);
      const sev = /P[0-3]/i.test(e.text) ? e.text.match(/P[0-3]/i)?.[0]?.toUpperCase() : undefined;
      runs.push({
        id: `review-${e.key}`,
        harness: e.agentName ?? "Reviewer",
        createdAtLabel: "",
        status: rejected ? "rejected" : "accepted",
        verdict: {
          label: rejected ? `Rejected${sev ? ` · ${sev}` : ""}` : "Accepted",
          tone: rejected ? "danger" : "success",
        },
        body: e.text,
      });
    }
    if (e.type === "appeal.decided") {
      const upheld = /upheld/i.test(e.text);
      runs.push({
        id: `appeal-${e.key}`,
        harness: "Second reviewer (blind appeal)",
        createdAtLabel: "",
        status: upheld ? "appeal_upheld" : "appeal_denied",
        verdict: { label: upheld ? "Appeal upheld" : "Appeal denied", tone: upheld ? "success" : "danger" },
        body: e.text,
      });
    }
  });
  if (!runs.length) return [];
  return [
    {
      key: `job-${job.id}`,
      number: Number(job.id) || 0,
      title: job.title,
      meta: `${job.status}${job.system ? ` · ${job.system}` : ""}`,
      verdict: runs[runs.length - 1].verdict,
      ao: { runs },
    },
  ];
}

export function presenceLabel(agent: Agent, presence?: Presence): { text: string; dotClass: string } {
  const fired = agent.status.toLowerCase() === "fired" || agent.status.toLowerCase() === "terminated";
  if (fired) return { text: "Fired by the CFO", dotClass: "bg-status-terminated" };
  switch (presence?.state) {
    case "working":
      return { text: presence.tool ? `Working · ${presence.tool}` : "Working", dotClass: "bg-status-working animate-status-pulse" };
    case "bidding":
      return { text: "Bidding", dotClass: "bg-status-validating animate-status-pulse" };
    case "review":
      return { text: "In review", dotClass: "bg-status-in-review" };
    case "appealing":
      return { text: "Appealing", dotClass: "bg-status-needs-you animate-status-pulse" };
    case "fired":
      return { text: "Fired by the CFO", dotClass: "bg-status-terminated" };
    default:
      return { text: "Idle", dotClass: "bg-passive" };
  }
}

export function clockLabel(iso?: string | null): string {
  return iso ? clockTime(iso) : "";
}
